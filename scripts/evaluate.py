"""Misst den Abgleich am Testset.

    python scripts/evaluate.py [dateiname-teil]

Pro Bild: gefundene Drehung/Massstab, NCC-Score, Laufzeit und der Abstand
zwischen vorhergesagter und geklickter Kraterposition (Median und Maximum, in
Pixeln und in Prozent des Mondradius). Bestanden: Median < 1 % des Radius.
"""

from __future__ import annotations

import csv
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from moonsolver.geometry import moon_view  # noqa: E402
from moonsolver.observation import Observation  # noqa: E402
from moonsolver.solve import locate, solve  # noqa: E402


def main() -> int:
    only = sys.argv[1] if len(sys.argv) > 1 else ""
    ts = ROOT / "testset"
    meta = list(csv.DictReader(open(ts / "testset.csv", encoding="utf-8")))
    gt: dict[str, list] = {}
    for r in csv.DictReader(open(ts / "groundtruth.csv", encoding="utf-8")):
        gt.setdefault(r["file"], []).append((r["name"], float(r["x"]), float(r["y"])))
    passed = 0
    rows = [m for m in meta if only in m["file"]]
    for m in rows:
        obs = Observation(datetime.fromisoformat(m["time_utc"].replace("Z", "+00:00")),
                          float(m["lat_deg"]), float(m["lon_deg"]))
        view = moon_view(obs)
        photo = np.asarray(Image.open(ts / m["file"]).convert("RGB"))
        t0 = time.time()
        sol = solve(photo, view)
        dt = time.time() - t0
        pts = gt.get(m["file"], [])
        pred = locate(sol, view, [p[0] for p in pts])
        err = np.array([np.hypot(pred[n][0] - x, pred[n][1] - y) for n, x, y in pts if n in pred])
        med = float(np.median(err)) if len(err) else float("nan")
        ok = med < 0.01 * sol.radius_px
        passed += ok
        print(f"{'OK  ' if ok else 'FAIL'} {m['file'][:40]:40s} score {sol.score:.2f}  rot {sol.theta_deg:6.1f}  "
              f"mirror {int(sol.mirror)}  R {sol.radius_px:6.0f}px  err med {med:7.1f}px "
              f"({100 * med / sol.radius_px:5.2f}%) max {err.max():7.1f}px  {dt:5.1f}s", flush=True)
    print(f"{passed}/{len(rows)} bestanden")
    return 0 if passed == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
