import type { HazardDelta } from "../api/client";
import "../styles/viz.css";

type Group = { key: keyof HazardDelta; label: string; tone: string; sign: string };

const GROUPS: Group[] = [
  { key: "new", label: "New threats", tone: "red", sign: "+" },
  { key: "escalated", label: "Escalated", tone: "amber", sign: "↑" },
  { key: "resolved", label: "Resolved", tone: "green", sign: "−" },
  { key: "ongoing", label: "Ongoing", tone: "faint", sign: "=" },
];

export function RunDeltaCard({ delta }: { delta?: HazardDelta }) {
  if (!delta) return null;
  const counts = {
    new: delta.new?.length ?? 0,
    escalated: delta.escalated?.length ?? 0,
    resolved: delta.resolved?.length ?? 0,
    ongoing: delta.ongoing?.length ?? 0,
  };
  const changed = counts.new + counts.escalated + counts.resolved;

  return (
    <div className="viz-card run-delta">
      <div className="viz-head">
        <div>
          <span className="viz-kicker">Since last monitoring run</span>
          <h3>{changed === 0 ? "No change in the threat picture" : `${changed} change${changed > 1 ? "s" : ""} this run`}</h3>
        </div>
        {delta.all_clear && <span className="run-delta-clear">ALL CLEAR</span>}
      </div>
      <div className="run-delta-strip">
        {GROUPS.map((g) => (
          <div key={g.key} className={`rd-pill ${g.tone}`}>
            <strong>{g.sign}{(delta[g.key] as unknown[])?.length ?? 0}</strong>
            <span>{g.label}</span>
          </div>
        ))}
      </div>
      {(counts.new > 0 || counts.escalated > 0 || counts.resolved > 0) && (
        <ul className="run-delta-list">
          {delta.new?.map((h) => (
            <li key={`n-${h.hazard_id}`}><span className="rd-tag red">NEW</span>{h.title}</li>
          ))}
          {delta.escalated?.map((h) => (
            <li key={`e-${h.hazard_id}`}><span className="rd-tag amber">ESCALATED</span>{h.title}</li>
          ))}
          {delta.resolved?.map((h) => (
            <li key={`r-${h.hazard_id}`}><span className="rd-tag green">RESOLVED</span>{h.title}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
