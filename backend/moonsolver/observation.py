"""Eingabedaten einer Aufnahme. Zeit und Ort sind in Phase 1 Pflicht."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Observation:
    time_utc: datetime
    latitude_deg: float
    longitude_deg: float
    elevation_m: float = 0.0

    def __post_init__(self) -> None:
        if self.time_utc.tzinfo is None:
            raise ValueError("time_utc braucht eine Zeitzone (UTC)")
        if not -90.0 <= self.latitude_deg <= 90.0:
            raise ValueError("latitude_deg ausserhalb von -90..90")
        if not -180.0 <= self.longitude_deg <= 180.0:
            raise ValueError("longitude_deg ausserhalb von -180..180")
