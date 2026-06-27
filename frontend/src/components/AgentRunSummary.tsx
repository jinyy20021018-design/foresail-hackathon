import type { AgentRunResponse } from "../api/client";
import { t, translate, type Language } from "../i18n";

type Props = { result: AgentRunResponse | null; language: Language };

export function AgentRunSummary({ result, language }: Props) {
  if (!result) return <section className="panel full-width agent-summary-card"><div className="decision-panel-heading"><div><span className="section-kicker">Monitoring outcome</span><h2>{t(language, "agentRunSummary")}</h2></div></div><p className="empty-state">{t(language, "agentSummaryEmpty")}</p></section>;
  return <section className="panel full-width agent-summary-card agent-decision-summary">
    <div className="decision-panel-heading"><div><span className="section-kicker">{result.agent_run_id} · completed</span><h2>Monitoring decision</h2><p>{result.summary}</p></div><span className="status-transition">{translate.status(language, result.status_before)} <b>→</b> {translate.status(language, result.status_after)}</span></div>
    <div className="agent-outcome-strip"><span><b>{result.relevant_count}</b> relevant events</span><span><b>{result.risk_summary.exposures.length}</b> exposures</span><span><b>{result.actions.length}</b> actions</span><span><b>{result.information_gaps.length}</b> information gaps</span></div>
    <details className="technical-details"><summary>Run diagnostics</summary><dl><div><dt>Events scanned</dt><dd>{result.events_scanned}</dd></div><div><dt>Watch / filtered</dt><dd>{result.watch_count} / {result.irrelevant_count}</dd></div><div><dt>Decision engine</dt><dd>{result.llm_enabled ? "LLM assisted" : "Deterministic"}</dd></div><div><dt>Summary source</dt><dd>{result.summary_source}</dd></div></dl></details>
  </section>;
}
