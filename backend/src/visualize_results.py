"""Produce a presentation image from measured outputs, with explicit caveats."""

import json

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .common import CONFIG, ROOT, read_raster


def run():
    report = json.loads((ROOT / "reports/reference_agreement.json").read_text())
    params = json.loads((ROOT / "models/baseline_parameters.json").read_text())
    before, _ = read_raster(ROOT / "data/cleaned" / f"{CONFIG['before']}_HHHH_dB.tif")
    after, _ = read_raster(ROOT / "data/cleaned" / f"{CONFIG['event']}_HHHH_dB.tif")
    classes, _ = read_raster(ROOT / "outputs/water_change_classes.tif")
    reference, _ = read_raster(ROOT / "outputs/reference_mask.tif")
    fontpath = "/System/Library/Fonts/Supplemental/Arial.ttf"

    def font(size):
        try:
            return ImageFont.truetype(fontpath, size)
        except OSError:
            return ImageFont.truetype("DejaVuSans.ttf", size)

    canvas = Image.new("RGB", (1600, 1120), "#101827")
    draw = ImageDraw.Draw(canvas)
    draw.text((35, 25), "SARScope | Candidate new open water", font=font(34), fill="white")
    draw.text(
        (35, 75),
        "North Lake Inba, Japan | Sep 14 → Sep 26, 2026 | Exploratory threshold baseline",
        font=font(22),
        fill="#b9c9db",
    )
    colors = np.array([[180, 185, 192], [40, 90, 150], [20, 220, 210], [225, 145, 55]])
    mapped = colors[np.minimum(classes, 3)].astype("uint8")
    mapped[classes == 255] = [48, 57, 72]
    # Reference boundary, rather than filled overlay, preserves candidate visibility.
    ref = reference.astype(bool)
    interior = ref.copy()
    for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        shifted = np.zeros(ref.shape, bool)
        if dy == -1:
            shifted[:-1] = ref[1:]
        elif dy == 1:
            shifted[1:] = ref[:-1]
        elif dx == -1:
            shifted[:, :-1] = ref[:, 1:]
        else:
            shifted[:, 1:] = ref[:, :-1]
        interior &= shifted
    mapped[ref & ~interior] = [255, 220, 60]
    for i, (array, title) in enumerate(
        [
            (before, "Smoothed baseline"),
            (after, "Smoothed event"),
            (mapped, "Candidate map + GSI outline"),
        ]
    ):
        x = 35 + i * 525
        draw.text((x, 125), title, font=font(23), fill="white")
        if array.ndim == 2:
            t = np.clip((np.nan_to_num(array, nan=-25) + 25) / 30, 0, 1)
            rgb = np.repeat((t * 255)[..., None], 3, axis=2).astype("uint8")
            rgb[~np.isfinite(array)] = [48, 57, 72]
        else:
            rgb = array
        img = Image.fromarray(rgb).resize((385, 620), Image.Resampling.NEAREST)
        canvas.paste(img, (x, 170))
    draw.text(
        (35, 810),
        "Intensity panels share −25 to +5 dB scale; 5×5 averaging in linear power.",
        font=font(20),
        fill="#b9c9db",
    )
    draw.text(
        (35, 850),
        f"Candidate area: {report['candidate_new_open_water_km2']:.2f} km²   |   Inside GSI outline: {100 * report['fraction_of_candidate_area_inside_reference']:.1f}%",
        font=font(26),
        fill="white",
    )
    draw.text(
        (35, 890),
        f"Valid GSI reference area detected: {100 * report['fraction_of_valid_reference_area_detected']:.1f}%   |   HH gate: {params['intensity_threshold_db']:.2f} dB; decrease ≥3 dB",
        font=font(22),
        fill="#b9c9db",
    )
    draw.text(
        (35, 935),
        "Cyan: candidate new water   •   Blue: dark on both dates   •   Orange: baseline-dark to event-bright",
        font=font(21),
        fill="#14dcd2",
    )
    draw.text(
        (35, 973),
        "Yellow: GSI Sep 25 outline   •   Gray: other valid observations   •   Dark slate: no usable pair",
        font=font(21),
        fill="#ffdc3c",
    )
    draw.text(
        (35, 1025),
        "Overlap is descriptive, not validated accuracy. Reference is one day earlier and may be incomplete.",
        font=font(21),
        fill="white",
    )
    draw.text(
        (35, 1063),
        "No supervised model trained. Vegetation, buildings, terrain, and agricultural changes can confound detection.",
        font=font(20),
        fill="#b9c9db",
    )
    canvas.save(ROOT / "outputs/candidate_water_comparison.png")


