import json
import os
from pathlib import Path
import urllib.error
import urllib.request


ALLOWED_FACTORS = {
    "vessel_match",
    "watched_port_match",
    "route_region_match",
    "route_corridor_text_match",
    "shipment_window_overlap",
    "eta_or_deadline_impact",
    "high_severity",
    "voyage_alignment_match",
    "unrelated_region",
    "unrelated_port",
    "weather_watch_cap",
    "confidence_weighted",
    "forecast_horizon_decay",
    "incoterm_risk_not_ours",
}

DIRECT_EVIDENCE_FACTORS = {
    "vessel_match": "No vessel name match",
    "watched_port_match": "No watched port match",
    "eta_or_deadline_impact": "No confirmed ETA or deadline impact",
}


def build_factor_metadata(case: dict, event: dict, deterministic_factors: list[str]) -> dict:
    deterministic_candidates = _deterministic_candidates(deterministic_factors)
    base = {
        "llm_factor_used": False,
        "llm_candidate_factors": deterministic_candidates,
        "validated_factors": deterministic_candidates,
        "rejected_factors": [],
        "missing_direct_evidence": _missing_direct_evidence(deterministic_factors),
        "llm_factor_summary": "Deterministic relevance factors were used.",
    }

    _load_local_env()
    if not _truthy(os.getenv("USE_LLM_RELEVANCE_FACTORS")):
        return base

    if not os.getenv("OPENAI_API_KEY"):
        return {
            **base,
            "llm_factor_summary": "LLM relevance factor extraction was enabled, but OPENAI_API_KEY is not configured; deterministic factors were used.",
            "llm_factor_error": "OPENAI_API_KEY_NOT_CONFIGURED",
        }

    try:
        llm_payload = _extract_candidate_factors(case, event)
        candidates = _normalize_candidates(llm_payload.get("candidate_factors", []))
        validation = _validate_candidates(candidates, deterministic_factors)
        validated_factors = _merge_validated_factors(deterministic_factors, validation["accepted"])
        return {
            "llm_factor_used": True,
            "llm_candidate_factors": candidates,
            "validated_factors": validated_factors,
            "rejected_factors": validation["rejected"],
            "missing_direct_evidence": _as_string_list(llm_payload.get("missing_direct_evidence")) or _missing_direct_evidence(deterministic_factors),
            "llm_factor_summary": str(llm_payload.get("llm_summary") or "LLM proposed candidate factors; deterministic validation remained the scoring authority."),
        }
    except Exception as error:
        return {
            **base,
            "llm_factor_summary": "LLM relevance factor extraction failed; deterministic factors were used.",
            "llm_factor_error": _format_error(error),
        }


def summarize_factor_metadata(results: list[dict]) -> dict:
    llm_enabled = _truthy(os.getenv("USE_LLM_RELEVANCE_FACTORS"))
    candidate_count = sum(len(result.get("llm_candidate_factors") or []) for result in results)
    validated_count = sum(len(result.get("validated_factors") or []) for result in results)
    rejected_count = sum(len(result.get("rejected_factors") or []) for result in results)
    llm_used_count = sum(1 for result in results if result.get("llm_factor_used"))
    fallback_used = llm_enabled and llm_used_count < len(results)
    errors = [result.get("llm_factor_error") for result in results if result.get("llm_factor_error")]
    return {
        "llm_enabled": llm_enabled,
        "events_sent_to_llm": llm_used_count,
        "candidate_factors_count": candidate_count,
        "validated_factors_count": validated_count,
        "rejected_factors_count": rejected_count,
        "fallback_used": fallback_used,
        "errors": errors[:5],
    }


def _extract_candidate_factors(case: dict, event: dict) -> dict:
    api_key = os.getenv("OPENAI_API_KEY", "")
    payload = {
        "model": os.getenv("OPENAI_RELEVANCE_FACTOR_MODEL", "gpt-4o-mini"),
        "messages": [
            {
                "role": "system",
                "content": (
                    "Extract candidate relevance match factors for a trade disruption monitoring system. "
                    "Return only JSON. Do not assign final score, final classification, case status, risk level, or treatment actions."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "allowed_factors": sorted(ALLOWED_FACTORS),
                        "case_watch_profile": _case_payload(case),
                        "external_event": _event_payload(event),
                        "required_json_schema": {
                            "candidate_factors": [
                                {"factor": "watched_port_match", "evidence": "short evidence text", "confidence": 0.8}
                            ],
                            "missing_direct_evidence": ["No vessel name match"],
                            "llm_summary": "short explanation of candidate factor reasoning",
                        },
                    },
                    ensure_ascii=True,
                ),
            },
        ],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    timeout_seconds = int(os.getenv("OPENAI_RELEVANCE_FACTOR_TIMEOUT_SECONDS", "20"))
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        body = json.loads(response.read().decode("utf-8"))
    content = body["choices"][0]["message"]["content"]
    return json.loads(content)


