import type { RiskSummary } from "../api/client";
import { t, translate, type Language } from "../i18n";

type Props = { summary: RiskSummary | null; language: Language };

export function RiskSummaryPanel({ summary, language }: Props) {
  return (
    <section className="panel full-width risk-decision-panel">
      <div className="decision-panel-heading"><div><span className="section-kicker">Decision view</span><h2>{t(language, "riskSummary")}</h2><p>Material exposure created by the relevant events.</p></div>{summary && <span className={`review-state ${summary.triggered ? "rejected" : "approved"}`}><i />{summary.triggered ? t(language, "triggered") : t(language, "noTrigger")}</span>}</div>
      {!summary ? <p className="empty-state">{t(language, "noRiskSummary")}</p> : <>
        <div className="risk-source-line"><span><b>{summary.trigger_events.length}</b> trigger events</span><span><b>{summary.watch_events_considered?.length ?? 0}</b> watch signals</span></div>
        <div className="risk-list">
          {summary.exposures.map((exposure) => (
            <article key={exposure.category}>
              <span className={`priority-pill ${exposure.severity.toLowerCase()}`}>{translate.severity(language, exposure.severity)}</span>
              <div><h3>{translate.exposure(language, exposure.category)}</h3><p>{translate.impact(language, exposure.impact)}</p></div>
              <small>Evidence: {[...(exposure.trigger_event_ids ?? []), ...(exposure.watch_event_ids ?? [])].join(", ") || t(language, "none")}</small>
            </article>
          ))}
        </div>
      </>}
    </section>
  );
}
