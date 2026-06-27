import type { RelevanceResult } from "../api/client";
import { t, translate, type Language } from "../i18n";

type Props = {
  results: RelevanceResult[];
  language: Language;
};

export function EventResultsTable({ results, language }: Props) {
  return (
    <section className="panel full-width">
      <div className="panel-heading">
        <h2>{t(language, "eventResults")}</h2>
        <span className="tag">
          {results.length} {t(language, "evaluated")}
        </span>
      </div>
      {results.length === 0 ? (
        <p className="empty-state">{t(language, "runMonitoringHint")}</p>
      ) : (
        <div className="table-wrap">
          <table className="data-table wide-data-table">
            <thead>
              <tr>
                <th>{t(language, "eventTitle")}</th>
                <th>Source</th>
                <th>Source Type</th>
                <th>URL</th>
                <th>Confidence</th>
                <th>{t(language, "classification")}</th>
                <th>{t(language, "score")}</th>
                <th>{t(language, "matchedFactors")}</th>
                <th>{t(language, "explanation")}</th>
                <th>{t(language, "mappedExposures")}</th>
              </tr>
            </thead>
            <tbody>
              {results.map((result) => (
                <tr key={result.event_id}>
                  <td>{translate.eventTitle(language, result.title)}</td>
                  <td>{result.source || "-"}</td>
                  <td>{result.source_type || result.event_type || "-"}</td>
                  <td>{result.url ? <a href={result.url} target="_blank" rel="noreferrer">Open Source</a> : "-"}</td>
                  <td>{typeof result.confidence === "number" ? `${Math.round(result.confidence * 100)}%` : "-"}</td>
                  <td>
                    <span className={`classification ${result.classification.toLowerCase()}`}>
                      {translate.classification(language, result.classification)}
                    </span>
                  </td>
                  <td title={`Raw score: ${result.raw_score ?? result.score}`}>
                    {result.display_score ?? Math.max(0, Math.min(result.score, 100))} / 100
                  </td>
                  <td>
                    {result.matched_factors.map((factor) => translate.factor(language, factor)).join(", ") ||
                      t(language, "none")}
                  </td>
                  <td>{result.explanation}</td>
                  <td>
                    {result.mapped_exposures
                      .map((exposure) => translate.exposure(language, exposure))
                      .join(", ") || t(language, "none")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
