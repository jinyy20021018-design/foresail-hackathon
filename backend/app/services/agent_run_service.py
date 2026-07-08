from datetime import datetime, timezone
UTC = timezone.utc

from app.services.persistence_service import list_items, save_item, load_item


def save_agent_run(case_id: str, result: dict, run_status: str = "COMPLETED") -> dict:
    now = datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
    exposures = [exposure["category"] for exposure in result.get("risk_summary", {}).get("exposures", [])]
    obligations_at_risk = [
        obligation
        for obligation in result.get("obligations", [])
        if "risk" in obligation.get("current_assessment", "").lower()
        or "compressed" in obligation.get("current_assessment", "").lower()
    ]
    record = {
        "agent_run_id": result["agent_run_id"],
        "case_id": case_id,
        "started_at": result.get("started_at", now),
        "completed_at": now,
        "status_before": result.get("status_before"),
        "status_after": result.get("status_after"),
        "events_scanned": result.get("events_scanned", 0),
        "relevant_count": result.get("relevant_count", 0),
        "watch_count": result.get("watch_count", 0),
        "irrelevant_count": result.get("irrelevant_count", 0),
        "triggered_exposures": exposures,
        "obligations_at_risk_count": len(obligations_at_risk),
        "information_gaps_count": len(result.get("information_gaps", [])),
        "actions_generated_count": len(result.get("actions", [])),
        "drafts_generated_count": len(result.get("action_drafts", [])),
        "summary": result.get("summary", ""),
        "run_status": run_status,
    }
    save_item("agent_run", _run_key(case_id, record["agent_run_id"]), record, case_id)

    trace_records = []
    for step in result.get("trace", []):
        trace = {
            "trace_id": f"TRACE-{case_id}-{record['agent_run_id'].replace('RUN-', '')}-{step['step']:03d}",
            "agent_run_id": record["agent_run_id"],
            "case_id": case_id,
            "step_number": step["step"],
            "step_name": step["name"],
            "tool_or_service": step["tool_or_service"],
            "status": step["status"],
            "input_summary": step.get("input_summary", case_id),
            "output_summary": step["output_summary"],
            "description": step["description"],
            "created_at": now,
        }
        trace_records.append(trace)
        save_item("agent_trace", trace["trace_id"], trace, case_id)
    return record


def get_agent_runs(case_id: str) -> list[dict]:
    return list_items("agent_run", case_id)


def get_agent_run(case_id: str, agent_run_id: str) -> dict:
    direct = load_item("agent_run", _run_key(case_id, agent_run_id))
    if direct and direct.get("case_id") == case_id:
        return direct
    for record in get_agent_runs(case_id):
        if record.get("agent_run_id") == agent_run_id:
            return record
    raise KeyError(agent_run_id)


def get_agent_run_trace(case_id: str, agent_run_id: str) -> list[dict]:
    traces = [trace for trace in list_items("agent_trace", case_id) if trace.get("agent_run_id") == agent_run_id]
    return sorted(traces, key=lambda trace: trace["step_number"])


def _run_key(case_id: str, agent_run_id: str) -> str:
    return f"{case_id}:{agent_run_id}"
