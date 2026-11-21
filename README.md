# Moonsolver

Web-App, die auf Mondfotos benannte Krater erkennt und beschriftet, auch wenn der Mondrand nicht oder nur teilweise im Bild ist. Hauptszenarien: DSLR mit Teleobjektiv und Teleskop mit Astrokamera.

Ansatz (Phase 1): Aus Aufnahmezeit und Standort wird die Mondansicht berechnet (Libration, Sonnenstand) und gerendert. Das Foto wird dagegen ausgerichtet (Ausschnitt, Skala, Drehung, Spiegelung), danach werden Namen aus dem IAU/USGS-Gazetteer eingeblendet. Zeitangabe ist in Phase 1 Pflicht, gerechnet wird im Python-Backend.

## Struktur

| Pfad | Inhalt |
| --- | --- |
| `backend/moonsolver/` | FastAPI-Backend und Rechenmodule |
| `backend/moonsolver/static/` | Weboberfläche (wird unter `/` ausgeliefert) |
| `scripts/fetch_data.py` | Lädt Ephemeriden, Gazetteer und Mondkarten nach `data/` |
| `data/` | Heruntergeladene Daten (nicht im Repo) |
| `testset/` | Testfotos mit Zeit, Ort und Ground Truth |
| `tests/` | Tests |

## Stand

`scripts/evaluate.py` misst am Testset (Ziel: Median-Fehler < 1 % des Mondradius):

| Bild | Ergebnis |
| --- | --- |
| #1, #2, #3, #4 (mit Mondrand) | getroffen, Fehler 0,1–0,8 % des Radius, ca. 1 Min. |
| #1a (Ausschnitt ohne Rand) | getroffen, 0,35 %, ca. 3 Min. |
| #3a, #3b (Hochland-Ausschnitte) | nicht gefunden, Score ≤ 0,70, API meldet `reliable: false` |

Ein beschriftetes Bild erzeugt `scripts/annotate.py FOTO ZEIT_UTC BREITE LAENGE`.

## Loslegen

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python scripts/fetch_data.py        # Daten laden, siehe Hinweise im Skript
uvicorn moonsolver.api:app --reload
pytest
```

Danach `http://localhost:8000` öffnen: Foto hineinziehen, Aufnahmezeit (Ortszeit oder UTC) und Standort eintragen, „Krater erkennen“. Das beschriftete Bild lässt sich als PNG speichern. Der Regler „Kleinste Krater“ filtert ohne neue Rechnung.
