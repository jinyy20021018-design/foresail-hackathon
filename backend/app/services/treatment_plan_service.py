from datetime import datetime, timezone
UTC = timezone.utc

from app.services.case_service import get_case
from app.services.document_service import (
    get_action_drafts,
    get_best_case_facts,
    get_confirmed_facts,
    get_field_conflicts,
    get_information_gaps,
    get_obligations,
)
from app.services.persistence_service import list_items, save_item

VALID_PLAN_STATUSES = {"DRAFT", "RECOMMENDED", "SELECTED", "SUBMITTED_FOR_APPROVAL", "APPROVED", "REJECTED", "ARCHIVED"}
VALID_APPROVAL_STATUSES = {"DRAFT", "SUBMITTED", "APPROVED", "REJECTED", "NEEDS_MORE_INFO", "ARCHIVED"}
CONFIRMED_FACTS_REQUIRED_MESSAGE = "Confirmed case facts are required before generating treatment plans."


class ConfirmedFactsRequiredError(Exception):
    error = "CONFIRMED_FACTS_REQUIRED"
    message = CONFIRMED_FACTS_REQUIRED_MESSAGE


def generate_treatment_plans(case_id: str) -> dict:
    case = get_case(case_id)
    perspective = str(case.get("trade_perspective") or "SELLER").upper()
    conflicts = _safe_collection(get_field_conflicts, case_id)
    high_conflicts = [conflict for conflict in conflicts if conflict.get("severity") == "High" and conflict.get("status") == "OPEN"]
    try:
        facts = get_confirmed_facts(case_id)
    except KeyError:
        if not high_conflicts:
            raise ConfirmedFactsRequiredError() from None
        return _generate_conflict_safe_plan(case_id, case, high_conflicts)
    risk_summary = _safe_list_item("risk_summary", case_id) or {"triggered": False, "trigger_events": [], "exposures": []}
    relevance_results = _safe_list_item("relevance_results", case_id) or []
    actions = _safe_list_item("actions", case_id) or []
    obligations = _safe_collection(get_obligations, case_id)
    gaps = _safe_collection(get_information_gaps, case_id)
    drafts = _safe_collection(get_action_drafts, case_id)

    high_obligations = [
        obligation
        for obligation in obligations
        if obligation.get("severity") == "High" and str(obligation.get("status", "")).upper() == "OPEN"
    ]
    exposures = [exposure.get("category") for exposure in risk_summary.get("exposures", []) if exposure.get("category")]
    relevant_events = [result.get("title") for result in relevance_results if result.get("classification") == "Relevant"]
    warning = "Unresolved high-severity conflicts exist; avoid high-cost treatment until conflicts are resolved." if high_conflicts else ""

    recommended_type = _recommended_plan_type(case.get("status"), high_conflicts, high_obligations, exposures, gaps)
    plan_inputs = {
        "case": case,
        "facts": facts,
        "risk_summary": risk_summary,
        "actions": actions,
        "obligations": obligations,
        "gaps": gaps,
        "drafts": drafts,
        "high_conflicts": high_conflicts,
        "high_obligations": high_obligations,
        "exposures": exposures,
        "relevant_events": relevant_events,
        "warning": warning,
        "conflict_safe_mode": False,
        "perspective": perspective,
        "incoterm_basis": "CIF" if str(case.get("incoterm") or "").upper() == "CIF" else str(case.get("incoterm") or ""),
    }

    plans = [
        _build_plan(case_id, "PLAN-001", "LOW_COST", recommended_type, plan_inputs),
        _build_plan(case_id, "PLAN-002", "BALANCED", recommended_type, plan_inputs),
        _build_plan(case_id, "PLAN-003", "MAX_PROTECTION", recommended_type, plan_inputs),
    ]

    for plan in plans:
        save_item("treatment_plan", _plan_key(case_id, plan["plan_id"]), plan, case_id)
        for residual in plan["residual_risks"]:
            save_item("residual_risk", _residual_key(case_id, residual["residual_risk_id"]), residual, case_id)

    recommended_plan = next(plan for plan in plans if plan["status"] == "RECOMMENDED")
    return {
        "case_id": case_id,
        "recommended_plan_id": recommended_plan["plan_id"],
        "plans": plans,
        "conflict_safe_mode": False,
        "allowed_plan_types": ["LOW_COST", "BALANCED", "MAX_PROTECTION"],
    }


