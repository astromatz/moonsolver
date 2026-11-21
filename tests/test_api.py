from fastapi.testclient import TestClient

from moonsolver.api import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_index_serves_page():
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert 'id="drop"' in r.text


def _post(time_utc, lat=51.0, image=b"x"):
    return client.post(
        "/solve",
        files={"image": ("m.png", image, "image/png")},
        data={"time_utc": time_utc, "latitude_deg": lat, "longitude_deg": 10.0},
    )


def test_solve_requires_timezone():
    assert _post("2026-11-21T20:00:00").status_code == 422


def test_solve_rejects_bad_latitude():
    assert _post("2026-11-21T20:00:00Z", lat=95).status_code == 422


def test_solve_rejects_unreadable_image():
    r = _post("2026-11-21T20:00:00Z")
    assert r.status_code == 422
    assert "Bild" in r.json()["detail"]
