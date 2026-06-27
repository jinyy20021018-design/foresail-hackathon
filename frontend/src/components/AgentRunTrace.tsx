import type { AgentRunTraceStep } from "../api/client";
import { t, type Language } from "../i18n";

type Props = { trace: AgentRunTraceStep[]; language: Language };

export function AgentRunTrace({ trace, language }: Props) {
  return <details className="panel full-width trace-disclosure">
    <summary><span><strong>{t(language, "agentRunTrace")}</strong><small>Technical audit trail for this monitoring cycle</small></span><span className="tag">{trace.length} {t(language, "steps")}</span></summary>
    {trace.length === 0 ? <p className="empty-state trace-empty">{t(language, "agentTraceEmpty")}</p> : <ol className="agent-trace compact-trace">{trace.map((step) => <li key={step.step}><div className="trace-step-number">{step.step}</div><div><div className="trace-title"><strong>{step.name}</strong><span>{step.tool_or_service}</span></div><p>{step.description}</p><small>{step.output_summary}</small></div></li>)}</ol>}
  </details>;
}