def _generate_conflict_safe_plan(case_id: str, case: dict, high_conflicts: list[dict]) -> dict:
    facts = get_best_case_facts(case_id)
    inputs = {
        "case": case,
        "facts": facts,
        "risk_summary": {"triggered": False, "trigger_events": [], "exposures": []},
        "actions": [],
        "obligations": [],
        "gaps": [],
        "drafts": [],
        "high_conflicts": high_conflicts,
        "high_obligations": [],
        "exposures": [],
        "relevant_events": [],
        "warning": "Unresolved high-severity conflicts exist; only conflict-resolution treatment is allowed.",
        "conflict_safe_mode": True,
        "perspective": str(case.get("trade_perspective") or "SELLER").upper(),
        "incoterm_basis": "CIF" if str(case.get("incoterm") or "").upper() == "CIF" else str(case.get("incoterm") or ""),
    }
    plan = _build_plan(case_id, "PLAN-001", "LOW_COST", "LOW_COST", inputs)
    save_item("treatment_plan", _plan_key(case_id, plan["plan_id"]), plan, case_id)
    for residual in plan["residual_risks"]:
        save_item("residual_risk", _residual_key(case_id, residual["residual_risk_id"]), residual, case_id)
    return {
        "case_id": case_id,
        "recommended_plan_id": plan["plan_id"],
        "plans": [plan],
        "conflict_safe_mode": True,
        "allowed_plan_types": ["LOW_COST"],
    }


def list_treatment_plans(case_id: str) -> list[dict]:
    get_case(case_id)
    plans = [plan for plan in list_items("treatment_plan", case_id) if isinstance(plan, dict)]
    return sorted(plans, key=lambda plan: plan.get("plan_id", ""))


def get_treatment_plan(case_id: str, plan_id: str) -> dict:
    for plan in list_treatment_plans(case_id):
        if plan.get("plan_id") == plan_id:
            return plan
    raise KeyError(plan_id)


def select_treatment_plan(case_id: str, plan_id: str) -> dict:
    selected = None
    for plan in list_treatment_plans(case_id):
        if plan.get("plan_id") == plan_id:
            plan["status"] = "SELECTED"
            plan["updated_at"] = _now()
            selected = plan
        elif plan.get("status") == "SELECTED":
            plan["status"] = "DRAFT"
            plan["updated_at"] = _now()
        save_item("treatment_plan", _plan_key(case_id, plan["plan_id"]), plan, case_id)
    if not selected:
        raise KeyError(plan_id)
    return selected


def archive_treatment_plan(case_id: str, plan_id: str) -> dict:
    plan = get_treatment_plan(case_id, plan_id)
    plan["status"] = "ARCHIVED"
    plan["updated_at"] = _now()
    save_item("treatment_plan", _plan_key(case_id, plan_id), plan, case_id)
    return plan


def generate_approval_package(case_id: str, plan_id: str) -> dict:
    plan = get_treatment_plan(case_id, plan_id)
    package_id = _next_approval_id(case_id)
    now = _now()
    conflict_safe_mode = bool(plan.get("conflict_safe_mode"))
    title = f"Approval Package - {plan['plan_name']}"
    summary_prefix = ""
    approval_scope = "EXECUTION_APPROVAL"
    if conflict_safe_mode:
        title = f"Conflict Resolution Package - {plan['plan_name']}"
        summary_prefix = "Conflict-safe package only: this is not approval for LC amendment, insurance, routing, payment, or external execution. "
        approval_scope = "CONFLICT_RESOLUTION_ONLY"
    package = {
        "approval_package_id": package_id,
        "case_id": case_id,
        "plan_id": plan_id,
        "title": title,
        "summary": (
            f"{summary_prefix}{plan['plan_name']} is proposed because {plan['rationale']} "
            f"It covers {len(plan['covered_risks'])} risks and leaves {len(plan['residual_risks'])} residual risks for monitoring."
        ),
        "recommended_plan_name": plan["plan_name"],
        "estimated_cost_level": plan["estimated_cost_level"],
        "estimated_cost_amount": plan["estimated_cost_amount"],
        "estimated_cost_currency": plan["estimated_cost_currency"],
        "covered_risks": plan["covered_risks"],
        "residual_risks": [risk["risk_title"] for risk in plan["residual_risks"]],
        "required_actions": plan["required_actions"],
        "approval_roles": plan["approval_roles"],
        "approval_status": "DRAFT",
        "approval_scope": approval_scope,
        "conflict_safe_mode": conflict_safe_mode,
        "decision_note": None,
        "created_at": now,
        "updated_at": now,
    }
    save_item("approval_package", _approval_key(case_id, package_id), package, case_id)
    return package


