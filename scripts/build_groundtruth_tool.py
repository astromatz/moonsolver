"""Erzeugt tools/groundtruth.html aus der Vorlage und data/gazetteer_moon.csv.

    python scripts/build_groundtruth_tool.py

Die Seite laeuft offline im Browser. Fotos werden nur lokal gelesen.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GAZ = ROOT / "data" / "gazetteer_moon.csv"
TEMPLATE = ROOT / "tools" / "groundtruth_template.html"
OUT = ROOT / "tools" / "groundtruth.html"

TYPE_LABEL = {"AA": "Krater", "SF": "Satellitenkrater"}


def main() -> int:
    if not GAZ.exists():
        print("data/gazetteer_moon.csv fehlt. Erst: python scripts/fetch_data.py --only gazetteer")
        return 1
    with open(GAZ, encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    # Krater zuerst, grosse vor kleinen: dann stehen die ueblichen Namen oben in der Auswahl
    rows.sort(key=lambda r: (r["code"] not in ("AA", "SF"), -float(r["diameter_km"])))
    entries = [[r["name"], TYPE_LABEL.get(r["code"], r["type"].split(",")[0]), round(float(r["diameter_km"]))]
               for r in rows]
    html = TEMPLATE.read_text(encoding="utf-8")
    html = html.replace("/*GAZETTEER*/[]", json.dumps(entries, ensure_ascii=False, separators=(",", ":")))
    OUT.write_text(html, encoding="utf-8")
    print(f"{OUT.relative_to(ROOT)}: {len(entries)} Namen")
    return 0


if __name__ == "__main__":
    sys.exit(main())
