from dataclasses import asdict, dataclass


@dataclass
class LocationCoordinate:
    name: str
    lat: float
    lon: float
    country: str | None = None


_LOCATIONS = {
    "shanghai": LocationCoordinate("Shanghai", 31.2304, 121.4737, "China"),
    "chittagong": LocationCoordinate("Chittagong", 22.3569, 91.7832, "Bangladesh"),
    "dhaka": LocationCoordinate("Dhaka", 23.8103, 90.4125, "Bangladesh"),
    "bay of bengal": LocationCoordinate("Bay of Bengal", 15.0, 88.0, None),
    "east china sea": LocationCoordinate("East China Sea", 29.0, 125.0, None),
    "south china sea": LocationCoordinate("South China Sea", 12.0, 115.0, None),
    "singapore": LocationCoordinate("Singapore", 1.3521, 103.8198, "Singapore"),
    "rotterdam": LocationCoordinate("Rotterdam", 51.9244, 4.4777, "Netherlands"),
}


def resolve_location_coordinates(location_name: str) -> dict | None:
    if not location_name:
        return None
    coordinate = _LOCATIONS.get(str(location_name).strip().lower())
    return asdict(coordinate) if coordinate else None
