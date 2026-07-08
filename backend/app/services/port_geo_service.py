from dataclasses import asdict, dataclass

from app.services.port_registry_service import resolve_port, resolve_region_coordinates


@dataclass
class LocationCoordinate:
    name: str
    lat: float
    lon: float
    country: str | None = None


_LEGACY_LOCATIONS = {
    "bay of bengal": LocationCoordinate("Bay of Bengal", 15.0, 88.0, None),
    "east china sea": LocationCoordinate("East China Sea", 29.0, 125.0, None),
    "south china sea": LocationCoordinate("South China Sea", 12.0, 115.0, None),
}


def resolve_location_coordinates(location_name: str) -> dict | None:
    if not location_name:
        return None

    record = resolve_port(location_name)
    if record:
        return asdict(
            LocationCoordinate(
                name=record["name"],
                lat=record["lat"],
                lon=record["lng"],
                country=None,
            )
        )

    legacy = _LEGACY_LOCATIONS.get(str(location_name).strip().lower())
    if legacy:
        return asdict(legacy)

    region_coords = resolve_region_coordinates(location_name)
    if region_coords:
        return asdict(
            LocationCoordinate(
                name=str(location_name).strip(),
                lat=region_coords[0],
                lon=region_coords[1],
                country=None,
            )
        )

    return None
