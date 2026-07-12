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
  return (
    <section className="panel full-width relevance-panel">
      <div className="decision-panel-heading"><div><span className="section-kicker">Signal assessment</span><h2>{t(language, "eventResults")}</h2><p>Events ranked by their impact on this shipment.</p></div><span className="tag">{results.length} {t(language, "evaluated")}</span></div>
      {results.length === 0 ? <p className="empty-state">{t(language, "runMonitoringHint")}</p> : <>
        <div className="classification-summary"><span className="relevant"><b>{relevant}</b> Relevant</span><span className="watch"><b>{watch}</b> Watch</span><span><b>{irrelevant}</b> Filtered out</span></div>
        <div className="relevance-list">
          {results.map((result) => {
            const hasBreakdown = (result.factor_breakdown?.length ?? 0) > 0;
            const open = openId === result.event_id;
            return (
            <article key={result.event_id} className={`relevance-row ${result.classification.toLowerCase()}`}>
              <span className={`classification ${result.classification.toLowerCase()}`}>{translate.classification(language, result.classification)}</span>
              <div>
                <h3>{translate.eventTitle(language, result.title)}</h3><p>{result.explanation}</p>
                <small>{result.source || result.source_type || "Unknown source"}</small>
                {hasBreakdown && (
                  <button type="button" className="wf-toggle" onClick={() => setOpenId(open ? null : result.event_id)}>
                    {open ? "Hide score breakdown" : "Why this score?"}
                  </button>
                )}
                {open && hasBreakdown && <div className="wf-expand"><ScoreWaterfall result={result} /></div>}
              </div>
              <div className="relevance-score"><strong>{result.display_score ?? Math.max(0, Math.min(result.score, 100))}</strong><span>match score</span></div>
              <div className="exposure-tags">{result.mapped_exposures.map((exposure) => <span key={exposure}>{translate.exposure(language, exposure)}</span>)}</div>
              {result.url && <a href={result.url} target="_blank" rel="noreferrer">Source ↗</a>}
            </article>
            );
          })}
        </div>
      </>}
    </section>
  );
}
