#!/usr/bin/env python3
"""Generate a background-removed thumbnail for a plant's newest photo.

Thumbnails are OPTIONAL and only worth making for plants whose cutout comes
out clean (solid foliage / a clear pot against a plain background). Fine or
spiky foliage — palms, ferny fronds, spilling vines — tends to ghost badly at
thumbnail scale, so leave those on their full-photo thumbnail.

The output is a transparent PNG saved next to the source photo as
`<photo-stem>-thumb.png`. The report (`generate_report.py`) automatically
prefers that file for a plant's list-view avatar when it exists, letting the
plant float on the card color; otherwise it falls back to the full photo.

Requires `rembg`, `onnxruntime`, and `pillow` (not needed to build the report
itself — only to make a thumbnail):

    pip install rembg onnxruntime pillow

Usage:
    python3 make_thumbnail.py <plant-id> [<plant-id> ...]
    python3 make_thumbnail.py --all        # every plant (review the results!)
"""

import sys
from pathlib import Path

from PIL import Image, ImageOps

from generate_report import load_plants, photo_list, PLANTS_DIR, OUTPUT

DOCS = OUTPUT.parent
WORK = 640   # size fed to the matting model (bigger = cleaner edges)
OUT = 138    # final thumbnail side (~3× the 46px avatar, for retina)


def _square(im, side):
    im = ImageOps.exif_transpose(im).convert("RGB")
    w, h = im.size
    m = min(w, h)
    return im.crop(((w - m) // 2, (h - m) // 2, (w - m) // 2 + m, (h - m) // 2 + m)).resize(
        (side, side), Image.LANCZOS
    )


def make_thumb(plant, session):
    from rembg import remove

    photos = photo_list(plant)
    if not photos:
        return None
    src = photos[-1]["src"]                      # newest photo
    src_path = DOCS / src
    if not src_path.exists():
        return None

    cut = remove(_square(Image.open(src_path), WORK), session=session)  # RGBA, transparent bg
    cut = cut.resize((OUT, OUT), Image.LANCZOS)

    dest = DOCS / (src.rsplit(".", 1)[0] + "-thumb.png")
    dest.parent.mkdir(parents=True, exist_ok=True)
    cut.save(dest, "PNG", optimize=True)
    return dest


def main(argv):
    if not argv:
        print(__doc__)
        return 1

    from rembg import new_session
    session = new_session("u2netp")

    plants = load_plants()
    ids = sorted(plants) if argv == ["--all"] else argv
    for pid in ids:
        plant = plants.get(pid)
        if plant is None:
            print(f"  ✗ no plant '{pid}' in {PLANTS_DIR}")
            continue
        dest = make_thumb(plant, session)
        print(f"  ✓ {pid} → {dest.relative_to(DOCS.parent)}" if dest else f"  – {pid}: no usable photo")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
