"""Laedt die Daten fuer Phase 1 nach data/.

Hinweis: Die URLs sind noch nicht geprueft. Aus der Cloud-Sandbox sind die
Hosts nicht erreichbar, das Skript muss lokal laufen. Gazetteer, WAC-Mosaik
und DEM sind gross bzw. haben wechselnde Download-Pfade und sind deshalb
als manuelle Schritte beschrieben.
"""

from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"

FILES = {
    "de421.bsp": "https://ssd.jpl.nasa.gov/ftp/eph/planets/bsp/de421.bsp",
    "moon_pa_de421_1900-2050.bpc": "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/pck/moon_pa_de421_1900-2050.bpc",
    "moon_080317.tf": "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/fk/satellites/moon_080317.tf",
    "pck00008.tpc": "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/pck/pck00008.tpc",
}

MANUAL = """
Manuell nach data/ legen:
  gazetteer_moon.csv  IAU-Namen, Mond, Typ Krater/Mare/Mons/Rima, als CSV
                      exportiert von https://planetarynames.wr.usgs.gov/
  wac_albedo.tif      LROC WAC Global Mosaik, heruntergerechnet auf ca. 1 km/px
  dem.tif             LOLA- oder SLDEM2015-DEM, ca. 1 km/px
"""


def main() -> int:
    DATA.mkdir(exist_ok=True)
    failed = []
    for name, url in FILES.items():
        target = DATA / name
        if target.exists():
            print(f"vorhanden: {name}")
            continue
        print(f"lade {name} ...")
        try:
            urllib.request.urlretrieve(url, target)
        except OSError as exc:
            print(f"  fehlgeschlagen: {exc}")
            failed.append(name)
    print(MANUAL)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
