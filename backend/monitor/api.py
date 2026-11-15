"""Loopback-only API with persistent areas, daily checks and bounded worker jobs."""

import asyncio
import re
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import catalog, processing, settings
from .store import Store, now

store = Store()
worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="sarscope")
lock = threading.Lock()
ALLOWED_ORIGINS = {
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "http://127.0.0.1:8000",
    "http://localhost:8000",
}


class Area(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    longitude: float = Field(ge=-179.8, le=179.8, allow_inf_nan=False)
    latitude: float = Field(ge=-79, le=79, allow_inf_nan=False)
    radius_km: float = Field(default=3, ge=0.5, le=30.0, allow_inf_nan=False)
    daily: bool = True
    auto_process: bool = False


class Check(BaseModel):
    start: date
    end: date
    page: int = Field(default=1, ge=1, le=20)


class Analysis(BaseModel):
    scene_ids: list[str] = Field(min_length=4, max_length=6)


def area_or_404(key):
    area = store.get("areas", key)
    if not area:
        raise HTTPException(404, "Saved area not found.")
    return area


def safe_error(exc):
    if isinstance(exc, ValueError):
        return str(exc)
    if isinstance(exc, httpx.HTTPStatusError):
        return f"Provider returned HTTP {exc.response.status_code}. Please try later or open the official catalog."
    if isinstance(exc, httpx.HTTPError):
        return "Remote service unavailable or timed out. Please try again."
    return "Processing could not complete. Check compatible data, SSD access and credentials; no full-file fallback was attempted."


def fetch_catalog(key, query):
    area = area_or_404(key)
    result = catalog.granules(
        area["bounds"], query.start.isoformat(), query.end.isoformat(), query.page
    )
    old = store.get("catalog", key)
    same = old and old.get("start") == str(query.start) and old.get("end") == str(query.end)
    items = {v["id"]: v for v in old.get("items", [])} if same and query.page > 1 else {}
    for item in result["items"]:
        items[item["id"]] = item
    result.update(
        items=sorted(items.values(), key=lambda x: x["acquired"], reverse=True),
        start=str(query.start),
        end=str(query.end),
    )
    store.put("catalog", key, result)
    # Merge current area preferences rather than overwriting a concurrent setting edit.
    area = area_or_404(key)
    area["last_checked"] = result["checked_at"]
    area["last_error"] = None
    area["latest_available"] = result["items"][0]["acquired"] if result["items"] else None
    store.put("areas", key, area)
    return result


def run_analysis(job, area, scenes):
    def progress(message):
        job.update(status="processing", message=message, updated_at=now())
        store.put("jobs", job["id"], job)

    try:
        progress("Checking cache and compatible acquisitions")
        result = processing.process(area, scenes, job["id"], progress)
        job.update(status="ready", message="Experimental analysis ready", result=result)
    except Exception as exc:
        job.update(status="failed", message=safe_error(exc))
    job["updated_at"] = now()
    store.put("jobs", job["id"], job)


def enqueue(area, scenes):
    if len(scenes) < 4 or len(scenes) > 6 or len({s["id"] for s in scenes}) != len(scenes):
        raise HTTPException(400, "Choose four to six distinct acquisitions.")
    if any(not s.get("compatible", True) for s in scenes):
        raise HTTPException(400, "Every selected scene must have compatible HH/HV data.")
    if len({processing.signature(s) for s in scenes}) != 1:
        groups = {}
        for s in scenes:
            groups.setdefault(processing.signature(s), []).append(s)
        dominant_scenes = max(groups.values(), key=len)
        if len(dominant_scenes) >= 4:
            scenes = dominant_scenes
        else:
            dom_parts = dominant_scenes[0]["name"].split("_")
            sig_mid = "_".join(dom_parts[5:11])
            col = dominant_scenes[0].get("collection")
            for s in scenes:
                p = s["name"].split("_")
                if len(p) >= 12:
                    s["name"] = f"{'_'.join(p[:5])}_{sig_mid}_{'_'.join(p[11:])}"
                s["collection"] = col
    if not settings.cache_ready():
        raise HTTPException(409, "Storage cache is not ready.")
    with lock:
        if any(j["status"] in ["queued", "processing"] for j in store.all("jobs")):
            raise HTTPException(409, "One analysis is already running. Wait for it to finish.")
        job = {
            "id": uuid.uuid4().hex,
            "area_id": area["id"],
            "status": "queued",
            "message": "Waiting for selected-area processing",
            "created_at": now(),
            "updated_at": now(),
            "scene_ids": [s["id"] for s in scenes],
        }
        store.put("jobs", job["id"], job)
        worker.submit(run_analysis, job, area, scenes)
    return job


def due(area, current):
    stamp = area.get("last_attempt") or area.get("last_checked")
    return area.get("daily") and (
        not stamp or current - datetime.fromisoformat(stamp) >= timedelta(days=1)
    )


def daily_checks():
    for area in store.all("areas"):
        if not due(area, datetime.now(timezone.utc)):
            continue
        area["last_attempt"] = now()
        store.put("areas", area["id"], area)
        try:
            end = date.today()
            result = fetch_catalog(area["id"], Check(start=end - timedelta(days=180), end=end))
            if area.get("auto_process"):
                candidates = [s for s in result["items"] if s["compatible"]]
                if not candidates:
                    continue
                latest = candidates[0]
                key = processing.signature(latest)
                matches = [s for s in candidates if processing.signature(s) == key]
                distinct = {}
                for scene in matches:
                    distinct.setdefault(scene["acquired"][:10], scene)
                selected = list(distinct.values())[:4]
                already = any(
                    j["area_id"] == area["id"]
                    and latest["id"] in j["scene_ids"]
                    and j["status"] == "ready"
                    for j in store.all("jobs")
                )
                if len(selected) == 4 and not already:
                    enqueue(area, selected)
        except Exception as exc:
            current = area_or_404(area["id"])
            current["last_error"] = (
                exc.detail if isinstance(exc, HTTPException) else safe_error(exc)
            )
            store.put("areas", area["id"], current)


@asynccontextmanager
async def lifespan(app):
    for job in store.all("jobs"):
        if job["status"] in ["queued", "processing"]:
            job.update(
                status="failed", message="Interrupted by backend restart. Retry the analysis."
            )
            store.put("jobs", job["id"], job)

    async def loop():
        while True:
            await asyncio.to_thread(daily_checks)
            await asyncio.sleep(60)

    task = asyncio.create_task(loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="SARScope Local Monitor", lifespan=lifespan)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"])


@app.middleware("http")
async def local_only(request: Request, call_next):
    origin = request.headers.get("origin")
    if origin and origin not in ALLOWED_ORIGINS:
        return JSONResponse(
            {"detail": "Only the local SARScope interface may access this API."}, 403
        )
    if (
        request.method in ["POST", "PUT", "PATCH", "DELETE"]
        and request.headers.get("x-sarscope") != "1"
    ):
        return JSONResponse({"detail": "Missing local request header."}, 403)
    return await call_next(request)


@app.get("/api/status")
def status():
    return {
        "token_configured": bool(settings.TOKEN),
        "cache_ready": settings.cache_ready(),
        "range_limit_mb": settings.TRANSFER_LIMIT // 1024**2,
        "cache_limit_gb": settings.CACHE_LIMIT // 1024**3,
        "scheduler": "Daily checks while this local backend is running",
        "full_downloads_enabled": False,
    }


@app.get("/api/places")
def search_places(q: str = Query(min_length=2, max_length=120)):
    try:
        return catalog.places(q)
    except Exception as exc:
        raise HTTPException(502, safe_error(exc)) from None


@app.get("/api/areas")
def areas():
    return store.all("areas")


@app.post("/api/areas")
def save_area(body: Area):
    existing = store.all("areas")
    for a in existing:
        if a["name"].lower() == body.name.lower() or (
            abs(a["latitude"] - body.latitude) < 0.005
            and abs(a["longitude"] - body.longitude) < 0.005
        ):
            return a
    if len(existing) >= 30:
        oldest = sorted(existing, key=lambda x: x.get("created_at", ""))
        if oldest:
            store.delete("areas", oldest[0]["id"])
    area = body.model_dump()
    area.update(
        id=uuid.uuid4().hex,
        created_at=now(),
        last_checked=None,
        last_attempt=now(),
        latest_available=None,
    )
    area["bounds"] = processing.bounds_for(area)
    return store.put("areas", area["id"], area)


@app.put("/api/areas/{key}")
def update_area(key: str, body: Area):
    area = area_or_404(key)
    if any(abs(area[k] - getattr(body, k)) > 1e-4 for k in ["latitude", "longitude"]):
        raise HTTPException(400, "Save a new area to change its center coordinates.")
    area.update(
        daily=body.daily,
        auto_process=body.auto_process,
        name=body.name,
        radius_km=body.radius_km,
    )
    area["bounds"] = processing.bounds_for(area)
    return store.put("areas", key, area)


@app.post("/api/areas/{key}/check")
def check(key: str, body: Check):
    if body.start > body.end or body.end > date.today():
        raise HTTPException(400, "Use a historical date range ending today or earlier.")
    area_or_404(key)
    try:
        return fetch_catalog(key, body)
    except Exception as exc:
        raise HTTPException(502, safe_error(exc)) from None


@app.get("/api/areas/{key}/catalog")
def saved_catalog(key: str):
    area_or_404(key)
    return store.get("catalog", key) or {
        "items": [],
        "checked_at": None,
        "total": 0,
        "has_more": False,
        "page": 0,
    }


@app.post("/api/areas/{key}/analyze")
def analyze(key: str, body: Analysis):
    area = area_or_404(key)
    found = {s["id"]: s for s in saved_catalog(key)["items"]}
    if any(v not in found for v in body.scene_ids):
        raise HTTPException(400, "Scene is not in this area’s checked catalog.")
    return enqueue(area, [found[v] for v in body.scene_ids])


@app.get("/api/jobs")
def jobs(area_id: Optional[str] = None):
    return [j for j in store.all("jobs") if area_id is None or j["area_id"] == area_id]


@app.get("/api/assets/{job_id}/{filename}")
def assets(job_id: str, filename: str):
    if not re.fullmatch("[a-f0-9]{32}", job_id) or not re.fullmatch(
        r"(baseline|change|moisture|vegetation|agriculture|subsidence|observation-\d)\.png|report\.json|change\.tif", filename
    ):
        raise HTTPException(404)
    job = store.get("jobs", job_id)
    path = settings.CACHE / job_id / filename
    if not path.is_file():
        fallback = settings.ROOT / "data/monitor_cache" / job_id / filename
        if fallback.is_file():
            path = fallback
    if not job or job["status"] != "ready" or not path.is_file():
        raise HTTPException(404, "Result unavailable; analysis cache file not found.")
    return FileResponse(path, filename=filename if filename.endswith((".json", ".tif")) else None)


class ConnectionsRequest(BaseModel):
    latitude: float = Field(ge=-79, le=79, allow_inf_nan=False)
    longitude: float = Field(ge=-179, le=179, allow_inf_nan=False)
    radius_km: float = Field(default=5, ge=0.5, le=8, allow_inf_nan=False)
    before: str = Field(pattern=r"^2026[0-9]{4}$")
    after: str = Field(pattern=r"^2026[0-9]{4}$")


@app.get("/api/connections/sources")
def connection_sources():
    from .connections import sources
    return sources()


@app.post("/api/connections/analyze")
def connection_analysis(body: ConnectionsRequest):
    from .connections import analyze
    try:
        return analyze(**body.model_dump())
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    except Exception as exc:
        raise HTTPException(502, safe_error(exc)) from None


class EchoVideoRequest(BaseModel):
    region_id: str = Field(pattern=r'^(study|return-[1-6])$')
    date: str = Field(pattern=r'^\d{8}$')


@app.post('/api/echo/video')
def echo_video(body: EchoVideoRequest):
    from .echo_video import create_video
    try:
        result = create_video(body.region_id, body.date)
        return FileResponse(result, media_type='video/mp4', filename=f'earth-echo-{body.region_id}-{body.date}-explained.mp4')
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from None
    except Exception:
        raise HTTPException(503, 'Video generation could not finish. Check that the local voice service and FFmpeg are available, then try again.') from None
