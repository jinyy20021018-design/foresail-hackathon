from datetime import datetime, timedelta, timezone
UTC = timezone.utc

VALID_SOURCE_TYPES = {"MOCK", "WEATHER", "NEWS", "PORT", "GEOPOLITICAL", "POLICY", "MANUAL"}
VALID_EVENT_TYPES = {"VESSEL_DELAY", "PORT_DISRUPTION", "WEATHER", "SECURITY", "GEOPOLITICAL", "TRADE_POLICY", "ROUTE_DISRUPTION", "UNKNOWN"}
VALID_SEVERITIES = {"LOW", "MEDIUM", "HIGH", "CRITICAL", "UNKNOWN"}

DEFAULT_IMPACT_DURATION_DAYS = {
    "WEATHER": 3,
    "PORT_DISRUPTION": 7,
    "SECURITY": 14,
    "GEOPOLITICAL": 14,
    "TRADE_POLICY": 30,
    "ROUTE_DISRUPTION": 14,
    "VESSEL_DELAY": 7,
    "UNKNOWN": 7,
}

LEGACY_EVENT_TYPE_MAP = {
    "PORT_STRIKE": "PORT_DISRUPTION",
    "PORT_CONGESTION": "PORT_DISRUPTION",
}


def normalize_events(events: list[dict], case_id: str, source_hint: str | None = None) -> list[dict]:
    normalized = []
    seen_ids: set[str] = set()
    for index, event in enumerate(events, start=1):
        item = normalize_event(event, case_id, index, source_hint)
        event_id = item["event_id"]
        if event_id in seen_ids:
            event_id = f"{event_id}-{index:03d}"
            item["event_id"] = event_id
        seen_ids.add(event_id)
        normalized.append(item)
    return normalized


def normalize_event(event: dict, case_id: str, index: int = 1, source_hint: str | None = None) -> dict:
    source_type = _source_type(event)
    legacy_type = str(event.get("type") or event.get("event_type") or "UNKNOWN").upper()
    event_type = _event_type(legacy_type)
    severity = _severity(event.get("severity"))
    confidence = _confidence(event.get("confidence"))
    affected_vessels = _as_list(event.get("affected_vessels"))
    if event.get("affected_vessel"):
        affected_vessels.append(event["affected_vessel"])
    affected_vessels = _dedupe_text(affected_vessels)
    affected_ports = _dedupe_text(_as_list(event.get("affected_ports")))
    affected_routes = _dedupe_text(_as_list(event.get("affected_routes")))
    locations = _dedupe_text(_as_list(event.get("locations")) + affected_ports + _as_list(event.get("affected_region")))
    event_time = _date_or_datetime(event.get("event_time"))
    published_at = _date_or_datetime(event.get("published_at")) or event_time
    title = str(event.get("title") or "Untitled external event")
    event_id = str(event.get("event_id") or f"EVT-{source_type}-{index:03d}")
    source = str(event.get("source") or source_hint or "unknown_connector")
    dedup_key = event.get("dedup_key") or _dedup_key(source_type, event_type, title, event_time, affected_ports, affected_vessels)

    normalized = {
        "event_id": event_id,
        "case_id": case_id,
        "source": source,
        "source_type": source_type,
        "event_type": event_type,
        "title": title,
        "description": str(event.get("description") or event.get("impact") or title),
        "event_time": event_time,
        "published_at": published_at,
        "expected_impact_window": _impact_window(event, event_type, event_time),
        "voyage_aligned": bool(event.get("voyage_aligned")),
        "locations": locations,
        "affected_ports": affected_ports,
        "affected_routes": affected_routes,
        "affected_vessels": affected_vessels,
        "severity": severity,
        "confidence": confidence,
        "url": event.get("url"),
        "raw_payload": event.get("raw_payload") if event.get("raw_payload") is not None else event,
        "dedup_key": dedup_key,
        "created_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        # Backward-compatible fields used by the existing deterministic engine.
        "type": legacy_type if legacy_type != "UNKNOWN" else event_type,
        "affected_vessel": affected_vessels[0] if affected_vessels else None,
        "affected_region": event.get("affected_region") or (locations[0] if locations else ""),
        "impact": event.get("impact") or event.get("description") or title,
        "delay_days": event.get("delay_days"),
        "old_eta": event.get("old_eta"),
        "new_eta": event.get("new_eta"),
        "expected_classification": event.get("expected_classification"),
        "matched_query_ids": event.get("matched_query_ids", []),
        "matched_terms": event.get("matched_terms", []),
    }
    return normalized


def _source_type(event: dict) -> str:
    value = str(event.get("source_type") or "").upper()
    if value in VALID_SOURCE_TYPES:
        return value
    source = str(event.get("source") or "").lower()
    if "weather" in source:
        return "WEATHER"
    if "news" in source:
        return "NEWS"
    if "port" in source:
        return "PORT"
    if "security" in source:
        return "GEOPOLITICAL"
    return "MOCK"


def _event_type(value: str) -> str:
    mapped = LEGACY_EVENT_TYPE_MAP.get(value, value)
    return mapped if mapped in VALID_EVENT_TYPES else "UNKNOWN"


def _severity(value) -> str:
    text = str(value or "UNKNOWN").upper()
    if text == "MED":
        text = "MEDIUM"
    return text if text in VALID_SEVERITIES else "UNKNOWN"


def _confidence(value) -> float:
    try:
        return max(0.0, min(float(value), 1.0))
    except (TypeError, ValueError):
        return 0.0


def _as_list(value) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return [str(item) for item in value if item not in {None, ""}]
    return [str(value)]


def _dedupe_text(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value.strip() for value in values if value and value.strip()))


def _date_or_datetime(value) -> str | None:
    if value in {None, ""}:
        return None
    return str(value)


def _impact_window(event: dict, event_type: str, event_time: str | None) -> dict | None:
    explicit = event.get("expected_impact_window")
    if isinstance(explicit, dict) and explicit.get("start") and explicit.get("end"):
        return {"start": str(explicit["start"]), "end": str(explicit["end"]), "basis": str(explicit.get("basis") or "explicit")}

    if event_type == "VESSEL_DELAY" and event.get("new_eta"):
        start = event_time or str(event.get("old_eta") or "")
        if start:
            return {"start": start, "end": str(event["new_eta"]), "basis": "eta_shift"}

    start_date = _parse_date(event_time)
    if start_date is None:
        return None
    duration = DEFAULT_IMPACT_DURATION_DAYS.get(event_type, 7)
    return {
        "start": start_date.isoformat(),
        "end": (start_date + timedelta(days=duration)).isoformat(),
        "basis": "type_default",
    }


def _parse_date(value):
    if value in {None, ""}:
        return None
    text = str(value).strip()
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        pass
    try:
        return datetime.strptime(text[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _dedup_key(source_type: str, event_type: str, title: str, event_time: str | None, ports: list[str], vessels: list[str]) -> str:
    location = (ports or vessels or [""])[0]
    return "|".join([source_type, event_type, location.lower(), title.lower(), str(event_time or "")])
