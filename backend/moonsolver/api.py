"""HTTP-Schnittstelle."""

from __future__ import annotations

from datetime import datetime

from fastapi import FastAPI, File, Form, HTTPException, UploadFile

from .observation import Observation

app = FastAPI(title="Moonsolver")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/solve")
async def solve(
    image: UploadFile = File(...),
    time_utc: datetime = Form(...),
    latitude_deg: float = Form(...),
    longitude_deg: float = Form(...),
) -> dict:
    try:
        Observation(time_utc, latitude_deg, longitude_deg)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    raise HTTPException(status_code=501, detail="Abgleich noch nicht implementiert (M2)")
