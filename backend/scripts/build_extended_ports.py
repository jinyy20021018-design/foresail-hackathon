"""Generate app/data/port_registry_extended.json from the open sea-ports dataset.

Usage:
    python scripts/build_extended_ports.py <path-to-sea-ports.json>

Source dataset: https://github.com/marchah/sea-ports (MIT), entries keyed by UN/LOCODE
with coordinates as [lon, lat].
"""

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.port_registry_service import REGION_COORDINATES

OUTPUT_PATH = Path(__file__).resolve().parents[1] / "app" / "data" / "port_registry_extended.json"
REGION_MATCH_RADIUS_KM = 1500


def main(source_path: str) -> None:
    with open(source_path, encoding="utf-8") as handle:
        raw = json.load(handle)

    records = []
    for unlocode, entry in raw.items():
        coordinates = entry.get("coordinates")
        if not coordinates or len(coordinates) < 2:
            continue
        lng, lat = float(coordinates[0]), float(coordinates[1])
        name = str(entry.get("name") or "").strip()
        if not name:
            continue
        aliases = {name.lower()}
        city = str(entry.get("city") or "").strip()
        if city and city.lower() != name.lower():
            aliases.add(city.lower())
        for alias in entry.get("alias") or []:
            aliases.add(str(alias).lower())
        records.append(
            {
                "unlocode": unlocode,
                "name": name,
                "country": entry.get("country") or "",
                "aliases": sorted(aliases),
                "lat": round(lat, 4),
                "lng": round(lng, 4),
                "region": _nearest_region(lat, lng),
            }
        )

    records.sort(key=lambda record: record["unlocode"])
    OUTPUT_PATH.write_text(json.dumps(records, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"Wrote {len(records)} ports to {OUTPUT_PATH}")


def _nearest_region(lat: float, lng: float) -> str:
    best_region = "Open Water"
    best_distance = REGION_MATCH_RADIUS_KM
    for region, (region_lat, region_lng) in REGION_COORDINATES.items():
        distance = _distance_km(lat, lng, region_lat, region_lng)
        if distance < best_distance:
            best_distance = distance
            best_region = region
    return best_region


def _distance_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    a, b = math.radians(lat1), math.radians(lat2)
    h = math.sin((b - a) / 2) ** 2 + math.cos(a) * math.cos(b) * math.sin(math.radians(lng2 - lng1) / 2) ** 2
    return 6371 * 2 * math.asin(min(1, math.sqrt(h)))


if __name__ == "__main__":
    main(sys.argv[1])
