import copy
import os
from datetime import datetime, timezone

from app.services.action_set_service import confirmed_actions, get_action_set, latest_action_set
from app.services.case_service import get_case, get_relevance_results, get_risk_summary
from app.services.document_service import get_confirmed_facts, get_information_gaps, get_obligations
from app.services.hazard_service import list_hazards
from app.services.incoterm_rule_service import resolve_cif_responsibility
from app.services.persistence_service import list_items, save_item
from app.services.structured_llm_service import StructuredLLMError, generate_structured

UTC = timezone.utc
VALID_APPROVAL_STATUSES = {"DRAFT", "SUBMITTED", "APPROVED", "REJECTED", "NEEDS_MORE_INFO", "ARCHIVED"}
PLAN_TYPES = {"LOW_COST", "BALANCED", "MAX_PROTECTION"}
CONFIRMED_FACTS_REQUIRED_MESSAGE = "Confirmed case facts are required before generating treatment plans."


class ConfirmedFactsRequiredError(Exception):
    error = "CONFIRMED_FACTS_REQUIRED"
    message = CONFIRMED_FACTS_REQUIRED_MESSAGE


class PlanGenerationError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


PLAN_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["plans"],
    "properties": {
        "plans": {
            "type": "array",
            "minItems": 3,
            "maxItems": 3,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["plan_type", "plan_name", "summary", "recommended", "recommendation_level", "estimated_cost_level", "estimated_cost_amount", "estimated_cost_currency", "estimated_time_to_execute", "approval_required", "approval_roles", "covered_risks", "residual_risks", "required_actions", "linked_action_ids", "linked_gap_ids", "linked_obligation_ids", "assumptions", "preconditions", "recheck_triggers", "rationale"],
                "properties": {
                    "plan_type": {"type": "string", "enum": ["LOW_COST", "BALANCED", "MAX_PROTECTION"]},
                    "plan_name": {"type": "string"},
                    "summary": {"type": "string"},
                    "recommended": {"type": "boolean"},
                    "recommendation_level": {"type": "string"},
                    "estimated_cost_level": {"type": "string", "enum": ["Low", "Medium", "High"]},
                    "estimated_cost_amount": {"type": ["number", "null"]},
                    "estimated_cost_currency": {"type": ["string", "null"]},
                    "estimated_time_to_execute": {"type": "string"},
                    "approval_required": {"type": "boolean"},
                    "approval_roles": {"type": "array", "items": {"type": "string"}},
                    "covered_risks": {"type": "array", "items": {"type": "string"}},
                    "residual_risks": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["risk_title", "description", "severity", "reason_not_fully_covered", "monitoring_trigger", "owner_role"],
                            "properties": {
                                "risk_title": {"type": "string"},
                                "description": {"type": "string"},
                                "severity": {"type": "string", "enum": ["Low", "Medium", "High", "Critical"]},
                                "reason_not_fully_covered": {"type": "string"},
                                "monitoring_trigger": {"type": "string"},
                                "owner_role": {"type": "string"},
                            },
                        },
                    },
                    "required_actions": {"type": "array", "items": {"type": "string"}},
                    "linked_action_ids": {"type": "array", "items": {"type": "string"}},
                    "linked_gap_ids": {"type": "array", "items": {"type": "string"}},
                    "linked_obligation_ids": {"type": "array", "items": {"type": "string"}},
                    "assumptions": {"type": "array", "items": {"type": "string"}},
                    "preconditions": {"type": "array", "items": {"type": "string"}},
                    "recheck_triggers": {"type": "array", "items": {"type": "string"}},
                    "rationale": {"type": "string"},
                },
            },
        }
    },
}


