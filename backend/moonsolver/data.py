"""Zugriff auf die Dateien in data/ (einmal geladen, dann im Speicher)."""

from __future__ import annotations

import csv
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np

DATA = Path(os.environ.get("MOONSOLVER_DATA", Path(__file__).resolve().parents[2] / "data"))
MOON_RADIUS_KM = 1737.4
PPD = 32  # Raster von dem.tif / wac_albedo.tif


@dataclass(frozen=True)
class Feature:
    name: str
    code: str
    lat_deg: float
    lon_deg: float  # 0..360 Ost
    diameter_km: float


@lru_cache(maxsize=1)
def ephemeris():
    from skyfield.api import PlanetaryConstants, load

    ts = load.timescale()
    eph = load(str(DATA / "de421.bsp"))
    pc = PlanetaryConstants()
    pc.read_text(load(str(DATA / "moon_080317.tf")))
    pc.read_text(load(str(DATA / "pck00008.tpc")))
    pc.read_binary(load(str(DATA / "moon_pa_de421_1900-2050.bpc")))
    return ts, eph, pc.build_frame_named("MOON_ME_DE421")


@lru_cache(maxsize=1)
def gazetteer() -> tuple[Feature, ...]:
    with open(DATA / "gazetteer_moon.csv", encoding="utf-8") as fh:
        return tuple(
            Feature(r["name"], r["code"], float(r["lat_deg"]), float(r["lon_east_deg"]), float(r["diameter_km"]))
            for r in csv.DictReader(fh)
        )


@lru_cache(maxsize=1)
def maps() -> tuple[np.ndarray, np.ndarray]:
    """(Hoehe in m als float32, Albedo 0..1 als float32), je 5760 x 11520, Zeile 0 = +90 Grad."""
    import rasterio

    with rasterio.open(DATA / "dem.tif") as ds:
        dem = ds.read(1).astype(np.float32)
    with rasterio.open(DATA / "wac_albedo.tif") as ds:
        wac = ds.read(1).astype(np.float32) / 255.0
    return dem, wac
