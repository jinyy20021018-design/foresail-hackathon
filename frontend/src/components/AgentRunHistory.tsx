import { useState } from "react";
import { api, type AgentRunRecord, type AgentRunTraceStep } from "../api/client";

type Props = {
  caseId: string;
  runs: AgentRunRecord[];
};

export function AgentRunHistory({ caseId, runs }: Props) {
  const [trace, setTrace] = useState<AgentRunTraceStep[]>([]);
  return (
    <section className="panel full-width">
      <div className="panel-heading">
        <h2>Agent Run History</h2>
        <span className="tag">{runs.length} runs</span>
      </div>
      {runs.length === 0 ? <p className="empty-state">No agent run history yet.</p> : (
        <div className="table-wrap">
          <table className="data-table">
            <thead><tr><th>Run</th><th>Completed</th><th>Status</th><th>Events</th><th>R/W/I</th><th>Trace</th></tr></thead>
            <tbody>{runs.map((run) => (
              <tr key={run.agent_run_id}>
                <td>{run.agent_run_id}</td>
                <td>{formatRunTime(run.completed_at)}</td>
                <td>{`${run.status_before} -> ${run.status_after} / ${run.run_status}`}</td>
                <td>{run.events_scanned}</td>
                <td>{run.relevant_count}/{run.watch_count}/{run.irrelevant_count}</td>
                <td><button type="button" onClick={async () => setTrace(await api.getAgentRunTrace(caseId, run.agent_run_id))}>View Trace</button></td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      )}
      {trace.length > 0 && (
        <ol className="timeline">
          {trace.map((step) => <li key={step.trace_id ?? `${step.step}-${step.name}`}><strong>{step.step_name ?? step.name}</strong><span>{step.output_summary}</span></li>)}
        </ol>
      )}
    </section>
  );
}

function formatRunTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("en", { month: "short", day: "numeric", year: "numeric", hour: "2-digit", minute: "2-digit" }).format(date);
}
