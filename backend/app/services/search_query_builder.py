import os

from app.services.document_service import get_best_case_facts


def build_external_event_queries(case_id: str, watch_profile: dict) -> list[dict]:
    facts = get_best_case_facts(case_id)
    vessel = _value(facts.get("vessel") or watch_profile.get("watched_vessel"))
    ports = [port for port in watch_profile.get("watched_ports", []) if port and port != "TBD"]
    regions = [region for region in watch_profile.get("watched_route_regions", []) if region]
    route = _value(facts.get("route"))
    queries: list[dict] = []

    def add(query_text: str, query_type: str, priority: str, created_from: list[str], source_hint: str = "GDELT") -> None:
        queries.append({
            "query_id": f"Q-{len(queries) + 1:03d}",
            "query_text": query_text,
            "query_type": query_type,
            "priority": priority,
            "source_hint": source_hint,
            "created_from": created_from,
        })

    if vessel and vessel != "TBD":
        add(f"{vessel} vessel delay OR schedule OR ETA OR port call", "VESSEL", "HIGH", ["vessel"])

    if len(ports) >= 2:
        add(f"{ports[1]} port strike OR congestion OR disruption", "PORT", "HIGH", ["port_of_discharge"])
    elif ports:
        add(f"{ports[0]} port strike OR congestion OR disruption", "PORT", "HIGH", ["watched_ports"])

    if regions:
        add(f"{regions[0]} storm OR typhoon OR shipping disruption", "WEATHER_REGION", "MEDIUM", ["route_region"], "OPEN_METEO")

    if ports:
        add(f"{ports[0]} port delay OR congestion OR terminal disruption", "PORT", "MEDIUM", ["port_of_loading"])

    for region in regions[:2]:
        if region == regions[0]:
            add(f"{region} security OR conflict OR route disruption", "GEOPOLITICAL", "MEDIUM", ["route_region"], "GDELT")
            continue
        add(f"{region} storm OR typhoon OR shipping disruption", "WEATHER_REGION", "MEDIUM", ["route_region"], "OPEN_METEO")
        add(f"{region} security OR conflict OR route disruption", "GEOPOLITICAL", "MEDIUM", ["route_region"], "GDELT")

    if ports:
        destination = ports[-1]
        add(f"{destination} customs OR inland transport OR policy disruption", "TRADE_POLICY", "LOW", ["final_destination"])

    if "Bay of Bengal" not in regions and "bay of bengal" in route.lower():
        add("Bay of Bengal storm shipping disruption", "WEATHER_REGION", "MEDIUM", ["route"], "OPEN_METEO")

    add("global shipping delay port disruption customs", "GENERAL_SHIPPING", "LOW", ["fallback"], "GDELT")
    return _limit_queries(queries)


def _value(value) -> str:
    return str(value or "").strip()


def _limit_queries(queries: list[dict]) -> list[dict]:
    try:
        limit = int(os.getenv("EXTERNAL_EVENT_QUERY_LIMIT", "3"))
    except ValueError:
        limit = 3
    if limit <= 0:
        return queries
    return queries[:limit]
