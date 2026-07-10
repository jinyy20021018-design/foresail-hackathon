import copy
import json
import re
from datetime import date, datetime, timedelta, timezone
UTC = timezone.utc
from pathlib import Path

from app.services.status_machine import can_transition, transition_case
from app.services.watch_profile_service import build_watch_profile
from app.services.persistence_service import clear_namespace, list_item_records, load_item, save_item

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

_cases: dict[str, dict] = {}
_profiles: dict[str, dict] = {}
_results: dict[str, list[dict]] = {}
_risk_summaries: dict[str, dict] = {}
_actions: dict[str, list[dict]] = {}
_timelines: dict[str, list[dict]] = {}


def _load_demo_case() -> dict:
    with (DATA_DIR / "demo_case.json").open("r", encoding="utf-8") as file:
        return json.load(file)


def reset_store() -> None:
    clear_runtime_case_cache()
    try:
        from app.services.document_service import clear_runtime_document_cache

        clear_runtime_document_cache()
    except ImportError:
        pass
    for namespace in [
        "case",
        "watch_profile",
        "status_timeline",
        "relevance_results",
        "risk_summary",
        "actions",
        "documents",
        "extracted_fields",
        "confirmed_facts",
        "obligations",
        "information_gaps",
        "action_drafts",
        "field_conflicts",
        "agent_run",
        "agent_trace",
        "treatment_plan",
        "residual_risk",
        "approval_package",
        "external_event",
        "hazards",
        "corridor_state",
    ]:
        clear_namespace(namespace)


def clear_runtime_case_cache() -> None:
    _cases.clear()
    _profiles.clear()
    _results.clear()
    _risk_summaries.clear()
    _actions.clear()
    _timelines.clear()


def create_demo_case(uploaded_files: list[str] | None = None, imminent: bool = False) -> dict:
    case = _load_demo_case()
    case["case_id"] = generate_next_case_id()
    _ensure_case_defaults(case)
    if imminent:
        today = _today()
        case["etd"] = (today + timedelta(days=2)).isoformat()
        case["eta"] = (today + timedelta(days=14)).isoformat()
        case["latest_shipment_date"] = (today + timedelta(days=5)).isoformat()
        case["lc_expiry_date"] = (today + timedelta(days=35)).isoformat()
    case["uploaded_files"] = uploaded_files or []
    case["case_name"] = "CAPEMOLLINI Imminent Departure Demo" if imminent else "CAPEMOLLINI Shanghai to Dhaka Demo"
    case["buyer"] = "Demo Buyer"
    case["seller"] = "Demo Seller"
    case["commodity"] = "Cotton Yarn"
    case["owner"] = "Trade Ops"
    case["notes"] = "Demo case created from MVP seed data."
    now = _now()
    case["created_at"] = now
    case["updated_at"] = now
    case["mock_extraction_note"] = "Mock extracted fields for MVP. Files are not parsed in this version."

    timeline = [{"status": "DRAFT", "reason": "Demo case initialized from built-in mock extracted fields."}]
    transition_case(case, "ACTIVE", timeline, "Core trade fields are available.")

    profile = build_watch_profile(case)
    _cases[case["case_id"]] = copy.deepcopy(case)
    _profiles[case["case_id"]] = profile
    _timelines[case["case_id"]] = timeline
    _results[case["case_id"]] = []
    _risk_summaries[case["case_id"]] = {"triggered": False, "trigger_events": [], "exposures": []}
    _actions[case["case_id"]] = []
    _persist_case_bundle(case["case_id"])
    return get_case(case["case_id"])


