"""HTTP-Schnittstelle."""

from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path

import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from PIL import Image, UnidentifiedImageError

from .observation import Observation

STATIC = Path(__file__).parent / "static"

app = FastAPI(title="Moonsolver")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def _run(photo: np.ndarray, obs: Observation, min_diameter_px: float) -> dict:
    from .geometry import moon_view
    from .solve import RELIABLE_SCORE, labels, solve

    view = moon_view(obs)
    sol = solve(photo, view)
    h, w = photo.shape[:2]
    return {
        "solution": {
            "rotation_deg": sol.theta_deg % 360,
            "mirrored": sol.mirror,
            "moon_radius_px": sol.radius_px,
            "moon_center_px": [sol.center_x, sol.center_y],
            "score": sol.score,
            # Schwelle siehe solve.RELIABLE_SCORE (haengt vom Vergleichsmerkmal ab)
            "reliable": sol.score >= RELIABLE_SCORE,
        },
        "view": {
            "libration_lon_deg": view.libration_lon_deg,
            "libration_lat_deg": view.libration_lat_deg,
            "subsolar_lon_deg": view.subsolar_lon_deg,
            "subsolar_lat_deg": view.subsolar_lat_deg,
            "axis_position_angle_deg": view.axis_position_angle_deg,
        },
        "labels": [
            {"name": lb.name, "x": lb.x, "y": lb.y, "diameter_px": lb.diameter_px}
            for lb in labels(sol, view, w, h, min_diameter_px=min_diameter_px)
        ],
    }


@app.post("/solve")
async def solve_endpoint(
    image: UploadFile = File(...),
    time_utc: datetime = Form(...),
    latitude_deg: float = Form(...),
    longitude_deg: float = Form(...),
    min_diameter_px: float = Form(12.0),
) -> dict:
    try:
        obs = Observation(time_utc, latitude_deg, longitude_deg)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        photo = np.asarray(Image.open(io.BytesIO(await image.read())).convert("RGB"))
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(status_code=422, detail="Bild nicht lesbar") from exc
    return await run_in_threadpool(_run, photo, obs, min_diameter_px)
