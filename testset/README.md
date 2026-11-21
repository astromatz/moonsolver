# Testset

Ziel M0: 10 Fotos, davon mindestens 3 ohne sichtbaren Mondrand, je eins pro Quelle (DSLR mit Tele, Teleskop mit Astrokamera).

Pro Foto ein Eintrag in `testset.csv`:

| Spalte | Bedeutung |
| --- | --- |
| `file` | Dateiname |
| `source` | `dslr` oder `astrocam` |
| `time_utc` | Aufnahmezeit, ISO 8601 mit `Z` |
| `lat_deg`, `lon_deg` | Standort |
| `limb_visible` | `yes`, `partial`, `no` |
| `time_uncertainty_min` | geschätzte Unsicherheit der Zeit in Minuten |
| `crop_of` | bei Ausschnitten: `Originaldatei@x+y` (linke obere Ecke im Original), sonst leer |

Ausschnitte (`#1a`, `#3a`, `#3b`) sind aus den Originalen geschnitten, um Fälle ohne Mondrand zu haben.

Herkunft der Zeiten (Ort für alle: Köln, 50.9375° N, 6.9603° O):
- `#3`: Dateiname `22_41_28`, als MEZ gelesen → 21:41:28 UTC. Ob die Aufnahmesoftware MEZ oder UTC schrieb, ist ungeprüft.
- `#1`, `#2`, `#4`: nur Datum im Dateinamen, kein EXIF. Zeit geschätzt aus Mondhöhe über Köln (Skyfield) und dem Dateidatum der bearbeiteten JPGs (#2: 23:21 MESZ, #4: 23:00 MESZ als Obergrenze; #1: Mond geht am 2.9.2022 gegen 20:30 UTC unter).

Ground Truth: Für 5 Krater pro Foto die Pixelposition (x, y) in `groundtruth.csv` (`file,name,x,y`), abgelesen mit LTVT oder Virtual Moon Atlas.
