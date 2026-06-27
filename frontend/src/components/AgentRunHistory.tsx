import { useState } from "react";
import { api, type AgentRunRecord, type AgentRunTraceStep } from "../api/client";

type Props = { caseId: string; runs: AgentRunRecord[] };

export function AgentRunHistory({ caseId, runs }: Props) {
  const [trace, setTrace] = useState<AgentRunTraceStep[]>([]);
  const [selectedRun, setSelectedRun] = useState<string | null>(null);
  async function toggleTrace(runId: string) { if (selectedRun === runId) { setSelectedRun(null); setTrace([]); return; } setSelectedRun(runId); setTrace(await api.getAgentRunTrace(caseId, runId)); }
  return <section className="panel full-width run-history-panel">
    <div className="decision-panel-heading"><div><span className="section-kicker">Run log</span><h2>Agent run history</h2></div><span className="tag">{runs.length} runs</span></div>
    {runs.length === 0 ? <p className="empty-state">No agent run history yet.</p> : <div className="run-list">{runs.map((run) => <div key={run.agent_run_id} className={selectedRun === run.agent_run_id ? "selected" : ""}><div><strong>{run.agent_run_id}</strong><small>{formatRunTime(run.completed_at)}</small></div><span className="run-transition">{run.status_before} → {run.status_after}</span><span><b>{run.events_scanned}</b> events</span><span><b>{run.relevant_count}</b> relevant</span><button type="button" onClick={() => void toggleTrace(run.agent_run_id)}>{selectedRun === run.agent_run_id ? "Hide trace" : "View trace"}</button></div>)}</div>}
    {trace.length > 0 && <div className="inline-run-trace">{trace.map((step) => <div key={step.trace_id ?? `${step.step}-${step.name}`}><span>{step.step}</span><div><strong>{step.step_name ?? step.name}</strong><p>{step.output_summary}</p></div></div>)}</div>}
  </section>;
}
function formatRunTime(value: string) { const date = new Date(value); if (Number.isNaN(date.getTime())) return value; return new Intl.DateTimeFormat("en", { month: "short", day: "numeric", year: "numeric", hour: "2-digit", minute: "2-digit" }).format(date); }
