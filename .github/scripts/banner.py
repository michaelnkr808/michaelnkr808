#!/usr/bin/env python3
"""Draw the README header banner (light and dark versions) into assets/.

The grid on the right is a stylized attention map: a vision encoder cuts an
image into square patches, and the brighter patches are where the model is
looking. It reuses the contribution-graph greens so it matches the stats cards.
Static, so it only needs re-running when the text changes:

    python3 .github/scripts/banner.py
"""

import math
from pathlib import Path

from stats_cards import SANS, THEMES

W, H = 1280, 300
KICKER = "CS @ UC SANTA CRUZ"
NAME = "Michael Ramirez"
TAGLINE = "Computer vision · world models · robot manipulation"

COLS, ROWS, CELL, GAP = 24, 12, 15, 4
# Hot spots in grid coordinates: (column, row, spread, strength).
SPOTS = [(16.5, 5.5, 2.4, 1.0), (8.0, 8.0, 1.5, 0.6), (21.5, 1.5, 1.1, 0.45)]
CUTS = (0.2, 0.38, 0.58, 0.8)  # heat thresholds for green levels 1 to 4


def heat(c, r):
    v = sum(a * math.exp(-((c - x) ** 2 + (r - y) ** 2) / (2 * s * s)) for x, y, s, a in SPOTS)
    return v + 0.06 * math.sin(c * 12.9898 + r * 78.233)  # fixed texture, not a perfect blur


def level(v):
    return sum(v >= cut for cut in CUTS)


def banner(t):
    pitch = CELL + GAP
    gx = W - 56 - (COLS * pitch - GAP)
    gy = (H - (ROWS * pitch - GAP)) / 2
    cx, cy = SPOTS[0][:2]
    cells = []
    for r in range(ROWS):
        for c in range(COLS):
            delay = int(math.hypot(c - cx, r - cy) * 45)  # ripple out from the main hot spot
            cells.append(f'<rect class="fade" style="animation-delay:{delay}ms" x="{gx + c * pitch}" '
                         f'y="{gy + r * pitch}" width="{CELL}" height="{CELL}" rx="3" '
                         f'fill="{t["levels"][level(heat(c, r))]}"/>')
    cells = "\n".join(cells)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="{NAME}. {TAGLINE}" font-family="{SANS}">
<title>{NAME}</title>
<style>
  @keyframes fade {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
  .fade {{ animation: fade .6s ease-out both; }}
  @media (prefers-reduced-motion: reduce) {{ .fade {{ animation: none; }} }}
</style>
<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="14" fill="{t['bg']}" stroke="{t['border']}"/>
<text x="64" y="106" fill="{t['muted']}" font-size="15" font-weight="600" letter-spacing="2.5">{KICKER}</text>
<text x="62" y="174" fill="{t['text']}" font-size="68" font-weight="700" letter-spacing="-1.5">{NAME}</text>
<text x="64" y="218" fill="{t['muted']}" font-size="22">{TAGLINE}</text>
{cells}
</svg>
"""


def main():
    out = Path(__file__).resolve().parents[2] / "assets"
    out.mkdir(exist_ok=True)
    for name, t in THEMES.items():
        (out / f"banner-{name}.svg").write_text(banner(t))
    print(f"wrote banner-dark.svg and banner-light.svg to {out}")


if __name__ == "__main__":
    main()