def render_radar_preview(layers, outline, affine, dates, change, destination):
    """Render shared-scale raw-date diagnostics with the reference outline."""
    fontpath = "/System/Library/Fonts/Supplemental/Arial.ttf"

    def font(size):
        try:
            return ImageFont.truetype(fontpath, size)
        except OSError:
            return ImageFont.truetype("DejaVuSans.ttf", size)

    canvas = Image.new("RGB", (1500, 1460), "#101827")
    draw = ImageDraw.Draw(canvas)
    draw.text((40, 25), "North Lake Inba | First radar comparison", font=font(34), fill="white")
    draw.text(
        (40, 76),
        "NISAR HH intensity | 20 m pixels | September–October 2026",
        font=font(22),
        fill="#bdc9d9",
    )
    W, H = change.shape[1], change.shape[0]
    plotw, ploth = 650, 520
    scale = min(plotw / W, ploth / H)
    pw, ph = round(W * scale), round(H * scale)
    panels = [(layers[(d, "HHHH")], d[:4] + "-" + d[4:6] + "-" + d[6:], False) for d in dates] + [
        (change, "Change: Sep 26 minus Sep 14", True)
    ]
    for i, (data, title, is_change) in enumerate(panels):
        ox, oy = 40 + (i % 2) * 750, 135 + (i // 2) * 615
        draw.text((ox, oy), title, font=font(25), fill="white")
        t = np.clip(
            (np.nan_to_num(data, nan=0) + (8 if is_change else 25)) / (16 if is_change else 30),
            0,
            1,
        )
        if is_change:
            low = np.array([35, 110, 220])
            mid = np.array([240, 240, 240])
            high = np.array([220, 70, 40])
            rgb = np.where(
                (t <= 0.5)[..., None],
                low + (mid - low) * t[..., None] * 2,
                mid + (high - mid) * (t[..., None] - 0.5) * 2,
            )
        else:
            rgb = np.repeat((t * 255)[..., None], 3, axis=2)
        rgb[~np.isfinite(data)] = [48, 57, 72]
        img = Image.fromarray(np.uint8(np.clip(rgb, 0, 255))).resize(
            (pw, ph), Image.Resampling.NEAREST
        )
        ix, iy = ox, oy + 42
        canvas.paste(img, (ix, iy))
        for poly in getattr(outline, "geoms", [outline]):
            for ring in [poly.exterior, *poly.interiors]:
                pts = [
                    (ix + (a - affine.c) / 20 * pw / W, iy + (affine.f - b) / 20 * ph / H)
                    for a, b in ring.coords
                ]
                draw.line(pts, fill="#ffdc55", width=2)
        label = (
            "Blue: decrease | White: 0 | Red: increase (−8 to +8 dB)"
            if is_change
            else "Shared intensity scale: black −25 dB → white +5 dB"
        )
        draw.text((ox, oy + ploth + 53), label, font=font(18), fill="#bdc9d9")
    draw.text(
        (40, 1375),
        "Yellow: GSI estimated flood outline, Sep 25. Dark slate: excluded / missing data.",
        font=font(21),
        fill="#ffdc55",
    )
    draw.text(
        (40, 1410),
        "Exploratory radar change only—not a flood classification. Reference and satellite dates differ.",
        font=font(20),
        fill="#bdc9d9",
    )
    canvas.save(destination)


if __name__ == "__main__":
    run()
