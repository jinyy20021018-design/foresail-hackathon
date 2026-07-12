import os

from app.services.persistence_service import list_item_records

_SEED_ENV = {
    "EVENT_SOURCE_MODE": "MOCK",
    "USE_LLM_SUMMARY": "false",
    "REQUIRE_LLM_AGENT": "false",
}


def _apply_env(overrides: dict) -> dict:
    previous = {}
    for key, value in overrides.items():
        previous[key] = os.environ.get(key)
        os.environ[key] = value
    return previous


def _restore_env(previous: dict) -> None:
    for key, value in previous.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def seed_board(force: bool = False) -> dict:
    from app.services.case_service import (
        create_buyer_demo_case,
        create_hormuz_demo_case,
        create_redsea_demo_case,
        create_typhoon_demo_case,
    )
    from app.services.case_library_service import list_case_summaries
    from app.services.document_service import confirm_fields
    from app.agents.monitoring_agent import MonitoringAgent

    if list_item_records("case") and not force:
        return {"seeded": False, "cases": list_case_summaries()}

    previous = _apply_env(_SEED_ENV)
    try:
        agent = MonitoringAgent()
        for creator in (
            create_hormuz_demo_case,
            create_buyer_demo_case,
            create_redsea_demo_case,
            create_typhoon_demo_case,
        ):
            case = creator()
            confirm_fields(case["case_id"])
            agent.run_monitoring_cycle(case["case_id"])
    finally:
        _restore_env(previous)

    return {"seeded": True, "cases": list_case_summaries()}
