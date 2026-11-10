#!/usr/bin/env python3
"""Draw the README header banner (light and dark versions) into assets/.

The grid on the right is a stylized attention map: a vision encoder cuts an
image into square patches, and the brighter patches are where the model is
looking. The squares are windows onto a few soft green glows that drift slowly
behind them, so the "attention" wanders around the grid. It reuses the
contribution-graph greens so it matches the stats cards. Static file, so it
only needs re-running when something here changes:

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
PITCH = CELL + GAP
GX = W - 56 - (COLS * PITCH - GAP)
GY = (H - (ROWS * PITCH - GAP)) // 2

# Glows: start (column, row), radius in px, gradient, loop seconds, and the
# offsets in px it drifts through before returning to the start.
GLOWS = [
    ((16.5, 5.5), 105, "hot", 22, [(-150, 50), (-230, -20), (-90, -60)]),
    ((8.0, 8.0), 70, "warm", 17, [(120, -90), (220, 20)]),
    ((21.5, 1.5), 55, "warm", 26, [(-260, 140)]),
]


def keyframes(name, offsets):
    stops = [(0, 0)] + offsets + [(0, 0)]
    steps = " ".join(f"{100 * i / (len(stops) - 1):.0f}% {{ transform: translate({x}px, {y}px); }}"
                     for i, (x, y) in enumerate(stops))
    return f"@keyframes {name} {{ {steps} }}"


def banner(t, theme):
    lv = t["levels"]
    blend = "lighten" if theme == "dark" else "darken"  # overlapping glows keep the stronger green
    gradients = {
        "hot": [(0, lv[4], 1), (.3, lv[3], 1), (.55, lv[2], 1), (.8, lv[1], .7), (1, lv[1], 0)],
        "warm": [(0, lv[3], 1), (.45, lv[2], 1), (.8, lv[1], .6), (1, lv[1], 0)],
    }
    defs = []
    for gid, stops in gradients.items():
        s = "".join(f'<stop offset="{o}" stop-color="{c}" stop-opacity="{a}"/>' for o, c, a in stops)
        defs.append(f'<radialGradient id="{gid}">{s}</radialGradient>')

    # The mask is the grid of squares; they fade in rippling out from the main glow.
    (c0, r0) = GLOWS[0][0]
    cells = []
    for r in range(ROWS):
        for c in range(COLS):
            delay = int(math.hypot(c - c0, r - r0) * 45)
            cells.append(f'<rect class="fade" style="animation-delay:{delay}ms" x="{GX + c * PITCH}" '
                         f'y="{GY + r * PITCH}" width="{CELL}" height="{CELL}" rx="3" fill="#fff"/>')
    gw, gh = COLS * PITCH - GAP, ROWS * PITCH - GAP
    defs.append(f'<mask id="cells" maskUnits="userSpaceOnUse" x="{GX}" y="{GY}" width="{gw}" height="{gh}">'
                + "\n".join(cells) + "</mask>")

    css, glows = [], []
    for i, ((c, r), radius, grad, secs, offsets) in enumerate(GLOWS):
        css.append(keyframes(f"drift{i}", offsets))
        css.append(f".g{i} {{ mix-blend-mode: {blend}; animation: drift{i} {secs}s ease-in-out infinite; }}")
        glows.append(f'<circle class="g{i}" cx="{GX + c * PITCH + CELL / 2:.0f}" cy="{GY + r * PITCH + CELL / 2:.0f}" '
                     f'r="{radius}" fill="url(#{grad})"/>')

    nl = "\n"
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="{NAME}. {TAGLINE}" font-family="{SANS}">
<title>{NAME}</title>
<defs>
{nl.join(defs)}
</defs>
<style>
  @keyframes fade {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
  .fade {{ animation: fade .6s ease-out both; }}
  {(nl + "  ").join(css)}
  @media (prefers-reduced-motion: reduce) {{ .fade, .g0, .g1, .g2 {{ animation: none; }} }}
</style>
<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="14" fill="{t['bg']}" stroke="{t['border']}"/>
<text x="64" y="106" fill="{t['muted']}" font-size="15" font-weight="600" letter-spacing="2.5">{KICKER}</text>
<text x="62" y="174" fill="{t['text']}" font-size="68" font-weight="700" letter-spacing="-1.5">{NAME}</text>
<text x="64" y="218" fill="{t['muted']}" font-size="22">{TAGLINE}</text>
<g mask="url(#cells)">
  <rect x="{GX}" y="{GY}" width="{gw}" height="{gh}" fill="{lv[0]}"/>
  {(nl + "  ").join(glows)}
</g>
</svg>
"""


def main():
    out = Path(__file__).resolve().parents[2] / "assets"
    out.mkdir(exist_ok=True)
    for name, t in THEMES.items():
        (out / f"banner-{name}.svg").write_text(banner(t, name))
    print(f"wrote banner-dark.svg and banner-light.svg to {out}")


if __name__ == "__main__":
    main()
