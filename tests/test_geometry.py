"""Geometrie und Projektion. Braucht data/ (scripts/fetch_data.py), sonst uebersprungen."""

from datetime import datetime, timezone

import numpy as np
import pytest

from moonsolver.data import DATA

pytestmark = pytest.mark.skipif(not (DATA / "de421.bsp").exists(), reason="data/ fehlt")


def _view(t):
    from moonsolver.geometry import moon_view
    from moonsolver.observation import Observation

    return moon_view(Observation(t, 50.9375, 6.9603))


def test_first_quarter_sun_east():
    # 20.04.2021 erstes Viertel: Sonne steht ueber ca. 75-90 Grad Ost
    v = _view(datetime(2021, 4, 20, 20, tzinfo=timezone.utc))
    assert 60 < v.subsolar_lon_deg < 100
    assert abs(v.libration_lon_deg) < 8.5 and abs(v.libration_lat_deg) < 7.5
    assert 1750 < v.apparent_diameter_arcsec < 2050


def test_project_unproject_roundtrip():
    from moonsolver.render import Frame

    v = _view(datetime(2022, 11, 11, 21, 41, tzinfo=timezone.utc))
    fr = Frame(v, 500.0, 500.0, 400.0)
    lat, lon = np.array([-43.3, 9.6, 0.0]), np.array([348.8, 339.9, 0.0])
    x, y, vis = fr.project(lat, lon)
    assert vis.all()
    s = fr.unproject(x, y)
    lat2 = np.degrees(np.arcsin(s[:, 2]))
    lon2 = np.degrees(np.arctan2(s[:, 1], s[:, 0])) % 360
    assert np.allclose(lat2, lat, atol=1e-6)
    assert np.allclose((lon2 - lon + 180) % 360 - 180, 0, atol=1e-6)
