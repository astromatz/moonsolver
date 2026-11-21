"""Mondgeometrie fuer eine Aufnahme.

Alle Vektoren im mondfesten Mean-Earth-System (MOON_ME_DE421): x zeigt auf
0 Grad Laenge, z zum Nordpol. Grundlage sind Skyfield, DE421 und die
NAIF-Mondkerne aus data/.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .data import MOON_RADIUS_KM, ephemeris
from .observation import Observation


@dataclass(frozen=True)
class MoonView:
    libration_lon_deg: float      # selenografische Laenge des Scheibenmittelpunkts (-180..180)
    libration_lat_deg: float
    subsolar_lon_deg: float
    subsolar_lat_deg: float
    axis_position_angle_deg: float  # Positionswinkel der Mondachse, von Himmelsnord ueber Ost
    apparent_diameter_arcsec: float
    distance_km: float
    observer_dir: np.ndarray = field(repr=False, compare=False)  # Einheitsvektor Mond -> Beobachter
    sun_dir: np.ndarray = field(repr=False, compare=False)       # Einheitsvektor Mond -> Sonne

    def basis(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """(Ost, Nord, Sichtlinie): Bildachsen mit Mond-Nord oben und Ost rechts."""
        v = self.observer_dir
        e = np.cross([0.0, 0.0, 1.0], v)
        e /= np.linalg.norm(e)
        return e, np.cross(v, e), v


def _latlon(vec: np.ndarray) -> tuple[float, float]:
    x, y, z = vec / np.linalg.norm(vec)
    return math.degrees(math.asin(z)), (math.degrees(math.atan2(y, x)) + 180) % 360 - 180


def moon_view(obs: Observation) -> MoonView:
    from skyfield.api import wgs84

    ts, eph, frame = ephemeris()
    t = ts.from_datetime(obs.time_utc)
    observer = eph["earth"] + wgs84.latlon(obs.latitude_deg, obs.longitude_deg, elevation_m=obs.elevation_m)
    moon_icrf = observer.at(t).observe(eph["moon"]).apparent().position.km  # Beobachter -> Mond
    sun_icrf = (eph["sun"] - eph["moon"]).at(t).position.km
    rot = frame.rotation_at(t)  # ICRF -> ME

    dist = float(np.linalg.norm(moon_icrf))
    v = rot @ (-moon_icrf / dist)
    s = rot @ (sun_icrf / np.linalg.norm(sun_icrf))
    lib_lat, lib_lon = _latlon(v)
    sun_lat, sun_lon = _latlon(s)

    # Positionswinkel: Mond-Nordpol an den Himmel projiziert, gemessen von Himmelsnord ueber Ost
    los = moon_icrf / dist
    pole = rot.T @ np.array([0.0, 0.0, 1.0])
    cel_north = np.array([0.0, 0.0, 1.0]) - los * los[2]
    cel_north /= np.linalg.norm(cel_north)
    cel_east = np.cross(cel_north, los)  # Richtung wachsender Rektaszension
    cel_east /= np.linalg.norm(cel_east)
    pa = math.degrees(math.atan2(pole @ cel_east, pole @ cel_north)) % 360

    diameter = 2 * math.degrees(math.asin(MOON_RADIUS_KM / dist)) * 3600
    return MoonView(lib_lon, lib_lat, sun_lon, sun_lat, pa, diameter, dist, v, s)
