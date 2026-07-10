import math
from datetime import date, timedelta

from app.services.port_registry_service import REGION_COORDINATES
from app.services.route_geometry_service import build_route_geometry

REGION_MATCH_RADIUS_KM = 600


def build_voyage_schedule(case: dict) -> dict:
    etd = _parse_date(case.get("etd"))
    eta = _parse_date(case.get("eta"))
    warnings: list[str] = []
    if not etd or not eta or eta <= etd:
        return {"positions": [], "etd": case.get("etd"), "eta": case.get("eta"), "warnings": ["Voyage schedule requires valid ETD and ETA."]}

    geometry = build_route_geometry(
        case.get("port_of_loading") or "",
        case.get("port_of_discharge") or case.get("final_destination") or "",
        case.get("final_destination"),
    )
    coordinates = geometry.get("coordinates") or []
    if len(coordinates) < 2:
        return {"positions": [], "etd": str(etd), "eta": str(eta), "warnings": [*geometry.get("warnings", []), "Route geometry unavailable; voyage schedule not built."]}

    cumulative = [0.0]
    for index in range(1, len(coordinates)):
        cumulative.append(cumulative[-1] + _distance_km(coordinates[index - 1], coordinates[index]))
    total_km = cumulative[-1] or 1.0
    voyage_days = (eta - etd).days

    positions: list[dict] = []
    for day_offset in range(voyage_days + 1):
        fraction = day_offset / voyage_days if voyage_days else 0.0
        lat, lng = _point_at_fraction(coordinates, cumulative, fraction * total_km)
        positions.append(
            {
                "day_offset": day_offset,
                "date": (etd + timedelta(days=day_offset)).isoformat(),
                "lat": round(lat, 3),
                "lng": round(lng, 3),
                "region": _nearest_region(lat, lng),
            }
        )

    return {
        "positions": positions,
        "etd": str(etd),
        "eta": str(eta),
        "total_distance_km": round(total_km),
        "warnings": [*geometry.get("warnings", [])],
    }


def position_on(schedule: dict, target: date) -> dict | None:
    for position in schedule.get("positions", []):
        if position["date"] == target.isoformat():
            return position
    return None


def region_transit_windows(schedule: dict) -> list[dict]:
    windows: list[dict] = []
    for position in schedule.get("positions", []):
        region = position["region"]
        if windows and windows[-1]["region"] == region:
            windows[-1]["end"] = position["date"]
        else:
            windows.append({"region": region, "start": position["date"], "end": position["date"]})
    return windows


def _point_at_fraction(coordinates: list, cumulative: list[float], target_km: float) -> tuple[float, float]:
    if target_km <= 0:
        return coordinates[0][0], coordinates[0][1]
    if target_km >= cumulative[-1]:
        return coordinates[-1][0], coordinates[-1][1]
    for index in range(1, len(cumulative)):
        if cumulative[index] >= target_km:
            segment = cumulative[index] - cumulative[index - 1] or 1.0
            ratio = (target_km - cumulative[index - 1]) / segment
            lat = coordinates[index - 1][0] + ratio * (coordinates[index][0] - coordinates[index - 1][0])
            lng = coordinates[index - 1][1] + ratio * (coordinates[index][1] - coordinates[index - 1][1])
            return lat, lng
    return coordinates[-1][0], coordinates[-1][1]


def _nearest_region(lat: float, lng: float) -> str:
    best_region = "Open Water"
    best_distance = REGION_MATCH_RADIUS_KM
    for region, (region_lat, region_lng) in REGION_COORDINATES.items():
        distance = _distance_km([lat, lng], [region_lat, region_lng])
        if distance < best_distance:
            best_distance = distance
            best_region = region
    return best_region


def _distance_km(a, b) -> float:
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371 * 2 * math.asin(min(1, math.sqrt(h)))


def _parse_date(value) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        return None
