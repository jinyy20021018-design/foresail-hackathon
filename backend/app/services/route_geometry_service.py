import json
import math
from functools import lru_cache
from pathlib import Path

from app.services.port_registry_service import PortRecord, resolve_port

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "maritime_routes.json"

CHOKEPOINTS: dict[str, tuple[float, float]] = {
    "malacca": (1.3, 103.8),
    "singapore": (1.2644, 103.822),
    "suez": (30.0, 32.3),
    "gibraltar": (36.0, -5.5),
    "panama": (9.0, -79.5),
    "hormuz": (26.5, 56.5),
    "bab_el_mandeb": (12.5, 43.3),
    "cape_of_good_hope": (-34.5, 18.0),
    "taiwan_strait": (24.5, 119.0),
}


@lru_cache(maxsize=1)
def load_maritime_routes() -> dict:
    with DATA_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def build_route_geometry(
    origin_name: str,
    destination_name: str,
    final_destination_name: str | None = None,
) -> dict:
    warnings: list[str] = []
    origin = resolve_port(origin_name)
    destination = resolve_port(destination_name)
    final_destination = resolve_port(final_destination_name) if final_destination_name else None

    if not origin:
        warnings.append(f"Origin port not recognized: {origin_name}")
    if not destination:
        warnings.append(f"Destination port not recognized: {destination_name}")

    if not origin or not destination:
        return _empty_geometry(origin_name, destination_name, warnings)

    route_key = f"{_route_key(origin)}-{_route_key(destination)}"
    reverse_key = f"{_route_key(destination)}-{_route_key(origin)}"
    stored = load_maritime_routes().get(route_key) or load_maritime_routes().get(reverse_key)

    if stored:
        coordinates = stored["coordinates"]
        source = stored.get("source", "lane_network")
        distance = stored.get("distance_nautical_miles", _estimate_distance_nm(coordinates))
        confidence = "high"
    else:
        coordinates = _heuristic_route(origin, destination)
        source = "heuristic_lane"
        distance = _estimate_distance_nm(coordinates)
        confidence = "estimated"
        warnings.append("Route estimated from shipping-lane heuristics; not a surveyed passage.")

    legs: list[dict] = [{"type": "sea", "coordinates": coordinates}]

    inland_destination = final_destination
    if inland_destination and inland_destination["unlocode"] != destination["unlocode"]:
        inland_coords = [
            [destination["lat"], destination["lng"]],
            [inland_destination["lat"], inland_destination["lng"]],
        ]
        legs.append({"type": "inland", "coordinates": inland_coords})
        warnings.append(
            f"Inland segment shown from {destination['name']} to {inland_destination['name']} (illustrative)."
        )

    return {
        "origin": _port_payload(origin, origin_name),
        "destination": _port_payload(destination, destination_name),
        "final_destination": _port_payload(inland_destination, final_destination_name) if inland_destination else None,
        "coordinates": coordinates,
        "distance_nautical_miles": distance,
        "source": source,
        "confidence": confidence,
        "legs": legs,
        "warnings": warnings,
    }


def _route_key(record: PortRecord) -> str:
    return record["name"].lower().replace(" ", "-")


def _port_payload(record: PortRecord, input_name: str) -> dict:
    return {
        "name": input_name,
        "display_name": record["name"],
        "unlocode": record["unlocode"],
        "lat": record["lat"],
        "lng": record["lng"],
        "region": record["region"],
    }


def _empty_geometry(origin_name: str, destination_name: str, warnings: list[str]) -> dict:
    return {
        "origin": {"name": origin_name, "display_name": origin_name, "unlocode": None, "lat": None, "lng": None, "region": None},
        "destination": {"name": destination_name, "display_name": destination_name, "unlocode": None, "lat": None, "lng": None, "region": None},
        "final_destination": None,
        "coordinates": [],
        "distance_nautical_miles": 0,
        "source": "unresolved",
        "confidence": "none",
        "legs": [],
        "warnings": warnings,
    }


def _heuristic_route(origin: PortRecord, destination: PortRecord) -> list[list[float]]:
    start = (origin["lat"], origin["lng"])
    end = (destination["lat"], destination["lng"])
    waypoints: list[tuple[float, float]] = [start]

    if _needs_malacca(start, end):
        waypoints.extend([CHOKEPOINTS["taiwan_strait"], CHOKEPOINTS["malacca"], CHOKEPOINTS["singapore"]])

    if _needs_hormuz(start, end):
        waypoints.extend([
            (6.0, 87.0),
            (5.5, 84.0),
            (6.5, 78.5),
            (10.5, 71.5),
            (16.5, 65.5),
            (22.0, 60.0),
            CHOKEPOINTS["hormuz"],
        ])

    if _needs_suez(start, end):
        waypoints.extend([CHOKEPOINTS["hormuz"], CHOKEPOINTS["bab_el_mandeb"], CHOKEPOINTS["suez"]])

    if _needs_panama(start, end):
        waypoints.append(CHOKEPOINTS["panama"])

    if _needs_cape_route(start, end):
        waypoints.extend([CHOKEPOINTS["cape_of_good_hope"]])

    if _needs_gibraltar(start, end):
        waypoints.append(CHOKEPOINTS["gibraltar"])

    waypoints.append(end)
    return [[lat, lng] for lat, lng in _dedupe_points(waypoints)]


def _needs_malacca(start: tuple[float, float], end: tuple[float, float]) -> bool:
    east_asia_origin = start[1] > 100
    westbound = end[1] < start[1]
    indian_ocean_dest = 45 <= end[1] <= 130
    return east_asia_origin and westbound and indian_ocean_dest and abs(end[0] - start[0]) < 35


def _needs_hormuz(start: tuple[float, float], end: tuple[float, float]) -> bool:
    east_asia_origin = start[1] > 100
    persian_gulf = 45 <= end[1] <= 62 and 20 <= end[0] <= 30
    return east_asia_origin and persian_gulf


def _needs_suez(start: tuple[float, float], end: tuple[float, float]) -> bool:
    east_asia = start[1] > 90 and end[1] > -10
    europe = end[1] > -10 and end[1] < 40
    return east_asia and europe and end[0] > 30


def _needs_panama(start: tuple[float, float], end: tuple[float, float]) -> bool:
    pacific = start[1] > 100 or end[1] > 100
    atlantic = start[1] < -30 or end[1] < -30
    americas = (start[1] < -60 and end[1] > 60) or (end[1] < -60 and start[1] > 60)
    return pacific and atlantic and americas


def _needs_cape_route(start: tuple[float, float], end: tuple[float, float]) -> bool:
    crosses_indian = start[1] > 60 and end[1] < -20
    crosses_atlantic = start[1] < -20 and end[1] > 60
    return crosses_indian or crosses_atlantic


def _needs_gibraltar(start: tuple[float, float], end: tuple[float, float]) -> bool:
    return start[1] > 0 and end[1] > -20 and end[1] < 20 and abs(end[0] - start[0]) > 20


def _dedupe_points(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    deduped: list[tuple[float, float]] = []
    for point in points:
        if not deduped or _distance_km(deduped[-1], point) > 25:
            deduped.append(point)
    return deduped


def _estimate_distance_nm(coordinates: list[list[float]]) -> int:
    if len(coordinates) < 2:
        return 0
    km = sum(_distance_km((coordinates[index][0], coordinates[index][1]), (coordinates[index + 1][0], coordinates[index + 1][1])) for index in range(len(coordinates) - 1))
    return int(round(km / 1.852))


def _distance_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371 * 2 * math.asin(min(1, math.sqrt(h)))
