import type { RiskSummary } from "../api/client";
import { t, translate, type Language } from "../i18n";

type Props = {
  summary: RiskSummary | null;
  language: Language;
};

export function RiskSummaryPanel({ summary, language }: Props) {
  return (
    <section className="panel full-width">
      <div className="panel-heading">
        <h2>{t(language, "riskSummary")}</h2>
        {summary && <span className="tag">{summary.triggered ? t(language, "triggered") : t(language, "noTrigger")}</span>}
      </div>
      {!summary ? (
        <p className="empty-state">{t(language, "noRiskSummary")}</p>
      ) : (
        <>
          <p>
            <strong>{t(language, "triggerEvents")}:</strong> {summary.trigger_events.join(", ") || t(language, "none")}
          </p>
          <p>
            <strong>{t(language, "watchEventsConsidered")}:</strong>{" "}
            {(summary.watch_events_considered ?? []).join(", ") || t(language, "none")}
          </p>
          <div className="exposure-grid">
            {summary.exposures.map((exposure) => (
              <article key={`${exposure.party_perspective ?? "ALL"}-${exposure.category}`} className="exposure-item">
                <h3>{translate.exposure(language, exposure.category)}</h3>
                <p>{translate.impact(language, exposure.impact)}</p>
                <span>{translate.severity(language, exposure.severity)}</span>
                <small>Perspective: {exposure.party_perspective ?? summary.trade_perspective ?? "SELLER"}</small>
                <small>Responsible: {exposure.responsible_party ?? "UNKNOWN"} | Incoterm: {exposure.incoterm_basis || "N/A"}</small>
                <small>
                  {t(language, "triggerEvidence")}:{" "}
                  {(exposure.trigger_event_ids ?? []).join(", ") || t(language, "none")}
                </small>
                <small>
                  {t(language, "watchEvidence")}: {(exposure.watch_event_ids ?? []).join(", ") || t(language, "none")}
                </small>
              </article>
            ))}
          </div>
        </>
      )}
    </section>
  );
}
