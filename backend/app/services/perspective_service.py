from app.services.case_service import get_case, set_trade_perspective
from app.services.incoterm_rule_service import resolve_cif_responsibility

SUPPORTED_PERSPECTIVES = {"SELLER", "BUYER"}
UNSUPPORTED_PERSPECTIVE_ERROR = {
    "error": "UNSUPPORTED_PERSPECTIVE",
    "message": "trade_perspective must be SELLER or BUYER.",
}


class UnsupportedPerspectiveError(ValueError):
    pass


def normalize_perspective(perspective: str | None) -> str:
    normalized = str(perspective or "SELLER").strip().upper()
    if normalized not in SUPPORTED_PERSPECTIVES:
        raise UnsupportedPerspectiveError(normalized)
    return normalized


def update_case_perspective(case_id: str, perspective: str) -> dict:
    return set_trade_perspective(case_id, normalize_perspective(perspective))


def perspective_analysis(case_id: str, perspective: str | None = None) -> dict:
    case = get_case(case_id)
    selected = normalize_perspective(perspective or case.get("trade_perspective"))
    responsibility = resolve_cif_responsibility(case)
    if selected == "SELLER":
        focus = [
            "Protect shipment and document compliance before risk transfer.",
            "Track LC latest shipment and presentation obligations.",
            "Prepare buyer and bank notices if shipment timing changes.",
        ]
        residual = [
            "Buyer may still dispute delays if documents or notices are incomplete.",
            "Destination-side disruption may affect payment timing even after shipment.",
        ]
    else:
        focus = [
            "Monitor cargo risk after on-board transfer under CIF.",
            "Check whether insurance and destination handling cover current disruption.",
            "Prepare import, port, and inland delivery contingency actions.",
        ]
        residual = [
            "Seller-arranged insurance may not cover all indirect losses.",
            "Port or inland disruption may remain outside seller control.",
        ]
    return {
        "case_id": case_id,
        "trade_perspective": selected,
        "incoterm": responsibility["incoterm"],
        "named_destination_port": responsibility["named_destination_port"],
        "risk_transfer_point": responsibility["risk_transfer_point"],
        "focus": focus,
        "residual_risks": residual,
        "seller_responsibilities": responsibility["seller_responsibilities"],
        "buyer_responsibilities": responsibility["buyer_responsibilities"],
        "warnings": responsibility["warnings"],
    }
