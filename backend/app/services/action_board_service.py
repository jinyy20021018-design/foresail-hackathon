ACTION_RULES = {
    "Shipping": [
        {
            "title": "Contact carrier to confirm latest ETA and delay reason",
            "owner_role": "Logistics",
            "priority": "High",
            "deadline": "Today",
        },
        {
            "title": "Request alternative routing or discharge options",
            "owner_role": "Logistics",
            "priority": "Medium",
            "deadline": "Today",
        },
    ],
    "LC Deadline": [
        {
            "title": "Review whether delay affects latest shipment date or document presentation",
            "owner_role": "Trade Finance",
            "priority": "High",
            "deadline": "Today",
        },
        {
            "title": "Prepare LC amendment request if shipment timing becomes non-compliant",
            "owner_role": "Trade Finance",
            "priority": "High",
            "deadline": "T+1",
        },
    ],
    "Port Operation": [
        {
            "title": "Check Bangladesh / Chittagong port operation status",
            "owner_role": "Logistics",
            "priority": "High",
            "deadline": "Today",
        },
        {
            "title": "Ask freight forwarder for congestion and discharge alternatives",
            "owner_role": "Freight Forwarder",
            "priority": "Medium",
            "deadline": "Today",
        },
    ],
    "Payment Timeline": [
        {
            "title": "Update expected payment and cashflow timeline",
            "owner_role": "Finance",
            "priority": "Medium",
            "deadline": "T+1",
        },
        {
            "title": "Notify finance team of possible working capital impact",
            "owner_role": "Finance",
            "priority": "Medium",
            "deadline": "T+1",
        },
    ],
}

CIF_ACTION_RULES = {
    "SELLER": [
        ("Notify buyer of shipment / delay status", "Trade Ops", "High", "Today", "SHARED"),
        ("Request updated ETA from carrier", "Logistics", "High", "Today", "SELLER"),
        ("Check LC latest shipment date", "Trade Finance", "High", "Today", "SELLER"),
        ("Check LC presentation period", "Trade Finance", "High", "Today", "SELLER"),
        ("Prepare or verify bill of lading", "Shipping Documentation", "High", "Today", "SELLER"),
        ("Prepare or verify insurance certificate", "Insurance", "High", "Today", "SELLER"),
        ("Consider LC amendment request if shipment deadline is at risk", "Trade Finance", "High", "T+1", "SELLER"),
    ],
    "BUYER": [
        ("Request updated shipment status from seller", "Procurement", "High", "Today", "SELLER"),
        ("Monitor destination port congestion", "Logistics", "High", "Today", "BUYER"),
        ("Prepare import customs documents", "Import Operations", "High", "T+1", "BUYER"),
        ("Coordinate customs broker / port agent", "Import Operations", "High", "Today", "BUYER"),
        ("Review demurrage and storage exposure", "Logistics", "High", "Today", "BUYER"),
        ("Review insurance claim procedure if cargo damage is suspected", "Insurance", "Medium", "T+1", "BUYER"),
    ],
}


def generate_actions(risk_summary: dict) -> list[dict]:
    seen_titles: set[str] = set()
    actions: list[dict] = []

    for exposure in risk_summary.get("exposures", []):
        category = exposure["category"]
        perspective = exposure.get("party_perspective") or risk_summary.get("trade_perspective") or "SELLER"
        incoterm_basis = exposure.get("incoterm_basis") or risk_summary.get("incoterm_basis") or ""
        if incoterm_basis == "CIF" and perspective in CIF_ACTION_RULES:
            for title, owner_role, priority, deadline, responsible_party in CIF_ACTION_RULES[perspective]:
                if not _is_relevant_cif_action(title, exposure):
                    continue
                key = f"{perspective}:{title}"
                if key in seen_titles:
                    continue
                seen_titles.add(key)
                actions.append(_action(len(actions), title, owner_role, priority, deadline, category, perspective, responsible_party, "CIF"))
            continue

        for rule in ACTION_RULES.get(category, []):
            key = f"{perspective}:{rule['title']}"
            if key in seen_titles:
                continue
            seen_titles.add(key)
            actions.append(
                _action(
                    len(actions),
                    rule["title"],
                    rule["owner_role"],
                    rule["priority"],
                    rule["deadline"],
                    category,
                    perspective,
                    "UNKNOWN",
                    incoterm_basis,
                )
            )

    return actions


def _action(index: int, title: str, owner_role: str, priority: str, deadline: str, exposure: str, perspective: str, responsible_party: str, incoterm_basis: str) -> dict:
    return {
        "action_id": f"ACT-{index + 1:03d}",
        "title": title,
        "owner_role": owner_role,
        "priority": priority,
        "deadline": deadline,
        "status": "Open",
        "related_exposure": exposure,
        "party_perspective": perspective,
        "responsible_party": responsible_party,
        "incoterm_basis": incoterm_basis,
    }


def _is_relevant_cif_action(title: str, exposure: dict) -> bool:
    scenario = exposure.get("cif_scenario")
    category = exposure.get("category")
    if scenario == "destination_port_congestion":
        return title not in {"Check LC latest shipment date", "Check LC presentation period", "Consider LC amendment request if shipment deadline is at risk"}
    if scenario == "shipment_delay_before_loading":
        return title not in {"Monitor destination port congestion", "Coordinate customs broker / port agent", "Review demurrage and storage exposure"}
    if category == "LC Deadline":
        return title in {
            "Notify buyer of shipment / delay status",
            "Check LC latest shipment date",
            "Check LC presentation period",
            "Prepare or verify bill of lading",
            "Prepare or verify insurance certificate",
            "Consider LC amendment request if shipment deadline is at risk",
            "Request updated shipment status from seller",
        }
    return True
