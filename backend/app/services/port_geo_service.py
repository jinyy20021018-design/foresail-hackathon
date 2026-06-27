PORT_COORDINATES = {
    "Shanghai": {"lat": 31.2304, "lon": 121.4737, "country": "China"},
    "Chittagong": {"lat": 22.3569, "lon": 91.7832, "country": "Bangladesh"},
    "Dhaka": {"lat": 23.8103, "lon": 90.4125, "country": "Bangladesh"},
    "Bay of Bengal": {"lat": 15.0, "lon": 88.0, "country": None},
    "Singapore": {"lat": 1.3521, "lon": 103.8198, "country": "Singapore"},
    "Rotterdam": {"lat": 51.9244, "lon": 4.4777, "country": "Netherlands"},
}


def resolve_location_coordinates(location_name: str) -> dict | None:
    if not location_name:
        return None
    normalized = location_name.strip().lower()
    for name, coordinate in PORT_COORDINATES.items():
        if name.lower() == normalized:
            return {"name": name, **coordinate}
    for name, coordinate in PORT_COORDINATES.items():
        if name.lower() in normalized or normalized in name.lower():
            return {"name": name, **coordinate}
    return None