def list_approval_packages(case_id: str) -> list[dict]:
    get_case(case_id)
    packages = [package for package in list_items("approval_package", case_id) if isinstance(package, dict)]
    return sorted(packages, key=lambda package: package.get("approval_package_id", ""))


def update_approval_status(case_id: str, approval_package_id: str, status: str, note: str | None = None) -> dict:
    if status not in VALID_APPROVAL_STATUSES:
        raise ValueError(f"Unsupported approval status: {status}")
    for package in list_approval_packages(case_id):
        if package.get("approval_package_id") == approval_package_id:
            package["approval_status"] = status
            package["decision_note"] = note
            package["updated_at"] = _now()
            save_item("approval_package", _approval_key(case_id, approval_package_id), package, case_id)
            return package
    raise KeyError(approval_package_id)


def _build_plan(case_id: str, plan_id: str, plan_type: str, recommended_type: str, inputs: dict) -> dict:
    now = _now()
    profile = _plan_profile(plan_type, inputs)
    linked_actions = [action.get("action_id") for action in inputs["actions"] if action.get("action_id")]
    linked_gaps = [gap.get("gap_id") for gap in inputs["gaps"] if gap.get("gap_id")]
    linked_obligations = [obligation.get("obligation_id") for obligation in inputs["obligations"] if obligation.get("obligation_id")]
    residual_risks = _residual_risks(case_id, plan_id, plan_type, inputs)
    rationale = profile["rationale"]
    if inputs["warning"]:
        rationale = f"{inputs['warning']} {rationale}"

    return {
        "plan_id": plan_id,
        "case_id": case_id,
        "plan_type": plan_type,
        "plan_name": profile["plan_name"],
        "summary": profile["summary"],
        "recommendation_level": "Recommended" if plan_type == recommended_type else profile["recommendation_level"],
        "estimated_cost_level": profile["estimated_cost_level"],
        "estimated_cost_amount": profile["estimated_cost_amount"],
        "estimated_cost_currency": "USD",
        "estimated_time_to_execute": profile["estimated_time_to_execute"],
        "approval_required": profile["approval_required"],
        "approval_roles": profile["approval_roles"],
        "covered_risks": profile["covered_risks"],
        "residual_risks": residual_risks,
        "required_actions": profile["required_actions"],
        "linked_action_ids": linked_actions,
        "linked_gap_ids": linked_gaps,
        "linked_obligation_ids": linked_obligations,
        "assumptions": profile["assumptions"],
        "preconditions": profile["preconditions"],
        "recheck_triggers": profile["recheck_triggers"],
        "rationale": rationale,
        "status": "RECOMMENDED" if plan_type == recommended_type else "DRAFT",
        "conflict_safe_mode": inputs.get("conflict_safe_mode", False),
        "perspective": inputs.get("perspective", "SELLER"),
        "incoterm_basis": inputs.get("incoterm_basis", ""),
        "created_at": now,
        "updated_at": now,
    }


