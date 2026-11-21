"""Laedt die Daten fuer Phase 1 nach data/ und bereitet sie auf.

    python scripts/fetch_data.py                 # alles, fragt vor grossen Downloads
    python scripts/fetch_data.py --only kernels,gazetteer
    python scripts/fetch_data.py --yes           # ohne Rueckfrage

Ergebnis in data/ (alle Karten im selben Raster: 32 px/Grad, einfach
zylindrisch, Laenge 0..360 Ost ab Spalte 0, Zeile 0 = Breite +90):

  de421.bsp, moon_pa_de421_1900-2050.bpc, moon_080317.tf, pck00008.tpc
                      Ephemeride und Mondorientierung (JPL/NAIF), ca. 19 MB
  gazetteer_moon.csv  IAU-Nomenklatur Mond (USGS), alle Typen inkl.
                      Satellitenkrater; Download 23 MB
  dem.tif             LOLA LDEM_64 (Hoehe in m, int16), auf 32 px/Grad
                      gemittelt; Download 531 MB
  wac_albedo.tif      LROC WAC Global Mosaik 100 m (USGS), per HTTP-Range
                      jede ~9. Zeile gelesen und horizontal gemittelt;
                      Download ca. 630 MB statt 5,7 GB

dem.tif und wac_albedo.tif brauchen rasterio (pip install -e ".[data]").
"""

from __future__ import annotations

import argparse
import csv
import io
import math
import struct
import sys
import time
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
PPD = 32  # Zielraster: Pixel pro Grad
MOON_R = 1737400.0
MOON_CRS = "+proj=longlat +R=1737400 +no_defs"

KERNELS = {
    "de421.bsp": "https://ssd.jpl.nasa.gov/ftp/eph/planets/bsp/de421.bsp",
    "moon_pa_de421_1900-2050.bpc": "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/pck/moon_pa_de421_1900-2050.bpc",
    "moon_080317.tf": "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/fk/satellites/moon_080317.tf",
    # pck00008 liegt seit pck00011 im Archivordner
    "pck00008.tpc": "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/pck/a_old_versions/pck00008.tpc",
}
GAZETTEER_URL = "https://asc-planetarynames-data.s3.us-west-2.amazonaws.com/MOON_nomenclature_center_pts.zip"
LDEM_URL = "https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/cylindrical/img/ldem_64.img"
LDEM_BYTES = 530841600  # 11520 x 23040 int16, laut ldem_64.lbl
WAC_URL = "https://planetarymaps.usgs.gov/mosaic/Lunar_LRO_LROC-WAC_Mosaic_global_100m_June2013.tif"

SIZES_MB = {"kernels": 19, "gazetteer": 23, "dem": 531, "wac": 630}
LARGE_MB = 100


def download(url: str, target: Path) -> None:
    """Laedt atomar: erst .part, dann umbenennen. Abbrueche hinterlassen nichts Halbes."""
    part = target.with_name(target.name + ".part")
    with urllib.request.urlopen(url, timeout=60) as resp, open(part, "wb") as fh:
        total = int(resp.headers.get("Content-Length", 0))
        done, last = 0, 0.0
        while chunk := resp.read(1 << 20):
            fh.write(chunk)
            done += len(chunk)
            if total > 10e6 and time.monotonic() - last > 2:
                print(f"\r  {done / 1e6:.0f}/{total / 1e6:.0f} MB", end="", flush=True)
                last = time.monotonic()
    if total > 10e6:
        print(f"\r  {done / 1e6:.0f}/{total / 1e6:.0f} MB")
    if total and done != total:
        part.unlink()
        raise OSError(f"unvollstaendig: {done} von {total} Bytes")
    part.replace(target)


# --- Kernel -----------------------------------------------------------------

def fetch_kernels() -> None:
    for name, url in KERNELS.items():
        target = DATA / name
        if target.exists():
            print(f"vorhanden: {name}")
            continue
        print(f"lade {name} ...")
        download(url, target)


# --- Gazetteer --------------------------------------------------------------

def read_dbf(raw: bytes) -> list[dict[str, str]]:
    """Minimaler dBASE-III-Leser (reicht fuer die USGS-Shapefiles, UTF-8 laut .cpg)."""
    n, hlen, rlen = struct.unpack("<IHH", raw[4:12])
    fields = []
    for i in range(32, hlen - 1, 32):
        fields.append((raw[i:i + 11].split(b"\0")[0].decode(), raw[i + 16]))
    rows = []
    for r in range(n):
        rec = raw[hlen + r * rlen: hlen + (r + 1) * rlen]
        if rec[:1] == b"*":  # geloescht
            continue
        o, vals = 1, {}
        for name, length in fields:
            vals[name] = rec[o:o + length].decode("utf-8", "replace").strip()
            o += length
        rows.append(vals)
    return rows


def fetch_gazetteer() -> None:
    target = DATA / "gazetteer_moon.csv"
    if target.exists():
        print("vorhanden: gazetteer_moon.csv")
        return
    print("lade Gazetteer ...")
    with urllib.request.urlopen(GAZETTEER_URL, timeout=60) as resp:
        blob = resp.read()
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        dbf = next(n for n in zf.namelist() if n.lower().endswith(".dbf"))
        rows = read_dbf(zf.read(dbf))
    rows = [r for r in rows if r["approval"].startswith("Adopted")]
    part = target.with_name(target.name + ".part")
    with open(part, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["name", "type", "code", "lat_deg", "lon_east_deg", "diameter_km"])
        for r in rows:
            w.writerow([r["name"], r["type"], r["code"],
                        f"{float(r['center_lat']):.5f}", f"{float(r['center_lon']) % 360:.5f}",
                        f"{float(r['diameter']):.3f}"])
    part.replace(target)
    print(f"  {len(rows)} Eintraege")