def generate_treatment_plans(case_id: str, action_set_id: str | None = None) -> dict:
    get_case(case_id)
    try:
        get_confirmed_facts(case_id)
    except KeyError as error:
        raise ConfirmedFactsRequiredError() from error
    action_set = get_action_set(case_id, action_set_id) if action_set_id else latest_action_set(case_id)
    if not action_set or action_set.get("status") != "CONFIRMED":
        raise PlanGenerationError("ACTIONS_NOT_CONFIRMED", "A confirmed action set is required before generating treatment plans.")
    selected_actions = confirmed_actions(action_set)
    if not selected_actions:
        raise PlanGenerationError("NO_ACTIONS_SELECTED", "The confirmed action set contains no selected actions.")
    existing = next((item for item in list_plan_sets(case_id) if item.get("action_set_id") == action_set["action_set_id"] and item.get("status") == "COMPLETED"), None)
    if existing:
        return _plan_set_response(existing)

    context = _plan_context(case_id, action_set, selected_actions)
    model = os.getenv("OPENAI_PLAN_MODEL", "gpt-4o-mini")
    try:
        output = generate_structured(
            model=model,
            timeout_seconds=int(os.getenv("OPENAI_PLAN_TIMEOUT_SECONDS", "60")),
            schema_name="foresail_treatment_plans",
            schema=PLAN_SCHEMA,
            instructions=(
                "Generate exactly three complete English treatment alternatives: LOW_COST, BALANCED, and MAX_PROTECTION. "
                "Use only supplied facts and confirmed actions. Exactly one plan must be recommended. Never reference excluded actions or unknown identifiers."
            ),
            input_data=context,
        )
    except StructuredLLMError as error:
        raise PlanGenerationError(error.code, str(error)) from error

    raw_plans = output.get("plans") or []
    _validate_plans(raw_plans, context)
    version = max((int(item.get("version", 0)) for item in list_plan_sets(case_id)), default=0) + 1
    plan_set_id = f"PSET-{version:03d}"
    now = _now()
    plans = []
    for index, raw in enumerate(raw_plans):
        raw = copy.deepcopy(raw)
        plan_id = f"PLAN-{version:03d}-{index + 1:03d}"
        residuals = []
        for residual_index, residual in enumerate(raw.pop("residual_risks"), start=1):
            item = {
                **residual,
                "residual_risk_id": f"RR-{version:03d}-{index + 1:03d}-{residual_index:02d}",
                "case_id": case_id,
                "plan_id": plan_id,
                "plan_set_id": plan_set_id,
                "status": "OPEN",
                "perspective": context["case"].get("trade_perspective", "SELLER"),
                "incoterm_basis": context["case"].get("incoterm", ""),
                "created_at": now,
                "updated_at": now,
            }
            residuals.append(item)
            save_item("residual_risk", f"{case_id}:{item['residual_risk_id']}", item, case_id)
        recommended = raw.pop("recommended")
        plan = {
            **raw,
            "plan_id": plan_id,
            "case_id": case_id,
            "plan_set_id": plan_set_id,
            "action_set_id": action_set["action_set_id"],
            "version": version,
            "status": "RECOMMENDED" if recommended else "DRAFT",
            "residual_risks": residuals,
            "hazard_ids": [item.get("hazard_id") for item in context["hazards"] if item.get("hazard_id")],
            "amount_at_risk": context["confirmed_facts"].get("amount"),
            "amount_at_risk_currency": context["confirmed_facts"].get("currency"),
            "perspective": context["case"].get("trade_perspective", "SELLER"),
            "incoterm_basis": context["case"].get("incoterm", ""),
            "generation_source": "llm",
            "generation_model": model,
            "created_at": now,
            "updated_at": now,
        }
        plans.append(plan)
        save_item("treatment_plan", f"{case_id}:{plan_id}", plan, case_id)
    recommended = next(plan for plan in plans if plan["status"] == "RECOMMENDED")
    plan_set = {
        "plan_set_id": plan_set_id,
        "case_id": case_id,
        "action_set_id": action_set["action_set_id"],
        "version": version,
        "status": "COMPLETED",
        "model": model,
        "generation_source": "llm",
        "recommended_plan_id": recommended["plan_id"],
        "plans": plans,
        "created_at": now,
        "updated_at": now,
    }
    save_item("plan_set", f"{case_id}:{plan_set_id}", plan_set, case_id)
    return _plan_set_response(plan_set)


def list_plan_sets(case_id: str) -> list[dict]:
    get_case(case_id)
    return sorted([item for item in list_items("plan_set", case_id) if isinstance(item, dict)], key=lambda item: int(item.get("version", 0)))


def list_treatment_plans(case_id: str, action_set_id: str | None = None) -> list[dict]:
    plan_sets = list_plan_sets(case_id)
    if action_set_id:
        selected = next((item for item in plan_sets if item.get("action_set_id") == action_set_id), None)
    else:
        selected = plan_sets[-1] if plan_sets else None
    if selected:
        plans = [item for item in list_items("treatment_plan", case_id) if isinstance(item, dict) and item.get("plan_set_id") == selected.get("plan_set_id")]
        return sorted(copy.deepcopy(plans), key=lambda item: item.get("plan_id", ""))
    legacy = [item for item in list_items("treatment_plan", case_id) if isinstance(item, dict)]
    return sorted([{**item, "generation_source": item.get("generation_source", "legacy")} for item in legacy], key=lambda item: item.get("plan_id", ""))


def get_treatment_plan(case_id: str, plan_id: str) -> dict:
    for plan in [item for item in list_items("treatment_plan", case_id) if isinstance(item, dict)]:
        if plan.get("plan_id") == plan_id:
            return copy.deepcopy(plan)
    raise KeyError(plan_id)


def select_treatment_plan(case_id: str, plan_id: str) -> dict:
    target = get_treatment_plan(case_id, plan_id)
    for plan in [item for item in list_items("treatment_plan", case_id) if isinstance(item, dict)]:
        if plan.get("plan_set_id") != target.get("plan_set_id"):
            continue
        plan["status"] = "SELECTED" if plan["plan_id"] == plan_id else ("RECOMMENDED" if plan.get("status") == "SELECTED" else plan.get("status", "DRAFT"))
        plan["updated_at"] = _now()
        save_item("treatment_plan", f"{case_id}:{plan['plan_id']}", plan, case_id)
    target = get_treatment_plan(case_id, plan_id)
    target["status"] = "SELECTED"
    return target


