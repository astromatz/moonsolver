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
| #1, #2, #4 (mit Mondrand) | getroffen, Fehler 0,4–0,7 % des Radius, ca. 1 Min. |
| #3 (Panorama mit Teilrand) | getroffen, 0,14 %, ca. 3,5 Min. |
| #1a (Ausschnitt ohne Rand) | getroffen, 0,25 %, ca. 2,5 Min. |
| #3b (Hochland-Ausschnitt) | getroffen, 0,10 %, ca. 3,5 Min. |
| #3a (Tycho-Ausschnitt) | nicht gefunden (falsch gespiegelt), API meldet `reliable: false` |

Der Abgleich vergleicht Kantenstärke (Kraterränder, Schattenkanten) statt Helligkeit; `MOONSOLVER_FEATURE=gray` schaltet auf den alten Helligkeitsvergleich zurück. `scripts/make_crops.py` erzeugt 98 randlose Testausschnitte mit bekannter Lösung und misst sie mit `--eval` (Helligkeitsvergleich: 61/98, Hochland 3/16; mit Kanten Hochland-Stichprobe 4/8 statt 1/8, vollständig nicht gemessen).

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
