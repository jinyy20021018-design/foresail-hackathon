from app.services.port_registry_service import resolve_port

DEFAULT_WATCHED_REGIONS = [
    "East China Sea",
    "South China Sea",
    "Bay of Bengal",
    "Bangladesh",
]

CORRIDOR_ALIASES: dict[str, list[str]] = {
    "strait of hormuz": ["hormuz", "persian gulf", "gulf of oman"],
    "persian gulf": ["hormuz", "persian gulf", "gulf of oman", "jebel ali"],
    "indian ocean": ["indian ocean", "arabian sea"],
    "strait of malacca": ["malacca", "singapore strait"],
    "bay of bengal": ["bay of bengal", "chittagong", "bangladesh"],
    "east china sea": ["east china sea", "shanghai"],
    "south china sea": ["south china sea"],
}


def regions_from_route(route: str | None) -> list[str]:
    if not route:
        return []
    text = str(route).strip()
    if not text or text.upper() == "TBD":
        return []
    normalized = text.replace("→", "->")
    return list(dict.fromkeys(part.strip() for part in normalized.split("->") if part.strip()))


def merge_watched_route_regions(case: dict) -> list[str]:
    regions: list[str] = []
    regions.extend(regions_from_route(case.get("route")))
    for port_name in (
        case.get("port_of_loading"),
        case.get("port_of_discharge"),
        case.get("final_destination"),
    ):
        if not port_name or str(port_name).strip().upper() == "TBD":
            continue
        regions.append(str(port_name).strip())
        record = resolve_port(port_name)
        if record and record.get("region"):
            regions.append(record["region"])
    if not regions:
        regions.extend(DEFAULT_WATCHED_REGIONS)
    return list(dict.fromkeys(regions))


def event_text_mentions_corridor(event: dict, corridors: set[str]) -> bool:
    text = " ".join(
        str(event.get(key) or "")
        for key in ("title", "description", "affected_region", "impact")
    ).lower()
    for corridor in corridors:
        corridor_lower = corridor.lower()
        if corridor_lower in text:
            return True
        for alias in CORRIDOR_ALIASES.get(corridor_lower, []):
            if alias in text:
                return True
    return False
