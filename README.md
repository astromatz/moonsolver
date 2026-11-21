# Moonsolver

Web-App, die auf Mondfotos benannte Krater erkennt und beschriftet, auch wenn der Mondrand nicht oder nur teilweise im Bild ist. Hauptszenarien: DSLR mit Teleobjektiv und Teleskop mit Astrokamera.

Ansatz (Phase 1): Aus Aufnahmezeit und Standort wird die Mondansicht berechnet (Libration, Sonnenstand) und gerendert. Das Foto wird dagegen ausgerichtet (Ausschnitt, Skala, Drehung, Spiegelung), danach werden Namen aus dem IAU/USGS-Gazetteer eingeblendet. Zeitangabe ist in Phase 1 Pflicht, gerechnet wird im Python-Backend.

## Struktur

| Pfad | Inhalt |
| --- | --- |
| `backend/moonsolver/` | FastAPI-Backend und Rechenmodule |
| `scripts/fetch_data.py` | Lädt Ephemeriden, Gazetteer und Mondkarten nach `data/` |
| `data/` | Heruntergeladene Daten (nicht im Repo) |
| `testset/` | Testfotos mit Zeit, Ort und Ground Truth |
| `tests/` | Tests |

## Loslegen

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python scripts/fetch_data.py        # Daten laden, siehe Hinweise im Skript
uvicorn moonsolver.api:app --reload
pytest
```
