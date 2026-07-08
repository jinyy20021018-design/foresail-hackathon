from app.services.case_service import get_case, get_relevance_results
from app.services.event_ingestion_service import list_external_events
from app.services.port_registry_service import resolve_port, resolve_region_coordinates
from app.services.route_geometry_service import build_route_geometry


def build_route_map(case_id: str) -> dict:
    case = get_case(case_id)
    geometry = build_route_geometry(
        case.get("port_of_loading") or "",
        case.get("port_of_discharge") or case.get("final_destination") or "",
        case.get("final_destination"),
    )

    relevance_results = _safe_relevance_results(case_id)
    external_events = {event["event_id"]: event for event in list_external_events(case_id)}
    map_events = _build_map_events(relevance_results, external_events)

    primary_threat = next((event for event in map_events if event["classification"] == "Relevant"), None)
    watch_events = [event for event in map_events if event["classification"] == "Watch"]

    return {
        "case_id": case_id,
        "geometry": geometry,
        "ports": {
            "loading": geometry.get("origin"),
            "discharge": geometry.get("destination"),
            "final_destination": geometry.get("final_destination"),
        },
        "map_events": map_events,
        "threat_summary": {
            "primary_threat": primary_threat,
            "watch_count": len(watch_events),
            "has_route_threats": bool(map_events),
            "neutral_message": None if map_events else "No route-level threats detected for the current monitoring cycle.",
        },
        "meta": {
            "source": geometry.get("source"),
            "confidence": geometry.get("confidence"),
            "warnings": geometry.get("warnings", []),
            "distance_nautical_miles": geometry.get("distance_nautical_miles"),
        },
    }


def _safe_relevance_results(case_id: str) -> list[dict]:
    try:
        return get_relevance_results(case_id)
    except KeyError:
        return []


def _build_map_events(relevance_results: list[dict], external_events: dict[str, dict]) -> list[dict]:
    map_events: list[dict] = []

    for result in relevance_results:
        classification = result.get("classification")
        if classification not in {"Relevant", "Watch"}:
            continue

        event = external_events.get(result.get("event_id", ""), {})
        coordinates = _resolve_event_coordinates(event, result)
        if not coordinates:
            continue

        map_events.append(
            {
                "event_id": result.get("event_id"),
                "title": result.get("title") or event.get("title") or "External event",
                "classification": classification,
                "event_type": result.get("event_type") or event.get("event_type") or event.get("type"),
                "lat": coordinates[0],
                "lng": coordinates[1],
                "source": event.get("source"),
            }
        )

    return map_events


def _resolve_event_coordinates(event: dict, relevance: dict) -> tuple[float, float] | None:
    for port_name in event.get("affected_ports") or []:
        record = resolve_port(port_name)
        if record:
            return record["lat"], record["lng"]

    for location in event.get("locations") or []:
        record = resolve_port(location)
        if record:
            return record["lat"], record["lng"]

    region = event.get("affected_region") or event.get("affected_routes")
    if isinstance(region, list):
        region = region[0] if region else None
    coordinates = resolve_region_coordinates(region if isinstance(region, str) else None)
    if coordinates:
        return coordinates

    title = (relevance.get("title") or event.get("title") or "").lower()
    if "shanghai" in title or "east china" in title:
        return resolve_region_coordinates("East China Sea")
    if "chittagong" in title or "chattogram" in title or "bangladesh" in title:
        return resolve_region_coordinates("Bangladesh")
    if "typhoon" in title:
        return resolve_region_coordinates("East China Sea")

    return None
