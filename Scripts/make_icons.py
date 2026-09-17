"""Rebuild the icon assets with a real alpha channel, and regenerate icon.ico.

The artwork is a rounded-square tile. Whatever produced the source PNGs left the
area outside the tile as opaque white instead of transparent, which shows up as a
white frame around the icon on a dark desktop or taskbar, and around the README
logo on GitHub's dark theme. This re-cuts each tile against transparency and
writes every icon size Windows asks for.

Run after changing assets/icon.png or assets/logo.png:

    python Scripts/make_icons.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
ICON_PNG = ASSETS / "icon.png"
LOGO_PNG = ASSETS / "logo.png"
ICON_ICO = ASSETS / "icon.ico"

# Windows picks the closest size; shipping all of them avoids blurry rescales
# in the taskbar (16/24), Explorer lists (32/48) and the Start menu (256).
ICO_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]

# Mask edges are drawn at 4x and downsampled — PIL has no antialiased drawing.
SUPERSAMPLE = 4

# The tile is inset by this much before masking, so the source's white-blended
# antialiased boundary is cut away rather than kept as a pale fringe.
ERODE_PX = 2


def _tile_bounds(im: Image.Image) -> tuple[int, int, int, int]:
    """Bounding box of the non-white tile, measured from the centre row/column."""
    px = im.convert("RGB").load()
    w, h = im.size

    def opaque(p) -> bool:
        return not (p[0] > 245 and p[1] > 245 and p[2] > 245)

    row, col = h // 2, w // 2
    left = next(x for x in range(w) if opaque(px[x, row]))
    right = next(x for x in range(w - 1, -1, -1) if opaque(px[x, row]))
    top = next(y for y in range(h) if opaque(px[col, y]))
    bottom = next(y for y in range(h - 1, -1, -1) if opaque(px[col, y]))
    return left, top, right, bottom


def _corner_radius(im: Image.Image, left: int, top: int) -> int:
    """Walk down the left edge until it reaches full width — that is the radius."""
    px = im.convert("RGB").load()
    w = im.size[0]

    def opaque(p) -> bool:
        return not (p[0] > 245 and p[1] > 245 and p[2] > 245)

    for y in range(top, top + im.size[1] // 2):
        x = next(x for x in range(w) if opaque(px[x, y]))
        if x <= left:
            return y - top
    raise ValueError("could not measure the corner radius")


def cut_tile(im: Image.Image) -> Image.Image:
    """Return *im* with everything outside its rounded tile made transparent."""
    left, top, right, bottom = _tile_bounds(im)
    radius = _corner_radius(im, left, top)

    box = (left + ERODE_PX, top + ERODE_PX, right - ERODE_PX, bottom - ERODE_PX)
    mask = Image.new("L", (im.width * SUPERSAMPLE, im.height * SUPERSAMPLE), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [c * SUPERSAMPLE for c in box],
        radius=(radius - ERODE_PX) * SUPERSAMPLE,
        fill=255,
    )
    mask = mask.resize(im.size, Image.LANCZOS)

    out = im.convert("RGBA")
    out.putalpha(mask)
    return out


def _is_cut(path: Path) -> bool:
    """True once the corners are transparent — makes re-running a no-op."""
    return Image.open(path).convert("RGBA").getpixel((1, 1))[3] == 0


def main() -> int:
    missing = [p for p in (ICON_PNG, LOGO_PNG) if not p.exists()]
    if missing:
        print("missing: " + ", ".join(str(p) for p in missing), file=sys.stderr)
        return 1

    for path in (ICON_PNG, LOGO_PNG):
        if _is_cut(path):
            print(f"{path.name} already has an alpha channel, leaving it alone")
            continue
        cut_tile(Image.open(path)).save(path)
        print(f"cut {path.name} against transparency")

    # Downscale the full-size tile per entry rather than letting save() do it, so
    # the small sizes get a proper LANCZOS resample of the alpha edge too.
    tile = Image.open(ICON_PNG).convert("RGBA")
    frames = [tile.resize(size, Image.LANCZOS) for size in ICO_SIZES]
    frames[-1].save(ICON_ICO, format="ICO", sizes=ICO_SIZES,
                    append_images=frames[:-1])
    print(f"wrote {ICON_ICO.name} ({len(ICO_SIZES)} sizes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