# --- Karten -----------------------------------------------------------------

def write_geotiff(target: Path, array, nodata) -> None:
    import rasterio
    from rasterio.transform import from_origin

    part = target.with_name(target.name + ".part")
    profile = dict(driver="GTiff", width=array.shape[1], height=array.shape[0], count=1,
                   dtype=array.dtype, crs=MOON_CRS, transform=from_origin(0, 90, 1 / PPD, 1 / PPD),
                   nodata=nodata, compress="deflate", tiled=True, blockxsize=512, blockysize=512)
    with rasterio.open(part, "w", **profile) as ds:
        ds.write(array, 1)
    part.replace(target)


def fetch_dem() -> None:
    import numpy as np

    target = DATA / "dem.tif"
    if target.exists():
        print("vorhanden: dem.tif")
        return
    raw = DATA / "raw" / "ldem_64.img"
    raw.parent.mkdir(exist_ok=True)
    if not raw.exists() or raw.stat().st_size != LDEM_BYTES:
        print("lade LOLA LDEM_64 (531 MB) ...")
        download(LDEM_URL, raw)
    dn = np.fromfile(raw, dtype="<i2").reshape(11520, 23040)
    # Hoehe = DN * 0.5 m (Label); 2x2 mitteln von 64 auf 32 px/Grad
    h = dn.astype(np.float32).reshape(5760, 2, 11520, 2).mean(axis=(1, 3)) * 0.5
    write_geotiff(target, np.round(h).astype(np.int16), nodata=None)
    raw.unlink()
    print(f"  dem.tif {h.shape[1]}x{h.shape[0]}, {h.min():.0f}..{h.max():.0f} m")


def fetch_wac(threads: int = 8) -> None:
    import numpy as np
    import rasterio
    from rasterio.windows import Window

    target = DATA / "wac_albedo.tif"
    if target.exists():
        print("vorhanden: wac_albedo.tif")
        return
    env = dict(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",
               GDAL_HTTP_MAX_RETRY="5", GDAL_HTTP_RETRY_DELAY="2")
    src = "/vsicurl/" + WAC_URL
    with rasterio.Env(**env), rasterio.open(src) as ds:
        width, height = ds.width, ds.height
        x0, dx = ds.transform.c, ds.transform.a
        y0, dy = ds.transform.f, ds.transform.e
    # Zielspalte fuer jede Quellspalte (Pixelmitte), Laenge auf 0..360 Ost
    lon = np.degrees((x0 + (np.arange(width) + 0.5) * dx) / MOON_R) % 360
    col = np.minimum((lon * PPD).astype(np.int64), 360 * PPD - 1)
    n_rows = 180 * PPD
    out = np.zeros((n_rows, 360 * PPD), dtype=np.uint8)

    def src_row(j: int) -> int:
        lat = 90 - (j + 0.5) / PPD
        return min(height - 1, max(0, int((math.radians(lat) * MOON_R - y0) / dy)))

    def work(js: list[int]) -> int:
        with rasterio.Env(**env), rasterio.open(src) as ds:
            for j in js:
                row = ds.read(1, window=Window(0, src_row(j), width, 1))[0]
                valid = row > 0
                s = np.bincount(col[valid], weights=row[valid], minlength=out.shape[1])
                c = np.bincount(col[valid], minlength=out.shape[1])
                out[j] = np.where(c > 0, np.round(s / np.maximum(c, 1)), 0).astype(np.uint8)
        return len(js)

    print(f"lese WAC-Mosaik zeilenweise ({n_rows} von {height} Zeilen, ca. 630 MB) ...")
    chunks = [list(range(k, n_rows, threads * 4)) for k in range(threads * 4)]
    done = 0
    with ThreadPoolExecutor(threads) as ex:
        for n in ex.map(work, chunks):
            done += n
            print(f"\r  {done}/{n_rows} Zeilen", end="", flush=True)
    print()
    write_geotiff(target, out, nodata=0)


# --- Ablauf -----------------------------------------------------------------

STEPS = {"kernels": fetch_kernels, "gazetteer": fetch_gazetteer, "dem": fetch_dem, "wac": fetch_wac}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", help="Kommagetrennt: " + ",".join(STEPS))
    ap.add_argument("--yes", action="store_true", help="grosse Downloads ohne Rueckfrage")
    args = ap.parse_args()
    steps = args.only.split(",") if args.only else list(STEPS)
    unknown = set(steps) - set(STEPS)
    if unknown:
        ap.error(f"unbekannt: {', '.join(sorted(unknown))}")
    DATA.mkdir(exist_ok=True)
    failed = []
    for step in steps:
        if SIZES_MB[step] >= LARGE_MB and not args.yes:
            try:
                answer = input(f"{step}: ca. {SIZES_MB[step]} MB laden? [j/N] ")
            except EOFError:  # kein Terminal, z. B. in CI
                answer = ""
            if answer.strip().lower() not in ("j", "y"):
                print(f"uebersprungen: {step}")
                continue
        try:
            STEPS[step]()
        except ImportError as exc:
            print(f"{step}: {exc}. Installieren mit: pip install -e \".[data]\"")
            failed.append(step)
        except OSError as exc:
            print(f"{step} fehlgeschlagen: {exc}")
            failed.append(step)
    if failed:
        print("fehlgeschlagen: " + ", ".join(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