def _plan_profile(plan_type: str, inputs: dict) -> dict:
    exposure_text = inputs["exposures"] or ["Shipping", "Port Operation", "LC Deadline"]
    perspective = inputs.get("perspective", "SELLER")
    if plan_type == "LOW_COST":
        if inputs.get("conflict_safe_mode"):
            return {
                "plan_name": "Low-cost Conflict Resolution Plan",
                "summary": "Resolve high-severity data conflicts before any irreversible trade, finance, or execution action.",
                "recommendation_level": "Recommended",
                "estimated_cost_level": "Low",
                "estimated_cost_amount": 500,
                "estimated_time_to_execute": "Same day",
                "approval_required": False,
                "approval_roles": [],
                "covered_risks": ["Document data conflict", "Premature execution risk"],
                "required_actions": [
                    "Review conflicting field evidence across uploaded documents",
                    "Request corrected or authoritative document evidence",
                    "Resolve high-severity conflicts before confirming case facts",
                    "Do not submit LC, insurance, routing, payment, or external execution actions until conflicts are resolved",
                ],
                "assumptions": ["Critical trade facts are not yet reliable enough for full treatment planning."],
                "preconditions": ["User reviews and resolves high-severity field conflicts."],
                "recheck_triggers": ["High conflict is resolved", "New authoritative document is uploaded", "Counterparty confirms corrected value"],
                "rationale": "This option is limited to conflict resolution and avoids irreversible execution while facts are disputed.",
            }
        if perspective == "BUYER":
            return {
                "plan_name": "Low-cost Buyer Arrival Monitoring Plan",
                "summary": "Confirm arrival, import, and destination-port facts before triggering costly buyer-side action.",
                "recommendation_level": "Conservative",
                "estimated_cost_level": "Low",
                "estimated_cost_amount": 500,
                "estimated_time_to_execute": "Same day",
                "approval_required": False,
                "approval_roles": [],
                "covered_risks": ["Arrival delay uncertainty", "Import readiness uncertainty", *exposure_text[:2]],
                "required_actions": [
                    "Request updated shipment status from seller",
                    "Monitor destination port congestion",
                    "Prepare import customs documents",
                    "Review demurrage and storage exposure",
                ],
                "assumptions": ["Cargo arrival and port facts still need current confirmation."],
                "preconditions": ["Buyer team can contact seller, customs broker, and port agent."],
                "recheck_triggers": ["ETA slips by 3 or more days", "Port congestion remains active", "Demurrage clock is likely to start"],
                "rationale": "This option keeps buyer-side cost low while closing arrival and import information gaps.",
            }
        return {
            "plan_name": "Low-cost Monitoring Plan",
            "summary": "Confirm latest external facts and continue monitoring before triggering costly actions.",
            "recommendation_level": "Conservative",
            "estimated_cost_level": "Low",
            "estimated_cost_amount": 500,
            "estimated_time_to_execute": "Same day",
            "approval_required": False,
            "approval_roles": [],
            "covered_risks": ["ETA uncertainty", "Port operation uncertainty", *exposure_text[:2]],
            "required_actions": [
                "Contact carrier to confirm latest ETA",
                "Contact port agent to confirm port operation status",
                "Notify internal team to continue monitoring",
                "Do not amend LC until updated facts are confirmed",
            ],
            "assumptions": ["Operational facts are not yet fully confirmed."],
            "preconditions": ["Trade team can contact carrier and port agent."],
            "recheck_triggers": ["ETA slips by 3 or more days", "Port disruption remains active", "Buyer requests formal notice"],
            "rationale": "This option keeps cost low while closing information gaps.",
        }
    if plan_type == "MAX_PROTECTION":
        if perspective == "BUYER":
            return {
                "plan_name": "Maximum Buyer Protection Plan",
                "summary": "Prepare import, demurrage, inland delivery, and insurance-claim readiness immediately.",
                "recommendation_level": "Protective",
                "estimated_cost_level": "High",
                "estimated_cost_amount": 15000,
                "estimated_time_to_execute": "1-2 business days",
                "approval_required": True,
                "approval_roles": ["Business Head", "Import Operations", "Management"],
                "covered_risks": ["Arrival delay risk", "Destination port delay risk", "Demurrage/storage risk", "Import clearance risk"],
                "required_actions": [
                    "Request formal shipment status from seller",
                    "Coordinate customs broker / port agent",
                    "Reserve inland delivery capacity",
                    "Review demurrage and storage exposure",
                    "Review insurance claim route if cargo damage is suspected",
                ],
                "assumptions": ["Buyer-side destination and import exposure is material."],
                "preconditions": ["Management approves higher-cost destination-side protective action."],
                "recheck_triggers": ["Port agent confirms berth delay", "Customs documents remain incomplete", "Cargo damage is suspected"],
                "rationale": "This option maximizes buyer protection after CIF risk transfer and destination-side disruption.",
            }
        return {
            "plan_name": "Maximum Protection Plan",
            "summary": "Prepare protective trade finance, insurance, carrier, and buyer-facing actions immediately.",
            "recommendation_level": "Protective",
            "estimated_cost_level": "High",
            "estimated_cost_amount": 15000,
            "estimated_time_to_execute": "1-2 business days",
            "approval_required": True,
            "approval_roles": ["Business Head", "Trade Finance", "Management"],
            "covered_risks": ["LC deadline risk", "Shipment delay risk", "Port disruption risk", "Payment timeline risk"],
            "required_actions": [
                "Prepare LC amendment request",
                "Ask carrier for alternative routing or priority space",
                "Contact insurance broker to confirm coverage",
                "Notify finance team about payment and cash-flow impact",
                "Send formal buyer risk notice draft",
            ],
            "assumptions": ["A material delay or deadline exposure is plausible."],
            "preconditions": ["Management approves higher-cost protective action."],
            "recheck_triggers": ["LC amendment rejected", "Insurance coverage limited", "Alternative space unavailable"],
            "rationale": "This option maximizes protection against deadline, port, and payment exposure.",
        }
    if perspective == "BUYER":
        return {
            "plan_name": "Balanced Buyer Risk Treatment Plan",
            "summary": "Confirm shipment facts while preparing import and destination-side actions for fast escalation.",
            "recommendation_level": "Balanced",
            "estimated_cost_level": "Medium",
            "estimated_cost_amount": 5000,
            "estimated_time_to_execute": "1 business day",
            "approval_required": True,
            "approval_roles": ["Import Operations Lead", "Business Owner"],
            "covered_risks": ["Arrival delay risk", "Port congestion risk", "Demurrage/storage exposure"],
            "required_actions": [
                "Request updated shipment status from seller",
                "Monitor destination port congestion",
                "Coordinate customs broker / port agent",
                "Prepare import customs documents",
                "Track inland delivery planning",
            ],
            "assumptions": ["Relevant event signals are credible but some seller or port confirmations remain open."],
            "preconditions": ["Seller, customs broker, and port updates are requested immediately."],
            "recheck_triggers": ["Confirmed ETA delay exceeds inventory tolerance", "Port congestion continues", "Customs broker flags clearance blocker"],
            "rationale": "This option balances cost control with readiness for buyer-side import and destination exposure.",
        }
    return {
        "plan_name": "Balanced Risk Treatment Plan",
        "summary": "Confirm facts while preparing finance and buyer-facing actions for fast escalation.",
        "recommendation_level": "Balanced",
        "estimated_cost_level": "Medium",
        "estimated_cost_amount": 5000,
        "estimated_time_to_execute": "1 business day",
        "approval_required": True,
        "approval_roles": ["Trade Finance Lead", "Business Owner"],
        "covered_risks": ["Shipment delay risk", "Port operation risk", "LC deadline risk"],
        "required_actions": [
            "Contact carrier to confirm latest ETA",
            "Contact port agent to confirm operation status",
            "Ask trade finance team to assess LC amendment need",
            "Prepare buyer delay notice draft",
            "Track open information gaps",
        ],
        "assumptions": ["Relevant event signals are credible but some third-party confirmations remain open."],
        "preconditions": ["Carrier and port updates are requested immediately."],
        "recheck_triggers": ["Confirmed ETA delay exceeds LC tolerance", "Port strike continues", "Buyer asks for formal amendment"],
        "rationale": "This option balances cost control with readiness for LC and buyer-facing action.",
    }


