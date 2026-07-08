from app.services.case_service import get_case
from app.services.document_service import (
    get_action_drafts,
    get_confirmed_facts,
    get_documents,
    get_extracted_fields,
    get_field_conflicts,
)
from app.services.agent_run_service import get_agent_runs


def get_workflow_state(case_id: str) -> dict:
    case = get_case(case_id)
    documents = get_documents(case_id)
    fields = get_extracted_fields(case_id)
    conflicts = get_field_conflicts(case_id)
    high_open = [conflict for conflict in conflicts if conflict["severity"] == "High" and conflict["status"] == "OPEN"]
    try:
        confirmed = get_confirmed_facts(case_id)
    except KeyError:
        confirmed = None
    runs = get_agent_runs(case_id)
    drafts = get_action_drafts(case_id)

    steps = [
        {"name": "Upload Documents", "status": "COMPLETED" if documents else "IN_PROGRESS"},
        {"name": "Review Extracted Fields", "status": _review_status(fields)},
        {"name": "Resolve Conflicts", "status": _resolve_conflicts_status(conflicts, high_open)},
        {"name": "Confirm Case Facts", "status": "COMPLETED" if confirmed else ("BLOCKED" if high_open else "NOT_STARTED")},
        {"name": "Run Agent Monitoring", "status": "COMPLETED" if runs else ("NOT_STARTED" if confirmed else "NOT_STARTED")},
        {"name": "Review Obligations / Gaps / Drafts", "status": "NEEDS_REVIEW" if drafts else "NOT_STARTED"},
        {"name": "Continue Monitoring", "status": "COMPLETED" if case.get("status") == "MONITORING" else "NOT_STARTED"},
    ]
    current = next((step["name"] for step in steps if step["status"] in {"IN_PROGRESS", "NEEDS_REVIEW", "BLOCKED"}), steps[-1]["name"])
    return {"case_id": case_id, "current_step": current, "steps": steps}


def _resolve_conflicts_status(conflicts: list[dict], high_open: list[dict]) -> str:
    if high_open:
        return "BLOCKED"
    if conflicts:
        open_conflicts = [conflict for conflict in conflicts if conflict.get("status") == "OPEN"]
        return "NEEDS_REVIEW" if open_conflicts else "COMPLETED"
    return "COMPLETED"


def _review_status(fields: list[dict]) -> str:
    if not fields:
        return "NOT_STARTED"
    if any(field["review_status"] == "PENDING" for field in fields if field.get("requires_confirmation")):
        return "NEEDS_REVIEW"
    return "COMPLETED"
