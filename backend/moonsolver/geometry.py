"""Mondgeometrie fuer eine Aufnahme (Meilenstein M1).

Liefern soll das Modul: optische Libration (selenografische Laenge/Breite des
Scheibenmittelpunkts), subsolaren Punkt, Positionswinkel der Mondachse,
scheinbaren Durchmesser. Grundlage: Skyfield mit de421.bsp und den
NAIF-Mondkernen aus data/ (siehe scripts/fetch_data.py).
"""

from __future__ import annotations

from dataclasses import dataclass

from .observation import Observation


@dataclass(frozen=True)
class MoonView:
    libration_lon_deg: float
    libration_lat_deg: float
    subsolar_lon_deg: float
    subsolar_lat_deg: float
    axis_position_angle_deg: float
    apparent_diameter_arcsec: float


def moon_view(obs: Observation) -> MoonView:
    raise NotImplementedError("M1: Geometrie aus Ephemeriden berechnen")