def archive_treatment_plan(case_id: str, plan_id: str) -> dict:
    plan = get_treatment_plan(case_id, plan_id)
    plan["status"] = "ARCHIVED"
    plan["updated_at"] = _now()
    save_item("treatment_plan", f"{case_id}:{plan_id}", plan, case_id)
    return copy.deepcopy(plan)


def generate_approval_package(case_id: str, plan_id: str) -> dict:
    plan = get_treatment_plan(case_id, plan_id)
    package_id = f"APP-{len(list_approval_packages(case_id)) + 1:03d}"
    now = _now()
    package = {
        "approval_package_id": package_id,
        "case_id": case_id,
        "plan_id": plan_id,
        "plan_set_id": plan.get("plan_set_id"),
        "action_set_id": plan.get("action_set_id"),
        "title": f"Approval Package - {plan['plan_name']}",
        "summary": f"{plan['plan_name']} is proposed because {plan['rationale']} It covers {len(plan['covered_risks'])} risks and leaves {len(plan['residual_risks'])} residual risks for monitoring.",
        "recommended_plan_name": plan["plan_name"],
        "estimated_cost_level": plan["estimated_cost_level"],
        "estimated_cost_amount": plan["estimated_cost_amount"],
        "estimated_cost_currency": plan["estimated_cost_currency"],
        "covered_risks": plan["covered_risks"],
        "residual_risks": [item["risk_title"] for item in plan["residual_risks"]],
        "required_actions": plan["required_actions"],
        "approval_roles": plan["approval_roles"],
        "approval_status": "DRAFT",
        "approval_scope": "EXECUTION_APPROVAL",
        "conflict_safe_mode": False,
        "decision_note": None,
        "created_at": now,
        "updated_at": now,
    }
    save_item("approval_package", f"{case_id}:{package_id}", package, case_id)
    return copy.deepcopy(package)


def list_approval_packages(case_id: str) -> list[dict]:
    get_case(case_id)
    return sorted([item for item in list_items("approval_package", case_id) if isinstance(item, dict)], key=lambda item: item.get("approval_package_id", ""))


def update_approval_status(case_id: str, approval_package_id: str, status: str, note: str | None = None) -> dict:
    if status not in VALID_APPROVAL_STATUSES:
        raise ValueError(f"Unsupported approval status: {status}")
    for package in list_approval_packages(case_id):
        if package.get("approval_package_id") == approval_package_id:
            package["approval_status"] = status
            package["decision_note"] = note
            package["updated_at"] = _now()
            save_item("approval_package", f"{case_id}:{approval_package_id}", package, case_id)
            return copy.deepcopy(package)
    raise KeyError(approval_package_id)


def _plan_context(case_id: str, action_set: dict, actions: list[dict]) -> dict:
    case = get_case(case_id)
    try:
        facts = get_confirmed_facts(case_id)
    except KeyError as error:
        raise ConfirmedFactsRequiredError() from error
    return {
        "case": case,
        "confirmed_facts": facts,
        "relevance_results": get_relevance_results(case_id),
        "risk_summary": get_risk_summary(case_id),
        "obligations": get_obligations(case_id),
        "information_gaps": get_information_gaps(case_id),
        "hazards": list_hazards(case_id),
        "incoterm_responsibility": resolve_cif_responsibility(case),
        "action_set_id": action_set["action_set_id"],
        "confirmed_actions": actions,
    }


def _validate_plans(plans: list[dict], context: dict) -> None:
    if len(plans) != 3 or {item.get("plan_type") for item in plans} != PLAN_TYPES:
        raise PlanGenerationError("INVALID_LLM_OUTPUT", "LLM must return exactly one plan for each required plan type.")
    if sum(1 for item in plans if item.get("recommended")) != 1:
        raise PlanGenerationError("INVALID_LLM_OUTPUT", "LLM must recommend exactly one plan.")
    action_ids = {item["action_id"] for item in context["confirmed_actions"]}
    gap_ids = {item.get("gap_id") for item in context["information_gaps"]}
    obligation_ids = {item.get("obligation_id") for item in context["obligations"]}
    for plan in plans:
        if any(item not in action_ids for item in plan.get("linked_action_ids", [])):
            raise PlanGenerationError("INVALID_LLM_OUTPUT", "Plan references an unconfirmed action.")
        if any(item not in gap_ids for item in plan.get("linked_gap_ids", [])):
            raise PlanGenerationError("INVALID_LLM_OUTPUT", "Plan references an unknown information gap.")
        if any(item not in obligation_ids for item in plan.get("linked_obligation_ids", [])):
            raise PlanGenerationError("INVALID_LLM_OUTPUT", "Plan references an unknown obligation.")


def _plan_set_response(plan_set: dict) -> dict:
    return {
        "case_id": plan_set["case_id"],
        "plan_set_id": plan_set["plan_set_id"],
        "action_set_id": plan_set["action_set_id"],
        "version": plan_set["version"],
        "status": plan_set["status"],
        "recommended_plan_id": plan_set["recommended_plan_id"],
        "plans": copy.deepcopy(plan_set["plans"]),
        "conflict_safe_mode": False,
        "allowed_plan_types": ["LOW_COST", "BALANCED", "MAX_PROTECTION"],
    }


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