def create_case(payload: dict) -> dict:
    now = _now()
    port_of_loading = payload.get("port_of_loading") or "TBD"
    port_of_discharge = payload.get("port_of_discharge") or "TBD"
    final_destination = payload.get("final_destination") or port_of_discharge
    route = " -> ".join(part for part in [port_of_loading, port_of_discharge, final_destination] if part and part != "TBD")
    case = {
        "case_id": generate_next_case_id(),
        "status": "DRAFT",
        "case_name": payload.get("case_name") or "New Trade Case",
        "buyer": payload.get("buyer") or "",
        "seller": payload.get("seller") or "",
        "commodity": payload.get("commodity") or "",
        "vessel": payload.get("vessel") or "TBD",
        "route": route or "TBD",
        "port_of_loading": port_of_loading,
        "port_of_discharge": port_of_discharge,
        "final_destination": final_destination,
        "etd": payload.get("etd") or "",
        "eta": payload.get("eta") or "",
        "latest_shipment_date": payload.get("latest_shipment_date") or "",
        "payment_method": payload.get("payment_method") or "",
        "incoterm": payload.get("incoterm") or "",
        "incoterm_named_place": payload.get("incoterm_named_place") or "",
        "trade_perspective": payload.get("trade_perspective") or "SELLER",
        "owner": payload.get("owner") or "Trade Ops",
        "notes": payload.get("notes") or "",
        "created_at": now,
        "updated_at": now,
        "uploaded_files": [],
        "mock_extraction_note": "New case created manually. Upload documents to extract trade facts.",
    }
    _cases[case["case_id"]] = copy.deepcopy(case)
    _profiles[case["case_id"]] = build_watch_profile(case)
    _timelines[case["case_id"]] = [{"status": "DRAFT", "reason": "Case created manually."}]
    _results[case["case_id"]] = []
    _risk_summaries[case["case_id"]] = {"triggered": False, "trigger_events": [], "exposures": []}
    _actions[case["case_id"]] = []
    _persist_case_bundle(case["case_id"])
    return get_case(case["case_id"])


def update_case_details(case_id: str, payload: dict) -> dict:
    if case_id not in _cases:
        get_case(case_id)
    editable_fields = [
        "case_name",
        "buyer",
        "seller",
        "commodity",
        "port_of_loading",
        "port_of_discharge",
        "final_destination",
        "owner",
        "notes",
    ]
    case = _cases[case_id]
    for field in editable_fields:
        if field in payload and payload[field] is not None:
            case[field] = payload[field]
    port_of_loading = case.get("port_of_loading") or ""
    port_of_discharge = case.get("port_of_discharge") or ""
    final_destination = case.get("final_destination") or ""
    route_parts = [part for part in [port_of_loading, port_of_discharge, final_destination] if part and part != "TBD"]
    if route_parts:
        case["route"] = " -> ".join(route_parts)
    case["updated_at"] = _now()
    _profiles[case_id] = build_watch_profile(case)
    _persist_case_bundle(case_id)
    return get_case(case_id)


def generate_next_case_id() -> str:
    max_number = 0
    for record in list_item_records("case"):
        case_id = str(record.get("payload", {}).get("case_id") or record.get("item_key") or "")
        match = re.fullmatch(r"CASE-(\d+)", case_id)
        if match:
            max_number = max(max_number, int(match.group(1)))
    return f"CASE-{max_number + 1:03d}"


def get_case(case_id: str) -> dict:
    if case_id not in _cases:
        stored = load_item("case", case_id)
        if stored:
            _cases[case_id] = stored
    if case_id not in _cases:
        raise KeyError(case_id)
    _ensure_case_defaults(_cases[case_id])
    return copy.deepcopy(_cases[case_id])


def get_watch_profile(case_id: str) -> dict:
    if case_id not in _profiles:
        stored = load_item("watch_profile", case_id)
        if stored:
            _profiles[case_id] = stored
    if case_id not in _profiles:
        raise KeyError(case_id)
    return copy.deepcopy(_profiles[case_id])


def replace_case_facts(case_id: str, facts: dict) -> None:
    if case_id not in _cases:
        get_case(case_id)
    case = _cases[case_id]
    for key in [
        "vessel",
        "route",
        "port_of_loading",
        "port_of_discharge",
        "final_destination",
        "etd",
        "eta",
        "latest_shipment_date",
        "payment_method",
        "incoterm",
        "incoterm_named_place",
        "amount",
        "currency",
    ]:
        if key in facts and facts[key] not in {None, ""}:
            case[key] = facts[key]
    case["updated_at"] = _now()
    _profiles[case_id] = build_watch_profile(case)
    _persist_case_bundle(case_id)


def set_trade_perspective(case_id: str, perspective: str) -> dict:
    if case_id not in _cases:
        get_case(case_id)
    _cases[case_id]["trade_perspective"] = perspective
    _cases[case_id]["updated_at"] = _now()
    _persist_case_bundle(case_id)
    return get_case(case_id)


