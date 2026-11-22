"""Zeitversatz-Test: Wie stark haengt der Abgleich von der Aufnahmezeit ab?

    python scripts/time_offset.py [dateiname-teil] [--range 180] [--step 15] [--dim 512]

Pro Bild einmal voll loesen (Zeit aus testset.csv), dann fuer jeden Versatz
die Ansicht neu rechnen und nur lokal um die Loesung verfeinern. Ausgabe pro
Versatz: NCC-Score, Drehung, Radius und Median-Fehler gegen die Ground Truth.
Das Score-Maximum zeigt, welche Zeit am besten zum Schattenwurf passt
(z. B. #3: MEZ oder UTC, also Versatz 0 oder +60 min).
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from moonsolver.geometry import moon_view  # noqa: E402
from moonsolver.observation import Observation  # noqa: E402
from moonsolver.solve import _refine, locate, prepare, solve  # noqa: E402


def local_fit(photo, view, sol, dim):
    """Verfeinert sol fuer eine neue Ansicht, ohne Grobsuche."""
    mid, f = prepare(photo, dim)
    s = _refine(mid, view, sol.scaled(f), 3, 7, 0.06, 7, 0.15)
    return _refine(mid, view, s, 1.0, 7, 0.02, 7, 0.06).scaled(1 / f)


def gt_error(sol, view, pts):
    pred = locate(sol, view, [p[0] for p in pts])
    err = [np.hypot(pred[n][0] - x, pred[n][1] - y) for n, x, y in pts if n in pred]
    return float(np.median(err)) if err else float("nan")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("only", nargs="?", default="")
    ap.add_argument("--range", type=int, default=180, help="Versatz +-Minuten")
    ap.add_argument("--step", type=int, default=15, help="Schrittweite in Minuten")
    ap.add_argument("--dim", type=int, default=512, help="Bildgroesse fuer die Verfeinerung")
    ap.add_argument("--csv", type=Path, help="Ergebnisse zusaetzlich als CSV schreiben")
    a = ap.parse_args()

    ts = ROOT / "testset"
    meta = [m for m in csv.DictReader(open(ts / "testset.csv", encoding="utf-8")) if a.only in m["file"]]
    gt: dict[str, list] = {}
    for r in csv.DictReader(open(ts / "groundtruth.csv", encoding="utf-8")):
        gt.setdefault(r["file"], []).append((r["name"], float(r["x"]), float(r["y"])))
    offsets = list(range(-a.range, a.range + 1, a.step))
    out_rows = []

    for m in meta:
        t0 = datetime.fromisoformat(m["time_utc"].replace("Z", "+00:00"))
        lat, lon = float(m["lat_deg"]), float(m["lon_deg"])
        photo = np.asarray(Image.open(ts / m["file"]).convert("RGB"))
        pts = gt.get(m["file"], [])
        tic = time.time()
        base = solve(photo, moon_view(Observation(t0, lat, lon)))
        print(f"\n{m['file'][:50]}  ({m['time_utc']}, Unsicherheit {m['time_uncertainty_min']} min)  "
              f"Basis score {base.score:.3f}, {time.time() - tic:.0f}s", flush=True)
        print("  Versatz   Score   Drehung   Radius   Fehler med (% R)")
        res = []
        for dm in offsets:
            view = moon_view(Observation(t0 + timedelta(minutes=dm), lat, lon))
            sol = local_fit(photo, view, base, a.dim)
            med = gt_error(sol, view, pts)
            res.append((dm, sol, med))
            out_rows.append({"file": m["file"], "offset_min": dm, "score": round(sol.score, 4),
                             "theta_deg": round(sol.theta_deg, 2), "radius_px": round(sol.radius_px, 1),
                             "err_med_px": round(med, 2), "err_med_pct": round(100 * med / sol.radius_px, 3)})
            print(f"  {dm:+5d} min  {sol.score:.4f}  {sol.theta_deg:7.2f}  {sol.radius_px:7.1f}  "
                  f"{med:7.1f}px ({100 * med / sol.radius_px:5.2f}%)", flush=True)
        best = max(res, key=lambda r: r[1].score)
        low = min(res, key=lambda r: r[2] if np.isfinite(r[2]) else np.inf)
        print(f"  -> bester Score bei {best[0]:+d} min, kleinster GT-Fehler bei {low[0]:+d} min")

    if a.csv and out_rows:
        with open(a.csv, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(out_rows[0]))
            w.writeheader()
            w.writerows(out_rows)
        print(f"\nCSV: {a.csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
