"""Generate the spacehack application icons (Windows .ico + macOS .icns).

The design is the game's own hero glyph — the roguelike ``@`` — rendered in
DejaVu Sans Mono (the font bundled for the Pygame UI) inside a cyan scanner
ring on deep-space navy, using the exact ``pygame_ui.Palette`` colours:

  background (3, 4, 8)      — deep-space navy
  panel      (8, 10, 16)    — disc fill
  border     (70, 82, 108)  — faint star colour
  instruction (255, 240, 175) — the amber ``@``
  selected_border (130, 210, 240) — the cyan scanner ring

Output is deterministic (seeded starfield) so the committed binaries are
reproducible.

Usage:
    python3 tools/make_icon.py            # regenerate packaging/*.ico|icns

Requires Pillow (build-time only; the generated files are committed, so the
game and the frozen builds never need Pillow).
"""

from __future__ import annotations

import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

REPO = Path(__file__).resolve().parent.parent
FONT = REPO / "src" / "spacehack" / "data" / "DejaVuSansMono.ttf"
OUT_ICO = REPO / "packaging" / "spacehack.ico"
OUT_ICNS = REPO / "packaging" / "spacehack.icns"

# pygame_ui.Palette
BG = (3, 4, 8)
PANEL = (8, 10, 16)
BORDER = (70, 82, 108)
AMBER = (255, 240, 175)
CYAN = (130, 210, 240)

SIZE = 1024
RNG_SEED = 1337
STAR_COUNT = 60

ICO_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def _stars() -> list[tuple[int, int, int, int]]:
    """Seeded starfield: (x, y, radius, alpha)."""
    rng = random.Random(RNG_SEED)
    stars = []
    for _ in range(STAR_COUNT):
        x = rng.randint(0, SIZE - 1)
        y = rng.randint(0, SIZE - 1)
        radius = rng.randint(1, 3)
        alpha = rng.randint(90, 200)
        stars.append((x, y, radius, alpha))
    return stars


def _render_master() -> Image.Image:
    """Compose the 1024x1024 master icon."""
    img = Image.new("RGBA", (SIZE, SIZE), (*BG, 255))

    # Starfield behind everything.
    stars = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(stars)
    for x, y, radius, alpha in _stars():
        draw.ellipse(
            (x - radius, y - radius, x + radius, y + radius),
            fill=(*BORDER, alpha),
        )
    img.alpha_composite(stars)

    # Scanner disc: panel-coloured circle, slightly larger than the ring.
    disc = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(disc)
    margin = 90
    draw.ellipse(
        (margin, margin, SIZE - margin, SIZE - margin),
        fill=(*PANEL, 235),
    )
    img.alpha_composite(disc)

    # Cyan scanner ring.
    ring = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(ring)
    draw.ellipse(
        (margin, margin, SIZE - margin, SIZE - margin),
        outline=(*CYAN, 255),
        width=22,
    )
    img.alpha_composite(ring)

    # Amber glow behind the @ (blurred copy at low alpha).
    glyph = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    font = ImageFont.truetype(str(FONT), 620)
    draw = ImageDraw.Draw(glyph)
    draw.text((SIZE / 2, SIZE / 2 + 14), "@", font=font, fill=(*AMBER, 255), anchor="mm")
    glow = glyph.filter(ImageFilter.GaussianBlur(30))
    glow.putalpha(glow.getchannel("A").point(lambda a: int(a * 0.45)))
    img.alpha_composite(glow)

    # Crisp @ on top.
    img.alpha_composite(glyph)

    # Subtle vignette: darken the corners for depth.
    vignette = Image.radial_gradient("L").resize((SIZE, SIZE))
    darken = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 255))
    mask = vignette.point(lambda v: int(140 - v * 0.14))
    img = Image.composite(img, darken, mask)

    return img


def main() -> None:
    assert FONT.is_file(), f"bundled font missing: {FONT}"
    OUT_ICO.parent.mkdir(parents=True, exist_ok=True)

    master = _render_master()
    master.save(str(OUT_ICO), format="ICO", sizes=ICO_SIZES)
    master.save(str(OUT_ICNS), format="ICNS")

    print(f"wrote {OUT_ICO.relative_to(REPO)} (sizes {ICO_SIZES})")
    print(f"wrote {OUT_ICNS.relative_to(REPO)} (1024x1024)")


if __name__ == "__main__":
    main()
