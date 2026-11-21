Heruntergeladene Daten, nicht versioniert. Befüllen mit:

    pip install -e ".[data]"
    python scripts/fetch_data.py

Einzelne Schritte: `--only kernels,gazetteer,dem,wac`. Vor Downloads über 100 MB fragt das Skript nach (`--yes` überspringt das).

| Datei | Quelle | Download |
| --- | --- | --- |
| `de421.bsp`, `moon_pa_de421_1900-2050.bpc`, `moon_080317.tf`, `pck00008.tpc` | JPL/NAIF | 19 MB |
| `gazetteer_moon.csv` | USGS Planetary Nomenclature, nur „Adopted by IAU“ | 23 MB |
| `dem.tif` | LOLA LDEM_64, auf 32 px/Grad gemittelt, Höhe in m | 531 MB |
| `wac_albedo.tif` | LROC WAC Global Mosaik 100 m, jede ~9. Zeile per HTTP-Range | ca. 630 MB |

`dem.tif` und `wac_albedo.tif` teilen ein Raster: 11520 × 5760 px, 32 px/Grad, Länge 0–360° Ost ab Spalte 0, Zeile 0 = +90° Breite. `gazetteer_moon.csv` nutzt dieselbe Längenkonvention (`lon_east_deg`).
