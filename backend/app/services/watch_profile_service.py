from app.services.route_region_service import merge_watched_route_regions


def build_watch_profile(case: dict) -> dict:
    return {
        "case_id": case["case_id"],
        "watched_vessel": case["vessel"],
        "watched_ports": [
            case["port_of_loading"],
            case["port_of_discharge"],
            case["final_destination"],
        ],
        "watched_route_regions": merge_watched_route_regions(case),
        "shipment_window": {
            "etd": case["etd"],
            "eta": case["eta"],
            "latest_shipment_date": case["latest_shipment_date"],
        },
        "deadline_sensitivity": [
            "Latest shipment date",
            "ETA delay",
            "LC at sight presentation timing",
        ],
        "risk_categories": [
            "Shipping",
            "LC Deadline",
            "Port Operation",
            "Payment Timeline",
        ],
        "alert_rules": [
            "Alert if vessel delay is greater than or equal to 3 days",
            "Alert if affected port matches port of loading or port of discharge",
            "Alert if affected region overlaps the route corridor",
            "Alert if event may affect latest shipment date or ETA",
            "Filter out events in unrelated regions or unrelated ports",
        ],
    }