def _validate_candidates(candidates: list[dict], deterministic_factors: list[str]) -> dict:
    deterministic_set = set(deterministic_factors)
    accepted = []
    rejected = []
    for candidate in candidates:
        factor = candidate.get("factor")
        evidence = str(candidate.get("evidence") or "").strip()
        confidence = candidate.get("confidence")
        if factor not in ALLOWED_FACTORS:
            rejected.append({**candidate, "reason": "Unknown factor."})
        elif not evidence:
            rejected.append({**candidate, "reason": "Evidence is required."})
        elif not _valid_confidence(confidence):
            rejected.append({**candidate, "reason": "Confidence must be between 0 and 1."})
        elif factor not in deterministic_set:
            rejected.append({**candidate, "reason": "Not supported by deterministic case/event validation."})
        else:
            accepted.append(candidate)
    return {"accepted": accepted, "rejected": rejected}


def _merge_validated_factors(deterministic_factors: list[str], accepted_candidates: list[dict]) -> list[dict]:
    accepted_by_factor = {candidate["factor"]: candidate for candidate in accepted_candidates}
    merged = []
    for factor in deterministic_factors:
        accepted = accepted_by_factor.get(factor)
        if accepted:
            merged.append({**accepted, "source": "llm_validated"})
        else:
            merged.append({
                "factor": factor,
                "evidence": "Supported by deterministic case/event validation.",
                "confidence": 1.0,
                "source": "deterministic",
            })
    return merged


def _normalize_candidates(raw_candidates) -> list[dict]:
    candidates = []
    for item in raw_candidates if isinstance(raw_candidates, list) else []:
        if not isinstance(item, dict):
            continue
        factor = str(item.get("factor") or "").strip()
        evidence = str(item.get("evidence") or "").strip()
        try:
            confidence = max(0.0, min(float(item.get("confidence", 0)), 1.0))
        except (TypeError, ValueError):
            confidence = item.get("confidence")
        candidates.append({"factor": factor, "evidence": evidence, "confidence": confidence})
    return candidates


def _deterministic_candidates(factors: list[str]) -> list[dict]:
    return [
        {
            "factor": factor,
            "evidence": "Detected by deterministic relevance rule.",
            "confidence": 1.0,
            "source": "deterministic",
        }
        for factor in factors
    ]


def _missing_direct_evidence(factors: list[str]) -> list[str]:
    factor_set = set(factors)
    return [message for factor, message in DIRECT_EVIDENCE_FACTORS.items() if factor not in factor_set]


def _case_payload(case: dict) -> dict:
    return {
        "case_id": case.get("case_id"),
        "vessel": case.get("vessel"),
        "route": case.get("route"),
        "port_of_loading": case.get("port_of_loading"),
        "port_of_discharge": case.get("port_of_discharge"),
        "final_destination": case.get("final_destination"),
        "etd": case.get("etd"),
        "eta": case.get("eta"),
        "latest_shipment_date": case.get("latest_shipment_date"),
        "payment_method": case.get("payment_method"),
        "incoterm": case.get("incoterm"),
    }


def _event_payload(event: dict) -> dict:
    return {
        "event_id": event.get("event_id"),
        "title": event.get("title"),
        "description": event.get("description") or event.get("impact"),
        "event_type": event.get("event_type") or event.get("type"),
        "source_type": event.get("source_type"),
        "severity": event.get("severity"),
        "confidence": event.get("confidence"),
        "event_time": event.get("event_time"),
        "published_at": event.get("published_at"),
        "affected_ports": event.get("affected_ports") or [],
        "affected_routes": event.get("affected_routes") or [],
        "affected_vessels": event.get("affected_vessels") or [],
        "affected_region": event.get("affected_region"),
        "expected_impact_window": event.get("expected_impact_window"),
        "impact": event.get("impact"),
    }


def _as_string_list(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item or "").strip()]


def _valid_confidence(value) -> bool:
    return isinstance(value, (int, float)) and 0 <= float(value) <= 1


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _load_local_env() -> None:
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _format_error(error: Exception) -> str:
    if isinstance(error, urllib.error.HTTPError):
        return f"HTTP_{error.code}"
    if isinstance(error, urllib.error.URLError):
        return f"URL_ERROR: {error.reason}"
    return error.__class__.__name__
