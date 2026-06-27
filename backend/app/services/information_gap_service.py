def detect_information_gaps(case_id: str, facts: dict, relevance_results: list[dict]) -> list[dict]:
    relevant_ids = {result["event_id"] for result in relevance_results if result["classification"] == "Relevant"}
    watch_or_relevant_exposures = {
        exposure
        for result in relevance_results
        if result["classification"] in {"Relevant", "Watch"}
        for exposure in result.get("mapped_exposures", [])
    }
    gaps: list[dict] = []

    if "EVT-001" in relevant_ids or "Shipping" in watch_or_relevant_exposures:
        gaps.append(_gap(case_id, "Need confirmed updated ETA from carrier", "Current ETA delay is based on event feed and requires carrier confirmation before LC amendment decision.", "LC amendment timing", "Logistics", "High"))

    if not facts.get("booking_reference"):
        gaps.append(_gap(case_id, "Need booking reference for outbound inquiry draft", "Carrier inquiry should reference the booking number, but no confirmed booking reference is available.", "Carrier ETA inquiry", "Logistics", "Medium"))

    if not facts.get("lc_expiry_date"):
        gaps.append(_gap(case_id, "Need complete LC expiry confirmation", "LC expiry date is missing from confirmed facts.", "LC deadline assessment", "Trade Finance", "High"))

    if not facts.get("presentation_period_days"):
        gaps.append(_gap(case_id, "Need LC presentation period confirmation", "Presentation period is missing from confirmed facts.", "Document presentation timing", "Trade Finance", "High"))

    if "EVT-002" in relevant_ids or "Port Operation" in watch_or_relevant_exposures:
        gaps.append(_gap(case_id, "Need latest port operation status from freight forwarder", "Bangladesh / Chittagong port disruption requires current local operational confirmation.", "Discharge and inland delivery planning", "Freight Forwarder", "High"))

    return gaps


def _gap(case_id: str, title: str, reason: str, blocks_decision: str, owner_role: str, priority: str) -> dict:
    return {
        "gap_id": "",
        "case_id": case_id,
        "title": title,
        "reason": reason,
        "blocks_decision": blocks_decision,
        "owner_role": owner_role,
        "priority": priority,
        "status": "OPEN",
    }


def assign_gap_ids(gaps: list[dict]) -> list[dict]:
    for index, gap in enumerate(gaps, start=1):
        gap["gap_id"] = f"GAP-{index:03d}"
    return gaps
