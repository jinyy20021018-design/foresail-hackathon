import copy
import os
from datetime import date, datetime, timezone

from app.services.case_service import get_case, get_relevance_results, get_risk_summary, mark_actions_required
from app.services.document_service import get_confirmed_facts, get_information_gaps, get_obligations
from app.services.hazard_service import list_hazards
from app.services.incoterm_rule_service import resolve_cif_responsibility
from app.services.persistence_service import list_items, save_item
from app.services.structured_llm_service import StructuredLLMError, generate_structured

UTC = timezone.utc
VALID_PRIORITIES = {"Low", "Medium", "High", "Critical"}
VALID_RESPONSIBLE = {"BUYER", "SELLER", "SHARED", "UNKNOWN"}


class ActionSetError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


ACTION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["actions"],
    "properties": {
        "actions": {
            "type": "array",
            "minItems": 1,
            "maxItems": 20,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["title", "owner_role", "priority", "deadline", "deadline_date", "rationale", "related_exposure", "responsible_party", "linked_hazard_ids", "linked_obligation_ids"],
                "properties": {
                    "title": {"type": "string", "minLength": 3},
                    "owner_role": {"type": "string", "minLength": 2},
                    "priority": {"type": "string", "enum": ["Low", "Medium", "High", "Critical"]},
                    "deadline": {"type": "string", "minLength": 2},
                    "deadline_date": {"type": "string"},
                    "rationale": {"type": "string", "minLength": 3},
                    "related_exposure": {"type": "string"},
                    "responsible_party": {"type": "string", "enum": ["BUYER", "SELLER", "SHARED", "UNKNOWN"]},
                    "linked_hazard_ids": {"type": "array", "items": {"type": "string"}},
                    "linked_obligation_ids": {"type": "array", "items": {"type": "string"}},
                },
            },
        }
    },
}


def generate_action_set(case_id: str) -> dict:
    context = _context(case_id)
    model = os.getenv("OPENAI_ACTION_MODEL", "gpt-4o-mini")
    try:
        output = generate_structured(
            model=model,
            timeout_seconds=int(os.getenv("OPENAI_ACTION_TIMEOUT_SECONDS", "60")),
            schema_name="foresail_action_candidates",
            schema=ACTION_SCHEMA,
            instructions=(
                "Generate executable trade-risk action candidates in English. Use only supplied facts and existing risk decisions. "
                "Do not reclassify events, change case status, or invent legal conclusions. Link only supplied exposure, hazard, and obligation identifiers."
            ),
            input_data=context,
        )
    except StructuredLLMError as error:
        raise ActionSetError(error.code, str(error)) from error

    versions = list_action_sets(case_id)
    version = max((int(item.get("version", 0)) for item in versions), default=0) + 1
    known_hazards = {item.get("hazard_id") for item in context["hazards"]}
    known_obligations = {item.get("obligation_id") for item in context["obligations"]}
    known_exposures = {item.get("category") for item in context["risk_summary"].get("exposures", [])}
    actions = []
    for index, raw in enumerate(output.get("actions") or []):
        _validate_raw_action(raw, known_hazards, known_obligations, known_exposures)
        actions.append({
            **raw,
            "action_id": f"ACT-{version:03d}-{index + 1:03d}",
            "selected": True,
            "status": "CANDIDATE",
            "party_perspective": context["case"].get("trade_perspective", "SELLER"),
            "incoterm_basis": context["case"].get("incoterm", ""),
            "generation_source": "llm",
        })
    if not actions:
        raise ActionSetError("INVALID_LLM_OUTPUT", "LLM returned no actions.")
    now = _now()
    action_set = {
        "action_set_id": f"ASET-{version:03d}",
        "case_id": case_id,
        "version": version,
        "status": "CANDIDATE",
        "model": model,
        "generation_source": "llm",
        "actions": actions,
        "created_at": now,
        "updated_at": now,
        "confirmed_at": None,
    }
    _save(action_set)
    mark_actions_required(case_id)
    return copy.deepcopy(action_set)


def clone_action_set(case_id: str, action_set_id: str) -> dict:
    source = get_action_set(case_id, action_set_id)
    versions = list_action_sets(case_id)
    version = max((int(item.get("version", 0)) for item in versions), default=0) + 1
    actions = []
    for index, raw in enumerate(source["actions"]):
        actions.append({**raw, "action_id": f"ACT-{version:03d}-{index + 1:03d}", "selected": raw.get("status") != "EXCLUDED", "status": "CANDIDATE"})
    now = _now()
    result = {**source, "action_set_id": f"ASET-{version:03d}", "version": version, "status": "CANDIDATE", "actions": actions, "created_at": now, "updated_at": now, "confirmed_at": None}
    _save(result)
    return copy.deepcopy(result)


