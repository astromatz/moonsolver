"""Prueft testset/groundtruth.csv auf Plausibilitaet.

    python scripts/check_groundtruth.py

Projiziert die benannten Krater orthografisch vom topozentrischen
Beobachterpunkt (Zeit/Ort aus testset.csv) und passt eine 2D-Aehnlichkeits-
transformation (mit und ohne Spiegelung) an die geklickten Pixel an.
Grosse Restfehler deuten auf falsch benannte oder verklickte Krater hin.
"""
import csv, sys
from pathlib import Path
import numpy as np
from skyfield.api import load, wgs84, PlanetaryConstants

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent
d = root / "data"
ts = load.timescale()
eph = load(str(d / "de421.bsp"))
pc = PlanetaryConstants()
pc.read_text(load(str(d / "moon_080317.tf")))
pc.read_text(load(str(d / "pck00008.tpc")))
pc.read_binary(load(str(d / "moon_pa_de421_1900-2050.bpc")))
frame = pc.build_frame_named("MOON_ME_DE421")
gaz = {r["name"]: (float(r["lat_deg"]), float(r["lon_east_deg"])) for r in csv.DictReader(open(d / "gazetteer_moon.csv", encoding="utf-8"))}
meta = {r["file"]: r for r in csv.DictReader(open(root / "testset" / "testset.csv", encoding="utf-8"))}
gt = {}
for r in csv.DictReader(open(root / "testset" / "groundtruth.csv", encoding="utf-8")):
    gt.setdefault(r["file"], []).append((r["name"], float(r["x"]), float(r["y"])))

def fit(P, Q):  # find a,b,tx,ty: Q ~ [[a,-b],[b,a]] P + t
    A = []; B = []
    for (px, py), (qx, qy) in zip(P, Q):
        A.append([px, -py, 1, 0]); B.append(qx)
        A.append([py, px, 0, 1]); B.append(qy)
    sol, *_ = np.linalg.lstsq(np.array(A), np.array(B), rcond=None)
    a, b, tx, ty = sol
    pred = np.array([[a * px - b * py + tx, b * px + a * py + ty] for px, py in P])
    return sol, np.linalg.norm(pred - np.array(Q), axis=1)

for f, pts in gt.items():
    m = meta[f]
    t = ts.from_datetime(__import__("datetime").datetime.fromisoformat(m["time_utc"].replace("Z", "+00:00")))
    obs = eph["earth"] + wgs84.latlon(float(m["lat_deg"]), float(m["lon_deg"]))
    pos = (obs - eph["moon"]).at(t)
    R = frame.rotation_at(t)  # ICRF -> Moon ME
    v = R @ pos.position.km
    v /= np.linalg.norm(v)    # direction moon->observer in ME frame
    north = np.array([0, 0, 1.0])
    e = np.cross(north, v); e /= np.linalg.norm(e)
    n = np.cross(v, e)
    P, Q, names, missing = [], [], [], []
    for name, x, y in pts:
        if name not in gaz:
            missing.append(name); continue
        lat, lon = np.radians(gaz[name])
        s = np.array([np.cos(lat) * np.cos(lon), np.cos(lat) * np.sin(lon), np.sin(lat)])
        P.append((s @ e, s @ n)); Q.append((x, -y)); names.append(name)  # image y down -> flip
    res = {}
    for mirror in (False, True):
        PP = [(-px, py) for px, py in P] if mirror else P
        sol, err = fit(PP, Q)
        res[mirror] = (np.sqrt((err ** 2).mean()), sol, err)
    mirror = min(res, key=lambda k: res[k][0])
    rms, sol, err = res[mirror]
    scale = np.hypot(sol[0], sol[1])
    print(f"\n{f}\n  RMS {rms:.1f} px, Mondradius {scale:.0f} px, gespiegelt={mirror}, ohne Spiegelung RMS {res[False][0]:.1f}")
    for nm, er in zip(names, err):
        flag = "  <-- auffaellig" if er > max(3 * np.median(err), 0.02 * scale) else ""
        print(f"    {nm:15s} {er:6.1f} px{flag}")
    if missing:
        print("  nicht im Gazetteer:", missing)
