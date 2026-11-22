"""Randlose Testausschnitte mit bekannter Loesung.

    python scripts/make_crops.py [--n 8] [--seed 1]      # Ausschnitte erzeugen
    python scripts/make_crops.py --eval [dateiname-teil]  # Abgleich daran messen

Die Vollbilder mit Rand (#1, #2, #4) werden einmal geloest (Ergebnis in
testset/crops/parents.json zwischengespeichert). Daraus werden quadratische
Ausschnitte geschnitten, die ganz auf der beleuchteten Scheibe liegen und den
Rand nicht zeigen. Die Loesung des Vollbilds, um den Ausschnitt verschoben,
ist die Wahrheit fuer den Ausschnitt.

--eval loest jeden Ausschnitt neu und vergleicht die Lage aller beschrifteten
Krater im Ausschnitt mit der Wahrheit. Bestanden: Median < 1 % des Radius.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from moonsolver.geometry import moon_view  # noqa: E402
from moonsolver.observation import Observation  # noqa: E402
from moonsolver.solve import Solution, labels, locate, solve  # noqa: E402

TS = ROOT / "testset"
OUT = TS / "crops"
PARENTS = ("#1_", "#2_", "#4_")
SIZES = (0.35, 0.5, 0.7, 0.9)   # Kantenlaenge in Mondradien
LIMB = 0.95                     # alle Ecken innerhalb 0,95 R


def view_of(m):
    t = datetime.fromisoformat(m["time_utc"].replace("Z", "+00:00"))
    return moon_view(Observation(t, float(m["lat_deg"]), float(m["lon_deg"])))


def parent_solutions(meta):
    cache = OUT / "parents.json"
    data = json.loads(cache.read_text()) if cache.exists() else {}
    for m in meta:
        if m["file"] not in data:
            tic = time.time()
            sol = solve(np.asarray(Image.open(TS / m["file"]).convert("RGB")), view_of(m))
            data[m["file"]] = asdict(sol)
            print(f"geloest {m['file'][:40]}  score {sol.score:.3f}  {time.time() - tic:.0f}s", flush=True)
            cache.write_text(json.dumps(data, indent=1))
    return {k: Solution(**v) for k, v in data.items()}


# Arten: Groessen (in R) und Bedingung an (Anteil beleuchtet, Anteil Mare)
KINDS = {
    "c": (SIZES, lambda lit, mare: lit >= 0.9),                     # leicht: hell, beliebig
    "k": ((0.2, 0.25), lambda lit, mare: lit >= 0.9),               # klein
    "h": ((0.25, 0.35, 0.5), lambda lit, mare: lit >= 0.9 and mare < 0.05),  # reines Hochland
    "t": ((0.25, 0.35, 0.5), lambda lit, mare: 0.4 <= lit <= 0.8),  # an der Licht-Schatten-Grenze
}
DEGRADE = 4   # pro Vollbild so viele Ausschnitte zusaetzlich unscharf + verrauscht ("u")


def degrade(img: Image.Image, rng) -> Image.Image:
    from scipy.ndimage import gaussian_filter
    a = np.asarray(img, dtype=np.float32)
    a = gaussian_filter(a, sigma=(2.0, 2.0, 0))
    a += rng.normal(0, 8, a.shape)
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def sample(img, gray, lit_thr, mare_thr, sol, sizes, cond, n, rng, tag, kind):
    R, cx, cy = sol.radius_px, sol.center_x, sol.center_y
    found = []
    made = tries = 0
    while made < n and tries < 5000:
        tries += 1
        # Groessen reihum; findet sich nach 500 Versuchen keine Lage, die naechstkleinere
        side = int(sizes[max(0, made % len(sizes) - tries // 500)] * R)
        x0 = int(rng.uniform(cx - R, cx + R - side))
        y0 = int(rng.uniform(cy - R, cy + R - side))
        if x0 < 0 or y0 < 0 or x0 + side > img.width or y0 + side > img.height:
            continue
        corners = [(x0, y0), (x0 + side, y0), (x0, y0 + side), (x0 + side, y0 + side)]
        if max(np.hypot(x - cx, y - cy) for x, y in corners) > LIMB * R:
            continue
        # Mindestabstand: hoechstens halb ueberlappend mit einem schon gewaehlten Ausschnitt
        if any(abs(x0 - a) < (side + sa) / 4 and abs(y0 - b) < (side + sa) / 4 for _, a, b, sa in found):
            continue
        g, s = gray[:, y0:y0 + side, x0:x0 + side]
        lit = g > lit_thr
        lit_frac = lit.mean()
        mare_frac = ((s < mare_thr) & lit).sum() / max(1, lit.sum())
        if not cond(lit_frac, mare_frac):
            continue
        made += 1
        tries = 0
        found.append((f"{tag}{kind}{made:02d}_{side}px.jpg", x0, y0, side))
    print(f"{tag} {kind}: {made}/{n} Ausschnitte")
    return found


def make(n, seed):
    OUT.mkdir(exist_ok=True)
    for f in OUT.glob("*.jpg"):
        f.unlink()
    meta = [m for m in csv.DictReader(open(TS / "testset.csv", encoding="utf-8"))
            if m["file"].startswith(PARENTS)]
    sols = parent_solutions(meta)
    rows = []
    for m in meta:
        sol = sols[m["file"]]
        img = Image.open(TS / m["file"]).convert("RGB")
        gray = np.asarray(img.convert("L"), dtype=np.float32)
        peak = np.percentile(gray, 99)
        lit_thr = peak * 0.25   # beleuchtet: > 25 % der Spitzenhelligkeit
        # Mare: geglaettet dunkler als 85 % des hellen Hochlands (80. Perzentil) im Umkreis von R/4.
        # Der Umkreis gleicht das Abdunkeln zur Licht-Schatten-Grenze hin aus.
        # Fuer die Pruefung wird gray als Stapel (Bild, Bild/Schwelle) uebergeben.
        from scipy.ndimage import gaussian_filter, percentile_filter, zoom
        smooth = gaussian_filter(gray, sol.radius_px / 40)
        k = max(1, int(sol.radius_px / 100))
        small = smooth[::k, ::k]
        ref = percentile_filter(small, 80, size=max(3, int(sol.radius_px / 4 / k)))
        ref = zoom(ref, (gray.shape[0] / ref.shape[0], gray.shape[1] / ref.shape[1]), order=1)
        gray = np.stack([gray, smooth / np.maximum(ref, 1)])
        mare_thr = 0.85
        tag = m["file"].split("_")[0]
        for i, (kind, (sizes, cond)) in enumerate(KINDS.items()):
            rng = np.random.default_rng([seed, i])  # eigene Folge je Art: "c" bleibt gleich
            for name, x0, y0, side in sample(img, gray, lit_thr, mare_thr, sol, sizes, cond, n, rng, tag, kind):
                crop = img.crop((x0, y0, x0 + side, y0 + side))
                variants = [(name, crop)]
                if kind == "c" and int(name[len(tag) + 1:len(tag) + 3]) <= DEGRADE:
                    variants.append((name.replace(f"{tag}c", f"{tag}u", 1), degrade(crop, rng)))
                for nm, im in variants:
                    im.save(OUT / nm, quality=95)
                    rows.append({"file": nm, "kind": nm[len(tag)], "parent": m["file"], "x0": x0, "y0": y0,
                                 "side": side, "side_R": round(side / sol.radius_px, 2),
                                 "time_utc": m["time_utc"], "lat_deg": m["lat_deg"], "lon_deg": m["lon_deg"]})
    with open(OUT / "crops.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} Ausschnitte in {OUT}")


def truth(sol: Solution, x0, y0):
    return Solution(sol.theta_deg, sol.mirror, sol.radius_px, sol.center_x - x0, sol.center_y - y0, sol.score)


def evaluate(only):
    rows = [r for r in csv.DictReader(open(OUT / "crops.csv", encoding="utf-8")) if only in r["file"]]
    sols = {k: Solution(**v) for k, v in json.loads((OUT / "parents.json").read_text()).items()}
    passed = 0
    for r in rows:
        view = view_of(r)
        true = truth(sols[r["parent"]], int(r["x0"]), int(r["y0"]))
        side = int(r["side"])
        names = [lb.name for lb in labels(true, view, side, side, min_diameter_px=4)]
        photo = np.asarray(Image.open(OUT / r["file"]).convert("RGB"))
        tic = time.time()
        sol = solve(photo, view)
        dt = time.time() - tic
        a, b = locate(true, view, names), locate(sol, view, names)
        err = np.array([np.hypot(a[n][0] - b[n][0], a[n][1] - b[n][1]) for n in a])
        pct = 100 * float(np.median(err)) / true.radius_px if len(err) else float("nan")
        ok = pct < 1.0
        passed += ok
        print(f"{'OK  ' if ok else 'FAIL'} {r['file']:22s} {r['side_R']:>4s} R  score {sol.score:.2f}  "
              f"rot {sol.theta_deg - true.theta_deg:+6.1f}  R {sol.radius_px / true.radius_px:5.2f}x  "
              f"err med {pct:6.2f}% R  ({len(err)} Krater)  {dt:4.0f}s", flush=True)
    print(f"{passed}/{len(rows)} bestanden")
    return 0 if passed == len(rows) else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("only", nargs="?", default="")
    ap.add_argument("--eval", action="store_true")
    ap.add_argument("--n", type=int, default=8, help="Ausschnitte pro Vollbild")
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    if a.eval:
        return evaluate(a.only)
    make(a.n, a.seed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