def _recommended_plan_type(status: str | None, high_conflicts: list[dict], high_obligations: list[dict], exposures: list[str], gaps: list[dict]) -> str:
    if high_conflicts:
        return "LOW_COST"
    if high_obligations or "LC Deadline" in exposures:
        return "MAX_PROTECTION"
    if status in {"ACTION_REQUIRED", "AT_RISK"}:
        return "BALANCED"
    if gaps:
        return "LOW_COST"
    return "BALANCED"


def _residual_risks(case_id: str, plan_id: str, plan_type: str, inputs: dict) -> list[dict]:
    if inputs.get("perspective") == "BUYER":
        templates = [
            (
                "Seller shipment update may remain incomplete",
                "Buyer-side planning still depends on timely seller and carrier information.",
                "Medium",
                "The plan requests updates but cannot force seller response timing.",
                "Seller does not provide updated shipment status within one business day.",
                "Procurement",
            ),
            (
                "Destination port delay may continue",
                "Port congestion and berth availability can change after the current assessment.",
                "High" if plan_type != "LOW_COST" else "Medium",
                "The plan can coordinate broker and port agent activity but cannot control port operations.",
                "Port agent reports continued congestion or storage exposure.",
                "Import Operations",
            ),
            (
                "Insurance claim path may depend on cargo condition evidence",
                "A claim can only progress if cargo damage or loss is evidenced after arrival.",
                "Medium",
                "The plan prepares the claim route but cannot determine claim validity before cargo inspection.",
                "Cargo damage is reported or survey evidence is requested.",
                "Insurance",
            ),
        ]
    else:
        templates = [
            (
                "Buyer or bank may reject LC amendment",
                "Any LC change depends on buyer and bank agreement.",
                "High" if plan_type != "LOW_COST" else "Medium",
                "The plan can prepare the request but cannot force third-party acceptance.",
                "LC amendment is rejected or not answered within one business day.",
                "Trade Finance",
            ),
            (
                "Port disruption duration remains uncertain",
                "Port operation status can change after the current assessment.",
                "Medium",
                "The plan relies on port agent updates and cannot control labor or congestion events.",
                "Port agent reports continued disruption or limited berth availability.",
                "Logistics",
            ),
            (
                "Carrier ETA may continue to slip",
                "The vessel schedule can change after the initial carrier confirmation.",
                "Medium" if plan_type == "MAX_PROTECTION" else "High",
                "The plan requests updates but cannot guarantee vessel performance.",
                "Carrier updates ETA later than the latest shipment or LC tolerance window.",
                "Trade Ops",
            ),
        ]
    if inputs["high_conflicts"]:
        templates.insert(
            0,
            (
                "Unresolved high-severity field conflict",
                "Critical trade facts conflict across documents and must be resolved before high-cost action.",
                "High",
                "Treatment options cannot fully cover risk while operative facts are disputed.",
                "User resolves high-severity conflicts or new document evidence is uploaded.",
                "Trade Ops",
            ),
        )

    now = _now()
    return [
        {
            "residual_risk_id": f"RR-{plan_id.split('-')[-1]}-{index:03d}",
            "case_id": case_id,
            "plan_id": plan_id,
            "risk_title": title,
            "description": description,
            "severity": severity,
            "reason_not_fully_covered": reason,
            "monitoring_trigger": trigger,
            "owner_role": owner,
            "status": "OPEN",
            "perspective": inputs.get("perspective", "SELLER"),
            "incoterm_basis": inputs.get("incoterm_basis", ""),
            "created_at": now,
            "updated_at": now,
        }
        for index, (title, description, severity, reason, trigger, owner) in enumerate(templates, start=1)
    ]


def _next_approval_id(case_id: str) -> str:
    existing = list_approval_packages(case_id)
    return f"APPROVAL-{len(existing) + 1:03d}"


def _safe_collection(factory, case_id: str) -> list[dict]:
    try:
        return factory(case_id)
    except KeyError:
        return []


def _safe_list_item(namespace: str, case_id: str):
    matches = list_items(namespace, case_id)
    if not matches:
        return None
    if len(matches) == 1:
        return matches[0]
    return matches


def _plan_key(case_id: str, plan_id: str) -> str:
    return f"{case_id}:{plan_id}"


def _residual_key(case_id: str, residual_risk_id: str) -> str:
    return f"{case_id}:{residual_risk_id}"


def _approval_key(case_id: str, approval_package_id: str) -> str:
    return f"{case_id}:{approval_package_id}"


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
