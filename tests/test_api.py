from fastapi.testclient import TestClient

from moonsolver.api import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def _post(time_utc, lat=51.0):
    return client.post(
        "/solve",
        files={"image": ("m.png", b"x", "image/png")},
        data={"time_utc": time_utc, "latitude_deg": lat, "longitude_deg": 10.0},
    )


def test_solve_requires_timezone():
    assert _post("2026-11-21T20:00:00").status_code == 422


def test_solve_rejects_bad_latitude():
    assert _post("2026-11-21T20:00:00Z", lat=95).status_code == 422


def test_solve_not_implemented_yet():
    assert _post("2026-11-21T20:00:00Z").status_code == 501
