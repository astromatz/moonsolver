"""Beschriftet ein Foto und speichert es als PNG.

    python scripts/annotate.py FOTO ZEIT_UTC BREITE LAENGE [AUSGABE.png]
    python scripts/annotate.py testset/#4_...jpg 2021-04-20T20:00:00Z 50.9375 6.9603
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from moonsolver.geometry import moon_view  # noqa: E402
from moonsolver.observation import Observation  # noqa: E402
from moonsolver.solve import labels, solve  # noqa: E402


def main() -> int:
    if len(sys.argv) < 5:
        print(__doc__)
        return 2
    src = Path(sys.argv[1])
    t = datetime.fromisoformat(sys.argv[2].replace("Z", "+00:00"))
    obs = Observation(t, float(sys.argv[3]), float(sys.argv[4]))
    out = Path(sys.argv[5]) if len(sys.argv) > 5 else src.with_name(src.stem + "_labels.png")

    img = Image.open(src).convert("RGB")
    photo = np.asarray(img)
    view = moon_view(obs)
    sol = solve(photo, view)
    lbs = labels(sol, view, img.width, img.height, min_diameter_px=max(12, img.width / 80))
    print(f"Drehung {sol.theta_deg % 360:.1f} Grad, gespiegelt {sol.mirror}, Mondradius {sol.radius_px:.0f} px, "
          f"Score {sol.score:.2f}, {len(lbs)} Namen")

    draw = ImageDraw.Draw(img)
    size = max(12, img.width // 90)
    try:
        font = ImageFont.truetype("arial.ttf", size)
    except OSError:
        font = ImageFont.load_default()
    # grosse Krater zuerst, kleine nur, wenn sie keinen Platz belegen
    taken: list[tuple[float, float, float, float]] = []
    for lb in sorted(lbs, key=lambda b: -b.diameter_px):
        w = draw.textlength(lb.name, font=font)
        box = (lb.x + 4, lb.y - size - 2, lb.x + 6 + w, lb.y + 2)
        if any(not (box[2] < b[0] or box[0] > b[2] or box[3] < b[1] or box[1] > b[3]) for b in taken):
            continue
        taken.append(box)
        r = 3
        draw.ellipse((lb.x - r, lb.y - r, lb.x + r, lb.y + r), outline=(255, 204, 51), width=2)
        draw.text((lb.x + 5, lb.y - size - 1), lb.name, fill=(255, 204, 51), font=font,
                  stroke_width=2, stroke_fill=(0, 0, 0))
    img.save(out)
    print(f"gespeichert: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
