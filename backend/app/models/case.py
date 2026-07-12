from dataclasses import dataclass, field


@dataclass
class TradeCase:
    case_id: str
    status: str
    vessel: str
    route: str
    port_of_loading: str
    port_of_discharge: str
    final_destination: str
    etd: str
    eta: str
    latest_shipment_date: str
    payment_method: str
    incoterm: str
    incoterm_named_place: str = ""
    trade_perspective: str = "SELLER"
    perspective_source: str = "DEFAULT"
    perspective_basis: str = ""
    uploaded_files: list[str] = field(default_factory=list)
    mock_extraction_note: str = "Mock extracted fields for MVP. Files are not parsed in this version."


@dataclass
class StatusTimelineEntry:
    status: str
    reason: str