def list_action_sets(case_id: str) -> list[dict]:
    get_case(case_id)
    return sorted([item for item in list_items("action_set", case_id) if isinstance(item, dict)], key=lambda item: int(item.get("version", 0)))


def get_action_set(case_id: str, action_set_id: str) -> dict:
    for item in list_action_sets(case_id):
        if item.get("action_set_id") == action_set_id:
            return copy.deepcopy(item)
    raise KeyError(action_set_id)


def latest_action_set(case_id: str) -> dict | None:
    items = list_action_sets(case_id)
    return copy.deepcopy(items[-1]) if items else None


def update_action_set(case_id: str, action_set_id: str, actions: list[dict]) -> dict:
    action_set = get_action_set(case_id, action_set_id)
    if action_set["status"] != "CANDIDATE":
        raise ActionSetError("ACTION_SET_IMMUTABLE", "Confirmed action sets cannot be edited.")
    incoming = {item.get("action_id"): item for item in actions}
    if set(incoming) != {item["action_id"] for item in action_set["actions"]}:
        raise ActionSetError("INVALID_ACTION_UPDATE", "The update must contain every action in this action set exactly once.")
    for action in action_set["actions"]:
        edited = incoming[action["action_id"]]
        for field in ["title", "owner_role", "priority", "deadline", "deadline_date", "selected"]:
            if field in edited:
                action[field] = edited[field]
        _validate_editable_action(action)
    action_set["updated_at"] = _now()
    _save(action_set)
    return copy.deepcopy(action_set)


def confirm_action_set(case_id: str, action_set_id: str) -> dict:
    action_set = get_action_set(case_id, action_set_id)
    if action_set["status"] == "CONFIRMED":
        return action_set
    selected = [item for item in action_set["actions"] if item.get("selected")]
    if not selected:
        raise ActionSetError("NO_ACTIONS_SELECTED", "Select at least one action before confirming.")
    action_set["status"] = "CONFIRMED"
    action_set["confirmed_at"] = _now()
    action_set["updated_at"] = action_set["confirmed_at"]
    for action in action_set["actions"]:
        action["status"] = "CONFIRMED" if action.get("selected") else "EXCLUDED"
    _save(action_set)
    save_item("actions", case_id, selected, case_id)
    return copy.deepcopy(action_set)


def confirmed_actions(action_set: dict) -> list[dict]:
    return [copy.deepcopy(item) for item in action_set.get("actions", []) if item.get("status") == "CONFIRMED" and item.get("selected")]


def _context(case_id: str) -> dict:
    case = get_case(case_id)
    try:
        facts = get_confirmed_facts(case_id)
    except KeyError as error:
        raise ActionSetError("CONFIRMED_FACTS_REQUIRED", "Confirmed case facts are required before generating actions.") from error
    return {
        "case": case,
        "confirmed_facts": facts,
        "relevance_results": get_relevance_results(case_id),
        "risk_summary": get_risk_summary(case_id),
        "obligations": get_obligations(case_id),
        "information_gaps": get_information_gaps(case_id),
        "hazards": list_hazards(case_id),
        "incoterm_responsibility": resolve_cif_responsibility(case),
    }


def _validate_raw_action(raw: dict, hazards: set, obligations: set, exposures: set) -> None:
    if not isinstance(raw, dict):
        raise ActionSetError("INVALID_LLM_OUTPUT", "Each action must be an object.")
    _validate_editable_action(raw)
    if raw.get("responsible_party") not in VALID_RESPONSIBLE:
        raise ActionSetError("INVALID_LLM_OUTPUT", "Action has an invalid responsible party.")
    if any(item not in hazards for item in raw.get("linked_hazard_ids", [])):
        raise ActionSetError("INVALID_LLM_OUTPUT", "Action references an unknown hazard.")
    if any(item not in obligations for item in raw.get("linked_obligation_ids", [])):
        raise ActionSetError("INVALID_LLM_OUTPUT", "Action references an unknown obligation.")
    if exposures and raw.get("related_exposure") not in exposures:
        raise ActionSetError("INVALID_LLM_OUTPUT", "Action references an unknown exposure.")


def _validate_editable_action(action: dict) -> None:
    if not str(action.get("title") or "").strip() or not str(action.get("owner_role") or "").strip():
        raise ActionSetError("INVALID_ACTION_UPDATE", "Action title and owner are required.")
    if action.get("priority") not in VALID_PRIORITIES:
        raise ActionSetError("INVALID_ACTION_UPDATE", "Action priority is invalid.")
    try:
        date.fromisoformat(str(action.get("deadline_date")))
    except ValueError as error:
        raise ActionSetError("INVALID_ACTION_UPDATE", "Action deadline_date must be YYYY-MM-DD.") from error


def _save(action_set: dict) -> None:
    save_item("action_set", f"{action_set['case_id']}:{action_set['action_set_id']}", action_set, action_set["case_id"])


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
