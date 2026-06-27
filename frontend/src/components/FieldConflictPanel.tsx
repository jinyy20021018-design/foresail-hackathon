import { useState } from "react";
import { api, type FieldConflict } from "../api/client";

type Props = {
  caseId: string;
  conflicts: FieldConflict[];
  onConflictsChange: (conflicts: FieldConflict[]) => void;
};

export function FieldConflictPanel({ caseId, conflicts, onConflictsChange }: Props) {
  const [resolvingId, setResolvingId] = useState<string | null>(null);
  const [resolvedValue, setResolvedValue] = useState("");
  const [resolutionNote, setResolutionNote] = useState("Resolved after document review.");

  function beginResolve(conflict: FieldConflict) {
    setResolvingId(conflict.conflict_id);
    setResolvedValue(String(conflict.values[0]?.value ?? ""));
    setResolutionNote("Resolved after document review.");
  }

  async function resolve(conflictId: string) {
    await api.resolveFieldConflict(caseId, conflictId, resolvedValue, resolutionNote);
    setResolvingId(null);
    onConflictsChange(await api.getFieldConflicts(caseId));
  }

  return (
    <section className="panel full-width">
      <div className="panel-heading">
        <h2>Field Conflicts</h2>
        <span className="tag">{conflicts.length} conflicts</span>
      </div>
      {conflicts.length === 0 ? <p className="empty-state">No field conflicts detected.</p> : (
        <div className="action-grid">
          {conflicts.map((conflict) => (
            <article className="action-item" key={conflict.conflict_id}>
              <span className="action-id">{conflict.conflict_id} | {conflict.severity} | {conflict.status}</span>
              <h3>{conflict.field_name}</h3>
              <p>{conflict.explanation}</p>
              <ul>
                {conflict.values.map((value) => (
                  <li key={`${value.field_id}-${value.source_document_name}`}>{value.source_document_name}: {String(value.value)}</li>
                ))}
              </ul>
              {conflict.status === "OPEN" && resolvingId !== conflict.conflict_id && <button className="secondary-action" type="button" onClick={() => beginResolve(conflict)}>Resolve conflict</button>}
              {resolvingId === conflict.conflict_id && (
                <div className="inline-resolution-form">
                  <label><span>Resolved value</span><input value={resolvedValue} onChange={(event) => setResolvedValue(event.target.value)} /></label>
                  <label><span>Resolution note</span><input value={resolutionNote} onChange={(event) => setResolutionNote(event.target.value)} /></label>
                  <div className="inline-actions">
                    <button type="button" onClick={() => void resolve(conflict.conflict_id)}>Confirm resolution</button>
                    <button type="button" onClick={() => setResolvingId(null)}>Cancel</button>
                  </div>
                </div>
              )}
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
