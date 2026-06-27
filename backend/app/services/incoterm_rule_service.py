def resolve_cif_responsibility(case: dict) -> dict:
    incoterm = str(case.get("incoterm") or "").strip().upper()
    named_place = (
        case.get("incoterm_named_place")
        or case.get("port_of_discharge")
        or case.get("final_destination")
        or ""
    )
    is_cif = incoterm.startswith("CIF")
    warnings: list[str] = []
    if not is_cif:
        warnings.append("INCOTERM_NOT_CIF")
    if is_cif and not named_place:
        warnings.append("CIF_NAMED_DESTINATION_PORT_MISSING")

    return {
        "incoterm": "CIF" if is_cif else (incoterm or "UNKNOWN"),
        "named_destination_port": named_place,
        "risk_transfer_point": "On board vessel at port of loading" if is_cif else "Not determined",
        "cost_responsibility_until": named_place if is_cif else "Not determined",
        "seller_responsibilities": [
            "Arrange carriage to named destination port",
            "Procure minimum cargo insurance cover",
            "Provide commercial invoice and transport documents",
            "Load goods on board at port of loading",
        ] if is_cif else [],
        "buyer_responsibilities": [
            "Bear cargo risk after goods are on board",
            "Handle import clearance unless otherwise agreed",
            "Take delivery at destination",
            "Manage downstream disruption after destination arrival",
        ] if is_cif else [],
        "warnings": warnings,
    }
