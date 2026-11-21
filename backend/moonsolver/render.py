"""Rendert die Mondansicht fuer eine MoonView.

Bildkoordinaten: Mond-Nord oben, Ost rechts (wie im Atlas), Scheibenmitte bei
(cx, cy), scheinbarer Radius r Pixel. Perspektive mit endlicher Entfernung,
damit der Rand auch bei grossen Bildern auf wenige Pixel stimmt.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.ndimage import map_coordinates

from .data import MOON_RADIUS_KM, PPD, maps
from .geometry import MoonView


@dataclass(frozen=True)
class Frame:
    """Abbildung Mondkugel <-> Renderpixel."""

    view: MoonView
    cx: float
    cy: float
    r: float

    @property
    def d(self) -> float:  # Entfernung in Mondradien
        return self.view.distance_km / MOON_RADIUS_KM

    def project(self, lat_deg, lon_deg):
        """Selenografische Koordinaten -> (x, y, sichtbar)."""
        lat, lon = np.radians(lat_deg), np.radians(lon_deg)
        s = np.stack([np.cos(lat) * np.cos(lon), np.cos(lat) * np.sin(lon), np.sin(lat)], axis=-1)
        e, n, v = self.view.basis()
        d = self.d
        depth = d - s @ v
        k = np.sqrt(d * d - 1) * self.r
        x = self.cx + k * (s @ e) / depth
        y = self.cy - k * (s @ n) / depth
        return x, y, (s @ v) > 1 / d

    def unproject(self, x, y):
        """Renderpixel -> Einheitsvektor auf der Kugel (NaN ausserhalb der Scheibe)."""
        e, n, v = self.view.basis()
        d = self.d
        k = np.sqrt(d * d - 1) * self.r
        a = (np.asarray(x, float) - self.cx) / k
        b = (self.cy - np.asarray(y, float)) / k
        # Strahl vom Beobachter P = d*v in Richtung -(v - a*e - b*n)
        ray = -v[None] + a[..., None] * e + b[..., None] * n
        ray /= np.linalg.norm(ray, axis=-1, keepdims=True)
        p = d * v
        bq = ray @ p
        disc = bq * bq - (d * d - 1)
        t = -bq - np.sqrt(np.where(disc >= 0, disc, np.nan))
        return p + t[..., None] * ray


def _sample(grid: np.ndarray, lat, lon):
    row = (90 - lat) * PPD - 0.5
    col = (lon % 360) * PPD - 0.5
    return map_coordinates(grid, [row, col], order=1, mode="grid-wrap")


def render(view: MoonView, radius_px: float, *, albedo_weight: float = 1.0, margin: float = 1.05) -> tuple[np.ndarray, Frame]:
    """Helligkeit 0..1 (Weltraum = 0). Gibt Bild und Frame zurueck."""
    size = int(np.ceil(2 * radius_px * margin)) | 1
    c = (size - 1) / 2
    frame = Frame(view, c, c, radius_px)
    yy, xx = np.mgrid[0:size, 0:size]
    s = frame.unproject(xx.ravel(), yy.ravel())
    ok = np.isfinite(s[:, 0])
    s = s[ok]
    lat = np.degrees(np.arcsin(np.clip(s[:, 2], -1, 1)))
    lon = np.degrees(np.arctan2(s[:, 1], s[:, 0]))

    dem, wac = maps()
    # Neigung aus dem DEM: Hoehendifferenzen ueber je ein Rasterpixel in Ost und Nord
    step = 1.0 / PPD
    m_per_deg = np.radians(1) * MOON_RADIUS_KM * 1000
    coslat = np.maximum(np.cos(np.radians(lat)), 0.05)
    dz_e = (_sample(dem, lat, lon + step) - _sample(dem, lat, lon - step)) / (2 * step * m_per_deg * coslat)
    dz_n = (_sample(dem, lat + step, lon) - _sample(dem, lat - step, lon)) / (2 * step * m_per_deg)

    up = s
    east = np.stack([-np.sin(np.radians(lon)), np.cos(np.radians(lon)), np.zeros_like(lon)], axis=-1)
    north = np.cross(up, east)
    normal = up - dz_e[:, None] * east - dz_n[:, None] * north
    normal /= np.linalg.norm(normal, axis=-1, keepdims=True)

    mu0 = np.clip(normal @ view.sun_dir, 0, None)
    to_obs = view.observer_dir * frame.d - s
    to_obs /= np.linalg.norm(to_obs, axis=-1, keepdims=True)
    mu = np.clip(normal @ to_obs.T if to_obs.ndim == 1 else np.einsum("ij,ij->i", normal, to_obs), 1e-3, None)
    shade = mu0 / (mu0 + mu)  # Lommel-Seeliger
    # Schatten der Kugel selbst: Punkte hinter dem Terminator bleiben dunkel
    shade *= (up @ view.sun_dir) > -0.02

    albedo = _sample(wac, lat, lon)
    bright = shade * (albedo ** albedo_weight)

    img = np.zeros(size * size, np.float32)
    img[np.flatnonzero(ok)] = bright
    img = img.reshape(size, size)
    return img / max(float(img.max()), 1e-6), frame
