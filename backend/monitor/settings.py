"""Local-only settings; never send Earthdata credentials to the browser."""

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env", override=False)
STATE = ROOT / "data/monitor"
# Determine cache path: if an explicit env var is set, use it;
# otherwise default cleanly to the local project cache directory.
_env_cache = os.getenv("SARSCOPE_CACHE_DIR")
if _env_cache:
    _cand = Path(_env_cache)
    if str(_cand).startswith("/Volumes/"):
        if len(_cand.parts) > 2 and Path("/Volumes", _cand.parts[2]).is_mount():
            CACHE = _cand
        else:
            CACHE = ROOT / "data/monitor_cache"
    else:
        CACHE = _cand if _cand.is_absolute() else ROOT / _cand
else:
    CACHE = ROOT / "data/monitor_cache"

CACHE.mkdir(parents=True, exist_ok=True)
TRANSFER_LIMIT = min(int(os.getenv("SARSCOPE_TRANSFER_MB", "256")), 512) * 1024**2
CACHE_LIMIT = int(os.getenv("SARSCOPE_CACHE_GB", "10")) * 1024**3
TOKEN = os.getenv("EARTHDATA_TOKEN", "").strip()
GEOCODER = os.getenv("SARSCOPE_GEOCODER_URL", "https://photon.komoot.io/api/")
USER_AGENT = "SARScope/1.0 (local educational satellite monitoring)"


def cache_ready():
    if str(CACHE).startswith("/Volumes/"):
        return len(CACHE.parts) > 2 and Path("/Volumes", CACHE.parts[2]).is_mount()
    return True
