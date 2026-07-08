def map_event_to_exposures(event: dict, classification: str, case: dict) -> list[str]:
    if classification == "Irrelevant":
        return []

    event_type = event["type"]
    exposures: list[str] = []

    if event_type == "VESSEL_DELAY":
        exposures.extend(["Shipping", "Payment Timeline"])
        if int(event.get("delay_days") or 0) >= 3:
            exposures.append("LC Deadline")

    elif event_type in {"PORT_STRIKE", "PORT_DISRUPTION"}:
        exposures.extend(["Port Operation", "Shipping", "Payment Timeline"])

    elif event_type == "WEATHER":
        exposures.append("Shipping")
        affected_ports = set(event.get("affected_ports") or [])
        if case["port_of_loading"] in affected_ports:
            exposures.append("LC Deadline")

    elif event_type == "SECURITY":
        from app.services.route_region_service import event_text_mentions_corridor, merge_watched_route_regions

        corridors = set(merge_watched_route_regions(case))
        if event.get("affected_region") in corridors or event_text_mentions_corridor(event, corridors):
            exposures.append("Shipping")

    elif event_type == "PORT_CONGESTION":
        affected_ports = set(event.get("affected_ports") or [])
        watched_ports = {case["port_of_loading"], case["port_of_discharge"], case["final_destination"]}
        if affected_ports.intersection(watched_ports):
            exposures.extend(["Port Operation", "Shipping"])

    return list(dict.fromkeys(exposures))


def summarize_exposures(case: dict, events: list[dict], relevance_results: list[dict]) -> dict:
    exposure_map: dict[str, dict] = {}
    trigger_events: list[str] = []
    watch_events: list[str] = []
    event_by_id = {event.get("event_id"): event for event in events}
    perspectives = ["SELLER", "BUYER"] if _is_cif(case) else [str(case.get("trade_perspective") or "SELLER").upper()]

    for result in relevance_results:
        if result["classification"] == "Relevant":
            trigger_events.append(result["event_id"])
        elif result["classification"] == "Watch":
            watch_events.append(result["event_id"])

        for exposure in result["mapped_exposures"]:
            for perspective in perspectives:
                details = _cif_perspective_details(case, event_by_id.get(result["event_id"], {}), exposure, perspective)
                key = f"{perspective}:{exposure}"
                current = exposure_map.setdefault(
                    key,
                    {
                        "category": exposure,
                        "impact": details["impact"],
                        "severity": details["severity"],
                        "party_perspective": perspective,
                        "affected_party": details["affected_party"],
                        "responsible_party": details["responsible_party"],
                        "incoterm_basis": "CIF" if _is_cif(case) else case.get("incoterm", ""),
                        "cif_scenario": details["scenario"],
                        "evidence_event_ids": [],
                        "trigger_event_ids": [],
                        "watch_event_ids": [],
                    },
                )
                current["evidence_event_ids"].append(result["event_id"])

                if result["classification"] == "Relevant":
                    current["trigger_event_ids"].append(result["event_id"])
                    current["severity"] = _max_severity(current["severity"], details["relevant_severity"])
                elif result["classification"] == "Watch":
                    current["watch_event_ids"].append(result["event_id"])

    return {
        "triggered": bool(trigger_events),
        "trigger_events": trigger_events,
        "watch_events_considered": watch_events,
        "exposures": list(exposure_map.values()),
    }


def _impact_for_exposure(exposure: str) -> str:
    impacts = {
        "Shipping": "Shipment timing or routing may be disrupted.",
        "LC Deadline": "Delay may create latest shipment or presentation timing risk under the LC.",
        "Port Operation": "Port disruption may slow discharge or inland delivery.",
        "Payment Timeline": "ETA or discharge delay may shift expected payment and cashflow timing.",
    }
    return impacts.get(exposure, "Trade case exposure requires review.")


def _is_cif(case: dict) -> bool:
    return str(case.get("incoterm") or "").strip().upper() == "CIF"


def _cif_perspective_details(case: dict, event: dict, exposure: str, perspective: str) -> dict:
    if not _is_cif(case):
        return {
            "impact": _impact_for_exposure(exposure),
            "severity": "Medium",
            "relevant_severity": "High",
            "affected_party": perspective,
            "responsible_party": "UNKNOWN",
            "scenario": "general trade exposure",
        }

    scenario = _cif_scenario(case, event)
    if scenario == "shipment_delay_before_loading":
        if perspective == "SELLER":
            return _details(
                "High",
                "High",
                "SELLER",
                "SELLER",
                scenario,
                "Latest shipment date, LC compliance, document presentation, buyer notification, and possible LC amendment risk.",
            )
        return _details(
            "Medium",
            "Medium",
            "BUYER",
            "SELLER",
            scenario,
            "Delayed cargo arrival may affect procurement or inventory planning; request updated shipment status from seller.",
        )
    if scenario == "after_loading_voyage_delay":
        if perspective == "SELLER" and exposure == "LC Deadline":
            return _details(
                "High",
                "High",
                "SELLER",
                "SELLER",
                scenario,
                "LC latest shipment, document presentation, insurance certificate readiness, and buyer notification may require seller action.",
            )
        if perspective == "BUYER":
            return _details(
                "High",
                "High",
                "BUYER",
                "BUYER",
                scenario,
                "Cargo risk has transferred after loading; monitor arrival delay, import planning, and possible insurance claim path.",
            )
        return _details(
            "Medium",
            "Medium",
            "SELLER",
            "SELLER",
            scenario,
            "Seller should manage carrier communication, document accuracy, insurance document readiness, and buyer notification.",
        )
    if scenario == "destination_port_congestion":
        if perspective == "BUYER":
            return _details(
                "High",
                "High",
                "BUYER",
                "BUYER",
                scenario,
                "Destination port delay, demurrage/storage risk, import clearance delay, and inland delivery delay exposure.",
            )
        return _details(
            "Medium",
            "Medium",
            "SELLER",
            "SHARED",
            scenario,
            "Seller has arranged freight and insurance but should notify buyer and provide compliant shipping documents.",
        )
    return _details("Medium", "High", perspective, "SHARED", scenario, _impact_for_exposure(exposure))


def _cif_scenario(case: dict, event: dict) -> str:
    event_type = event.get("type") or event.get("event_type")
    affected_ports = set(event.get("affected_ports") or [])
    loading_port = case.get("port_of_loading")
    destination_ports = {case.get("port_of_discharge"), case.get("final_destination"), case.get("incoterm_named_place")}
    destination_ports.discard(None)
    destination_ports.discard("")
    if event_type == "WEATHER" and loading_port in affected_ports:
        return "shipment_delay_before_loading"
    if event_type == "VESSEL_DELAY":
        return "after_loading_voyage_delay"
    if event_type in {"PORT_CONGESTION", "PORT_STRIKE", "PORT_DISRUPTION"} and affected_ports.intersection(destination_ports):
        return "destination_port_congestion"
    return "general_cif_exposure"


def _details(severity: str, relevant_severity: str, affected_party: str, responsible_party: str, scenario: str, impact: str) -> dict:
    return {
        "severity": severity,
        "relevant_severity": relevant_severity,
        "affected_party": affected_party,
        "responsible_party": responsible_party,
        "scenario": scenario,
        "impact": impact,
    }


def _max_severity(current: str, candidate: str) -> str:
    order = {"Low": 1, "Medium": 2, "High": 3}
    return candidate if order.get(candidate, 0) > order.get(current, 0) else current
