import { useState } from "react";
import { api, type FieldConflict } from "../api/client";

type Props = { caseId: string; conflicts: FieldConflict[]; onConflictsChange: (conflicts: FieldConflict[]) => void };

export function FieldConflictPanel({ caseId, conflicts, onConflictsChange }: Props) {
  const [resolvingId, setResolvingId] = useState<string | null>(null);
  const [resolvedValue, setResolvedValue] = useState("");
  const [resolutionNote, setResolutionNote] = useState("Resolved after document review.");
  function beginResolve(conflict: FieldConflict) { setResolvingId(conflict.conflict_id); setResolvedValue(String(conflict.values[0]?.value ?? "")); setResolutionNote("Resolved after document review."); }
  async function resolve(conflictId: string) { await api.resolveFieldConflict(caseId, conflictId, resolvedValue, resolutionNote); setResolvingId(null); onConflictsChange(await api.getFieldConflicts(caseId)); }

  return <section className="panel full-width conflicts-panel">
    <div className="decision-panel-heading"><div><span className="section-kicker">Exception review</span><h2>Field conflicts</h2><p>Choose the document value that should become the confirmed case fact.</p></div><span className="tag">{conflicts.length} conflicts</span></div>
    {conflicts.length === 0 ? <div className="review-complete"><span>✓</span><div><strong>No unresolved conflicts</strong><p>Extracted documents agree on the material case facts.</p></div></div> : <div className="conflict-list">{conflicts.map((conflict) => {
      const open = conflict.status === "OPEN"; const resolving = resolvingId === conflict.conflict_id;
      return <article key={conflict.conflict_id}>
        <header><div><span className="action-id">{conflict.conflict_id}</span><h3>{humanize(conflict.field_name)}</h3><p>{conflict.explanation}</p></div><span className={`priority-pill ${conflict.severity.toLowerCase()}`}>{conflict.severity}</span></header>
        <div className="conflict-values">{conflict.values.map((value) => <button type="button" key={`${value.field_id}-${value.source_document_name}`} className={resolving && resolvedValue === String(value.value) ? "selected" : ""} onClick={() => { if (!resolving) beginResolve(conflict); setResolvedValue(String(value.value)); }} disabled={!open}><span>{value.source_document_name}</span><strong>{String(value.value)}</strong><small>{resolving && resolvedValue === String(value.value) ? "Selected" : "Choose this value"}</small></button>)}</div>
        {open && !resolving && <button className="secondary-action" type="button" onClick={() => beginResolve(conflict)}>Resolve conflict</button>}
        {resolving && <div className="conflict-resolution"><label><span>Confirmed value</span><input value={resolvedValue} onChange={(event) => setResolvedValue(event.target.value)} /></label><label><span>Decision note</span><input value={resolutionNote} onChange={(event) => setResolutionNote(event.target.value)} /></label><div className="inline-actions"><button className="review-primary" type="button" onClick={() => void resolve(conflict.conflict_id)}>Confirm resolution</button><button type="button" onClick={() => setResolvingId(null)}>Cancel</button></div></div>}
      </article>;
    })}</div>}
  </section>;
}
function humanize(value: string) { return value.replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase()); }
