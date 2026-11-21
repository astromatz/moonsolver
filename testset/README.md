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

Ground Truth: Für 5 Krater pro Foto die Pixelposition (x, y) in `groundtruth.csv` (`file,name,x,y`), abgelesen mit LTVT oder Virtual Moon Atlas.
