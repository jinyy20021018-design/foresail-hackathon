import { useState } from "react";
import type { RelevanceResult } from "../api/client";
import { ScoreWaterfall } from "./ScoreWaterfall";
import { t, translate, type Language } from "../i18n";

type Props = { results: RelevanceResult[]; language: Language };

export function EventResultsTable({ results, language }: Props) {
  const [openId, setOpenId] = useState<string | null>(null);
  const relevant = results.filter((item) => item.classification === "Relevant").length;
  const watch = results.filter((item) => item.classification === "Watch").length;
  const irrelevant = results.length - relevant - watch;
  const rankedResults = [...results].sort(compareRiskResults);

  return (
    <section className="panel full-width relevance-panel">
      <div className="decision-panel-heading">
        <div>
          <span className="section-kicker">Signal assessment</span>
          <h2>{t(language, "eventResults")}</h2>
          <p>Sorted by classification, match score, severity, confidence, then recency.</p>
        </div>
        <span className="tag">{results.length} {t(language, "evaluated")}</span>
      </div>
      {results.length === 0 ? <p className="empty-state">{t(language, "runMonitoringHint")}</p> : <>
        <div className="classification-summary">
          <span className="relevant"><b>{relevant}</b> Relevant</span>
          <span className="watch"><b>{watch}</b> Watch</span>
          <span><b>{irrelevant}</b> Filtered out</span>
        </div>
        <div className="relevance-list">
          {rankedResults.map((result) => {
            const hasBreakdown = (result.factor_breakdown?.length ?? 0) > 0;
            const open = openId === result.event_id;
            return (
            <article key={result.event_id} className={`relevance-row ${result.classification.toLowerCase()}`}>
              <span className={`classification ${result.classification.toLowerCase()}`}>{translate.classification(language, result.classification)}</span>
              <div>
                <h3>{translate.eventTitle(language, result.title)}</h3>
                {result.llm_factor_used && <span className="llm-assisted-badge">LLM-assisted factors</span>}
                <p>{result.explanation}</p>
                <FactorInsight result={result} />
                <small>{result.source || result.source_type || "Unknown source"}</small>
                {hasBreakdown && (
                  <button type="button" className="wf-toggle" onClick={() => setOpenId(open ? null : result.event_id)}>
                    {open ? "Hide score breakdown" : "Why this score?"}
                  </button>
                )}
                {open && hasBreakdown && <div className="wf-expand"><ScoreWaterfall result={result} /></div>}
              </div>
              <div className="relevance-score">
                <strong>{displayScore(result)}</strong>
                <span>match score</span>
              </div>
              <div className="exposure-tags">
                {result.mapped_exposures.map((exposure) => <span key={exposure}>{translate.exposure(language, exposure)}</span>)}
              </div>
              {result.url
                ? <a href={result.url} target="_blank" rel="noreferrer">Source -&gt;</a>
                : <span className="source-unavailable">No source link</span>}
            </article>
            );
          })}
        </div>
      </>}
    </section>
  );
}

function FactorInsight({ result }: { result: RelevanceResult }) {
  const accepted = result.validated_factors?.length
    ? result.validated_factors
    : result.matched_factors.map((factor) => ({ factor, evidence: "Deterministic match factor." }));
  const rejected = result.rejected_factors ?? [];
  const missing = result.missing_direct_evidence ?? [];
  if (accepted.length === 0 && rejected.length === 0 && missing.length === 0 && !result.llm_factor_summary) return null;
  return (
    <div className="factor-insight">
      {result.llm_factor_summary && <p className="factor-summary">{result.llm_factor_summary}</p>}
      <div className="factor-chip-row">
        {accepted.slice(0, 4).map((item) => (
          <span className="factor-chip accepted" key={`accepted-${item.factor}`}>{humanizeFactor(item.factor)}</span>
        ))}
        {rejected.slice(0, 2).map((item) => (
          <span className="factor-chip rejected" key={`rejected-${item.factor}`}>{humanizeFactor(item.factor)}</span>
        ))}
      </div>
      {rejected.length > 0 && <small className="factor-note">Rejected: {rejected.map((item) => `${humanizeFactor(item.factor)}${item.reason ? ` (${item.reason})` : ""}`).join("; ")}</small>}
      {missing.length > 0 && <small className="factor-note">Missing: {missing.join("; ")}</small>}
    </div>
  );
}

function humanizeFactor(value: string) {
  return value.replace(/_/g, " ");
}

function compareRiskResults(a: RelevanceResult, b: RelevanceResult) {
  const classificationDelta = rankClassification(b.classification) - rankClassification(a.classification);
  if (classificationDelta !== 0) return classificationDelta;

  const scoreDelta = displayScore(b) - displayScore(a);
  if (scoreDelta !== 0) return scoreDelta;

  const severityDelta = rankSeverity(b.severity) - rankSeverity(a.severity);
  if (severityDelta !== 0) return severityDelta;

  const confidenceDelta = (b.confidence ?? 0) - (a.confidence ?? 0);
  if (confidenceDelta !== 0) return confidenceDelta;

  return eventTimeMs(b) - eventTimeMs(a);
}

function rankClassification(value: string) {
  return { Relevant: 3, Watch: 2, Irrelevant: 1 }[value] ?? 0;
}

function rankSeverity(value?: string | null) {
  return { CRITICAL: 4, HIGH: 3, MEDIUM: 2, LOW: 1, UNKNOWN: 0 }[String(value ?? "UNKNOWN").toUpperCase()] ?? 0;
}

function displayScore(result: RelevanceResult) {
  return result.display_score ?? Math.max(0, Math.min(result.score, 100));
}

function eventTimeMs(result: RelevanceResult) {
  const value = result.event_time ?? result.published_at;
  if (!value) return 0;
  const parsed = Date.parse(value);
  return Number.isNaN(parsed) ? 0 : parsed;
}
