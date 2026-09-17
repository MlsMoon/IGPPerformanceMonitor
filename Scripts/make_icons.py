"""Draw the app icon and write assets/icon.png, assets/logo.png, assets/icon.ico.

The mark is a dark rounded tile carrying a rising trend line over three bars —
a frame-rate graph. It is drawn here rather than shipped as opaque raster art
because two things kept going wrong by hand:

* The exported PNGs had no alpha, so the corners were opaque white and every
  dark desktop, taskbar and GitHub README drew a white frame around the icon.
* A single 512px drawing scaled down to 16px turned the trend line into mush.

So the geometry lives in normalised coordinates, and sizes at or below
SMALL_MAX_PX get a simplified variant with the line dropped and the bars
enlarged — the usual answer for small icon sizes, since three bold bars stay
readable at 16px where a 1px zigzag does not.

Run after changing anything here:

    python Scripts/make_icons.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
ICON_PNG = ASSETS / "icon.png"
LOGO_PNG = ASSETS / "logo.png"
ICON_ICO = ASSETS / "icon.ico"

MASTER_PX = 512

# Windows picks the closest entry; shipping all of them avoids blurry rescales
# in the taskbar (16/24), Explorer lists (32/48) and the Start menu (256).
ICO_SIZES = [16, 24, 32, 48, 64, 128, 256]
SMALL_MAX_PX = 32       # at or below this, drop the trend line

# PIL has no antialiased drawing, so everything is drawn large and downsampled.
SUPERSAMPLE = 4

# Mirrors theme.DARK: tile between window_bg and card_bg, marks on the accent
# palette so the icon and the charts it stands for use the same colours.
TILE = "#1b1f28"
# The tile is nearly the colour of a dark Windows taskbar, so it needs a hairline
# to read as a shape there. Same trick the stats list uses to separate its rows.
TILE_EDGE = "#333b49"
BLUE = "#4dabf7"
GREEN = "#51cf66"
PURPLE = "#cc5de8"
CYAN = "#22d3ee"

# Corner radius as a fraction of the canvas. The UI caps its radii at 6px on
# ~300px surfaces; an app icon conventionally sits rounder than that, but the
# 17.6% squircle this replaces read as iOS rather than as a Windows tool.
TILE_INSET = 0.020
TILE_RADIUS = 0.105
TILE_EDGE_WIDTH = 0.008

# (x, top, colour) with a shared baseline — normalised to the canvas.
BAR_WIDTH = 0.148
BAR_BASE = 0.815
BAR_RADIUS = 0.020
BARS = [(0.212, 0.586, BLUE), (0.426, 0.512, GREEN), (0.640, 0.625, PURPLE)]

LINE_WIDTH = 0.050
LINE = [(0.195, 0.412), (0.330, 0.330), (0.470, 0.386),
        (0.605, 0.258), (0.742, 0.295), (0.842, 0.190)]

# Bars only: fewer, larger shapes so the mark survives a 16px box.
SMALL_BAR_WIDTH = 0.170
SMALL_BAR_BASE = 0.780
SMALL_BAR_RADIUS = 0.030
SMALL_BARS = [(0.175, 0.420, BLUE), (0.415, 0.280, GREEN), (0.655, 0.500, PURPLE)]


def _draw_polyline(draw: ImageDraw.ImageDraw, points, width: float, colour: str):
    """Polyline with round joins and caps (PIL only offers mitred joins)."""
    draw.line(points, fill=colour, width=int(round(width)), joint="curve")
    r = width / 2
    for x, y in points:
        draw.ellipse([x - r, y - r, x + r, y + r], fill=colour)


def draw_icon(px: int, small: bool = False) -> Image.Image:
    """Render the mark at *px*, using the simplified variant when *small*."""
    canvas = px * SUPERSAMPLE
    im = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)

    inset = TILE_INSET * canvas
    draw.rounded_rectangle(
        [inset, inset, canvas - inset - 1, canvas - inset - 1],
        radius=TILE_RADIUS * canvas,
        fill=TILE,
        outline=TILE_EDGE,
        width=max(1, int(round(TILE_EDGE_WIDTH * canvas))),
    )

    bars, width, base, radius = (
        (SMALL_BARS, SMALL_BAR_WIDTH, SMALL_BAR_BASE, SMALL_BAR_RADIUS) if small
        else (BARS, BAR_WIDTH, BAR_BASE, BAR_RADIUS)
    )
    for x, top, colour in bars:
        draw.rounded_rectangle(
            [x * canvas, top * canvas, (x + width) * canvas, base * canvas],
            radius=radius * canvas,
            fill=colour,
        )

    if not small:
        _draw_polyline(draw, [(x * canvas, y * canvas) for x, y in LINE],
                       LINE_WIDTH * canvas, CYAN)

    return im.resize((px, px), Image.LANCZOS)


def main() -> int:
    ASSETS.mkdir(parents=True, exist_ok=True)

    master = draw_icon(MASTER_PX)
    master.save(ICON_PNG)
    master.save(LOGO_PNG)

    frames = [draw_icon(size, small=size <= SMALL_MAX_PX) for size in ICO_SIZES]
    sizes = [(s, s) for s in ICO_SIZES]
    frames[-1].save(ICON_ICO, format="ICO", sizes=sizes, append_images=frames[:-1])

    small = [s for s in ICO_SIZES if s <= SMALL_MAX_PX]
    print(f"wrote {ICON_PNG.name}, {LOGO_PNG.name}, "
          f"{ICON_ICO.name} ({len(ICO_SIZES)} sizes, simplified at {small})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