def get_timeline(case_id: str) -> list[dict]:
    if case_id not in _timelines:
        stored = load_item("status_timeline", case_id)
        if stored:
            _timelines[case_id] = stored
    if case_id not in _timelines:
        raise KeyError(case_id)
    return copy.deepcopy(_timelines[case_id])


def set_monitoring_outputs(
    case_id: str,
    relevance_results: list[dict],
    risk_summary: dict,
    actions: list[dict],
    hazard_delta: dict | None = None,
) -> None:
    if case_id not in _cases:
        get_case(case_id)
    if case_id not in _timelines:
        _timelines[case_id] = load_item("status_timeline", case_id) or []

    case = _cases[case_id]
    timeline = _timelines[case_id]
    triggered = risk_summary["triggered"]

    if case["status"] == "ACTIVE" and can_transition(case["status"], "WATCHING"):
        transition_case(case, "WATCHING", timeline, "Monitoring started with configured external event feed.")

    if triggered and can_transition(case["status"], "AT_RISK"):
        transition_case(case, "AT_RISK", timeline, "At least one Relevant event was detected.")

    if triggered and actions and can_transition(case["status"], "ACTION_REQUIRED"):
        transition_case(case, "ACTION_REQUIRED", timeline, "Recommended actions were generated for the triggered exposures.")

    if (
        not triggered
        and hazard_delta is not None
        and hazard_delta.get("all_clear")
        and case["status"] in {"AT_RISK", "ACTION_REQUIRED"}
        and can_transition(case["status"], "MONITORING")
    ):
        transition_case(case, "MONITORING", timeline, "All previously detected hazards are resolved; case returned to routine monitoring.")

    _results[case_id] = copy.deepcopy(relevance_results)
    _risk_summaries[case_id] = copy.deepcopy(risk_summary)
    _actions[case_id] = copy.deepcopy(actions)
    _persist_case_bundle(case_id)


def continue_monitoring(case_id: str) -> dict:
    if case_id not in _cases:
        get_case(case_id)
    if case_id not in _timelines:
        _timelines[case_id] = load_item("status_timeline", case_id) or []
    transition_case(
        _cases[case_id],
        "MONITORING",
        _timelines[case_id],
        "User confirmed the action board and continued monitoring.",
    )
    _persist_case_bundle(case_id)
    return {
        "case": get_case(case_id),
        "status_timeline": get_timeline(case_id),
    }


def get_relevance_results(case_id: str) -> list[dict]:
    if case_id not in _results:
        _results[case_id] = load_item("relevance_results", case_id) or []
    if case_id not in _results:
        raise KeyError(case_id)
    return copy.deepcopy(_results[case_id])


def get_risk_summary(case_id: str) -> dict:
    if case_id not in _risk_summaries:
        _risk_summaries[case_id] = load_item("risk_summary", case_id) or {"triggered": False, "trigger_events": [], "exposures": []}
    if case_id not in _risk_summaries:
        raise KeyError(case_id)
    return copy.deepcopy(_risk_summaries[case_id])


def get_actions(case_id: str) -> list[dict]:
    if case_id not in _actions:
        _actions[case_id] = load_item("actions", case_id) or []
    if case_id not in _actions:
        raise KeyError(case_id)
    return copy.deepcopy(_actions[case_id])


def _persist_case_bundle(case_id: str) -> None:
    if case_id in _cases:
        save_item("case", case_id, _cases[case_id], case_id)
    if case_id in _profiles:
        save_item("watch_profile", case_id, _profiles[case_id], case_id)
    if case_id in _timelines:
        save_item("status_timeline", case_id, _timelines[case_id], case_id)
    if case_id in _results:
        save_item("relevance_results", case_id, _results[case_id], case_id)
    if case_id in _risk_summaries:
        save_item("risk_summary", case_id, _risk_summaries[case_id], case_id)
    if case_id in _actions:
        save_item("actions", case_id, _actions[case_id], case_id)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _today() -> date:
    return datetime.now(UTC).date()


def _ensure_case_defaults(case: dict) -> None:
    case.setdefault("trade_perspective", "SELLER")
    case.setdefault("incoterm_named_place", "")
