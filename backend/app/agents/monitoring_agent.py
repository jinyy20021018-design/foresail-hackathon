import json
from itertools import count

from app.services.action_board_service import generate_actions
from app.services.action_draft_service import generate_action_drafts
from app.services.agent_summary_service import generate_agent_summary_result
from app.services.case_service import (
    get_case,
    get_timeline,
    get_watch_profile,
    set_monitoring_outputs,
)
from app.services.agent_run_service import save_agent_run
from app.services.document_service import (
    get_best_case_facts,
    get_field_conflicts,
    set_action_drafts,
    set_information_gaps,
    set_obligations,
)
from app.services.information_gap_service import assign_gap_ids, detect_information_gaps
from app.services.event_ingestion_service import fetch_events_for_case
from app.services.obligation_service import generate_obligations
from app.services.relevance_engine import classify_events
from app.services.risk_mapper import summarize_exposures
from app.services.treatment_plan_service import generate_approval_package, generate_treatment_plans

_run_counter = count(1)


class MonitoringAgent:
    def run_monitoring_cycle(self, case_id: str) -> dict:
        agent_run_id = f"RUN-{next(_run_counter):03d}"
        trace: list[dict] = []

        case = get_case(case_id)
        status_before = case["status"]
        trace.append(
            _trace_step(
                1,
                "Load Case",
                f"Loaded {case_id} for {case['vessel']} on the {case['route']} route.",
                "case_service",
                f"Case status before run: {status_before}",
            )
        )

        high_conflicts = [conflict for conflict in get_field_conflicts(case_id) if conflict["severity"] == "High" and conflict["status"] == "OPEN"]
        if high_conflicts:
            trace.append(
                _trace_step(
                    2,
                    "Check Field Conflicts",
                    "Checked whether unresolved high-severity field conflicts block monitoring.",
                    "document_service",
                    f"{len(high_conflicts)} unresolved high-severity conflicts found.",
                )
            )
            result = {
                "agent_run_id": agent_run_id,
                "case_id": case_id,
                "status_before": status_before,
                "status_after": status_before,
                "summary": "Agent run blocked because high-severity field conflicts must be resolved before monitoring.",
                "summary_source": "deterministic",
                "llm_enabled": False,
                "llm_required": False,
                "trace": trace,
                "events_scanned": 0,
                "relevant_count": 0,
                "watch_count": 0,
                "irrelevant_count": 0,
                "case": case,
                "watch_profile": get_watch_profile(case_id),
                "relevance_results": [],
                "risk_summary": {"triggered": False, "trigger_events": [], "watch_events_considered": [], "exposures": []},
                "obligations": [],
                "information_gaps": [],
                "action_drafts": [],
                "actions": [],
                "status_timeline": get_timeline(case_id),
                "unresolved_high_conflicts": high_conflicts,
            }
            save_agent_run(case_id, result, run_status="BLOCKED")
            return result

        facts = get_best_case_facts(case_id)
        trace.append(
            _trace_step(
                2,
                "Load Confirmed Fields",
                "Loaded confirmed case facts when available; otherwise used the existing case snapshot.",
                "document_service",
                "Confirmed facts available." if facts != case else "No confirmed facts found; using case snapshot.",
            )
        )

        watch_profile = get_watch_profile(case_id)
        trace.append(
            _trace_step(
                3,
                "Build Watch Profile",
                "Retrieved the case watch profile used to monitor vessel, ports, route regions, and deadlines.",
                "watch_profile_service",
                f"Watching {watch_profile['watched_vessel']} and {len(watch_profile['watched_ports'])} ports.",
            )
        )

        ingestion_result = fetch_events_for_case(case_id, watch_profile, agent_run_id=agent_run_id, persist=True)
        events = ingestion_result["events"]
        search_summary = ingestion_result.get("search_summary", {})
        real_api_summary = ingestion_result.get("real_api_summary", {})
        trace.append(
            _trace_step(
                4,
                "Build Search Queries",
                "Generated external information search queries from the case watch profile.",
                "search_query_builder",
                json.dumps({"queries_generated": real_api_summary.get("queries_generated", search_summary.get("queries_generated", 0))}, ensure_ascii=True),
            )
        )
        trace.append(
            _trace_step(
                5,
                "Fetch GDELT Events",
                "Fetched news, port, geopolitical, and trade-policy event candidates through the GDELT connector.",
                "gdelt_event_connector",
                json.dumps(
                    {
                        "enabled": real_api_summary.get("gdelt_enabled", False),
                        "queries_generated": real_api_summary.get("queries_generated", 0),
                        "articles_fetched": real_api_summary.get("gdelt_articles_fetched", 0),
                        "events_extracted": real_api_summary.get("gdelt_events_extracted", 0),
                        "connector_errors": real_api_summary.get("connector_errors", []),
                        "warnings": real_api_summary.get("warnings", []),
                    },
                    ensure_ascii=True,
                ),
            )
        )
        trace.append(
            _trace_step(
                6,
                "Fetch Open-Meteo Weather",
                "Fetched weather forecast event candidates for watched ports and route regions.",
                "open_meteo_weather_connector",
                json.dumps(
                    {
                        "enabled": real_api_summary.get("weather_enabled", False),
                        "locations_checked": real_api_summary.get("weather_locations_checked", 0),
                        "weather_events_extracted": real_api_summary.get("weather_events_extracted", 0),
                        "connector_errors": real_api_summary.get("connector_errors", []),
                        "warnings": real_api_summary.get("warnings", []),
                    },
                    ensure_ascii=True,
                ),
            )
        )
        trace.append(
            _trace_step(
                7,
                "Extract Real Events",
                "Converted real API results into normalized external event candidates before normalization.",
                "event_connectors",
                f"{real_api_summary.get('gdelt_events_extracted', 0)} GDELT and {real_api_summary.get('weather_events_extracted', 0)} weather events extracted.",
            )
        )
        trace.append(
            _trace_step(
                8,
                "Fetch External Events",
                "Fetched events through the configured external event ingestion service.",
                "event_ingestion_service",
                json.dumps(
                    {
                        "mode": ingestion_result["mode"],
                        "connectors_called": ingestion_result["connectors_called"],
                        "events_raw_count": ingestion_result["events_raw_count"],
                        "events_normalized_count": ingestion_result["events_normalized_count"],
                        "events_deduped_count": ingestion_result["events_deduped_count"],
                        "connector_errors": ingestion_result["connector_errors"],
                    },
                    ensure_ascii=True,
                ),
            )
        )
        trace.append(
            _trace_step(
                9,
                "Normalize Events",
                "Converted connector outputs into the normalized external event schema before relevance scoring.",
                "event_normalizer",
                f"{ingestion_result['events_normalized_count']} normalized events available.",
            )
        )
        trace.append(
            _trace_step(
                10,
                "Deduplicate Events",
                "Removed duplicate events by deduplication key and source confidence.",
                "event_deduplicator",
                f"{ingestion_result['deduplication']['duplicates_removed']} duplicates removed; {ingestion_result['events_deduped_count']} events retained.",
            )
        )

        relevance_results = classify_events(facts, events)
        relevant_count = _count(relevance_results, "Relevant")
        watch_count = _count(relevance_results, "Watch")
        irrelevant_count = _count(relevance_results, "Irrelevant")
        trace.append(
            _trace_step(
                11,
                "Classify Event Relevance",
                "Classified each event using deterministic relevance scoring.",
                "relevance_engine",
                f"{relevant_count} Relevant, {watch_count} Watch, {irrelevant_count} Irrelevant.",
            )
        )

        risk_summary = summarize_exposures(facts, events, relevance_results)
        trace.append(
            _trace_step(
                12,
                "Map Exposures",
                "Mapped Relevant and Watch events to case-level risk exposure categories.",
                "risk_mapper",
                f"{len(risk_summary['exposures'])} exposure categories identified.",
            )
        )

        obligations = generate_obligations(case_id, facts, relevance_results, risk_summary)
        set_obligations(case_id, obligations)
        obligations_at_risk = [obligation for obligation in obligations if "risk" in obligation["current_assessment"].lower()]
        trace.append(
            _trace_step(
                13,
                "Map Obligations & Deadlines",
                "Mapped confirmed facts and risk results to preliminary operational obligation and deadline assessments.",
                "obligation_service",
                f"{len(obligations)} obligations mapped; {len(obligations_at_risk)} at risk.",
            )
        )

        information_gaps = assign_gap_ids(detect_information_gaps(case_id, facts, relevance_results))
        set_information_gaps(case_id, information_gaps)
        trace.append(
            _trace_step(
                14,
                "Detect Information Gaps",
                "Detected missing confirmations that may block operational decisions.",
                "information_gap_service",
                f"{len(information_gaps)} information gaps detected.",
            )
        )

        actions = generate_actions(risk_summary)
        trace.append(
            _trace_step(
                15,
                "Generate Actions",
                "Generated deduplicated recommended actions from aggregated exposures.",
                "action_board_service",
                f"{len(actions)} recommended actions generated.",
            )
        )

        action_drafts = generate_action_drafts(case_id, facts, risk_summary, actions)
        set_action_drafts(case_id, action_drafts)
        trace.append(
            _trace_step(
                16,
                "Generate Action Drafts",
                "Generated draft outbound/internal messages for user review. Nothing was sent externally.",
                "action_draft_service",
                f"{len(action_drafts)} action drafts generated.",
            )
        )

        set_monitoring_outputs(case_id, relevance_results, risk_summary, actions)
        updated_case = get_case(case_id)
        status_after = updated_case["status"]
        status_timeline = get_timeline(case_id)
        trace.append(
            _trace_step(
                17,
                "Update Case Status",
                "Updated case status through the existing deterministic status machine.",
                "status_machine",
                f"Case moved from {status_before} to {status_after}.",
            )
        )

        treatment_output = {"plans": [], "recommended_plan_id": None}
        approval_package = None
        try:
            treatment_output = generate_treatment_plans(case_id)
            trace.append(
                _trace_step(
                    18,
                    "Generate Treatment Plans",
                    "Generated structured risk treatment plan options from current exposures, obligations, gaps, and actions.",
                    "treatment_plan_service",
                    f"{len(treatment_output['plans'])} treatment plans generated.",
                )
            )
            trace.append(
                _trace_step(
                    19,
                    "Generate Residual Risk Summary",
                    "Generated residual risk summaries for each treatment plan.",
                    "treatment_plan_service",
                    "Residual risks persisted with treatment plans.",
                )
            )
            if treatment_output.get("recommended_plan_id"):
                approval_package = generate_approval_package(case_id, treatment_output["recommended_plan_id"])
                approval_summary = f"Approval package {approval_package['approval_package_id']} generated."
            else:
                approval_summary = "No recommended treatment plan available for approval package."
            trace.append(
                _trace_step(
                    20,
                    "Generate Approval Summary Draft",
                    "Generated a structured approval summary draft for the recommended treatment plan.",
                    "treatment_plan_service",
                    approval_summary,
                )
            )
            trace.append(
                _trace_step(
                    21,
                    "Persist Treatment Outputs",
                    "Persisted treatment plans, residual risks, and approval package data for the case.",
                    "persistence_service",
                    "Treatment outputs persisted.",
                )
            )
        except Exception as error:
            trace.append(
                _trace_step(
                    18,
                    "Generate Treatment Plans",
                    "Attempted to generate treatment plans after agent monitoring outputs.",
                    "treatment_plan_service",
                    f"Treatment plan generation failed: {error}",
                    status="error",
                )
            )

        trace.append(
            _trace_step(
                len(trace) + 1,
                "Save Agent Run History",
                "Saved this agent run and trace steps for audit history.",
                "agent_run_service",
                "Agent run history persisted.",
            )
        )

        summary_result = generate_agent_summary_result(
            case=case,
            status_before=status_before,
            status_after=status_after,
            relevance_results=relevance_results,
            risk_summary=risk_summary,
            actions=actions,
            obligations=obligations,
            information_gaps=information_gaps,
            action_drafts=action_drafts,
        )
        summary = summary_result["summary"]
        trace.append(
            _trace_step(
                len(trace) + 1,
                "Generate Agent Summary",
                "Generated a user-facing agent run summary from the completed tool outputs.",
                "agent_summary_service",
                f"Agent run summary generated by {summary_result['summary_source']}.",
            )
        )
        result = {
            "agent_run_id": agent_run_id,
            "case_id": case_id,
            "status_before": status_before,
            "status_after": status_after,
            "summary": summary,
            "summary_source": summary_result["summary_source"],
            "llm_enabled": summary_result["llm_enabled"],
            "llm_required": summary_result["llm_required"],
            "trace": trace,
            "events_scanned": len(events),
            "relevant_count": relevant_count,
            "watch_count": watch_count,
            "irrelevant_count": irrelevant_count,
            "case": updated_case,
            "watch_profile": watch_profile,
            "relevance_results": relevance_results,
            "risk_summary": risk_summary,
            "obligations": obligations,
            "information_gaps": information_gaps,
            "action_drafts": action_drafts,
            "actions": actions,
            "status_timeline": status_timeline,
            "unresolved_high_conflicts": [],
            "treatment_plans": treatment_output.get("plans", []),
            "recommended_treatment_plan_id": treatment_output.get("recommended_plan_id"),
            "approval_package": approval_package,
        }
        save_agent_run(case_id, result, run_status="COMPLETED")
        return result


def _count(results: list[dict], classification: str) -> int:
    return sum(1 for result in results if result["classification"] == classification)


def _trace_step(step: int, name: str, description: str, tool_or_service: str, output_summary: str, status: str = "completed") -> dict:
    return {
        "step": step,
        "name": name,
        "status": status,
        "description": description,
        "tool_or_service": tool_or_service,
        "output_summary": output_summary,
    }
