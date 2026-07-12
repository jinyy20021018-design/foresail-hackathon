import { useEffect, useMemo, useState } from "react";
import { api, type ActionSet, type RecommendedAction } from "../api/client";
import { t, translate, type Language } from "../i18n";

type Props = {
  caseId: string;
  actionSets: ActionSet[];
  language: Language;
  onActionSetsChange: (sets: ActionSet[]) => void;
  onConfirmed: (set: ActionSet) => void;
  onError: (message: string | null) => void;
};

export function ActionBoard({ caseId, actionSets, language, onActionSetsChange, onConfirmed, onError }: Props) {
  const [selectedSetId, setSelectedSetId] = useState<string>(actionSets[actionSets.length - 1]?.action_set_id ?? "");
  const [editingActions, setEditingActions] = useState<RecommendedAction[]>([]);
  const [busy, setBusy] = useState(false);
  const selectedSet = useMemo<ActionSet | undefined>(() => actionSets.find((item: ActionSet) => item.action_set_id === selectedSetId) ?? actionSets[actionSets.length - 1], [actionSets, selectedSetId]);
  const editable = selectedSet?.status === "CANDIDATE";

  useEffect(() => {
    if (selectedSet) {
      setSelectedSetId(selectedSet.action_set_id);
      setEditingActions(selectedSet.actions.map((item) => ({ ...item })));
    } else {
      setEditingActions([]);
    }
  }, [selectedSet?.action_set_id, selectedSet?.updated_at]);

  async function refresh(preferredId?: string) {
    const sets = await api.listActionSets(caseId);
    onActionSetsChange(sets);
    if (preferredId) setSelectedSetId(preferredId);
  }

  async function generate() {
    setBusy(true);
    onError(null);
    try {
      const created = await api.generateActionSet(caseId);
      await refresh(created.action_set_id);
    } catch (caught) {
      onError(caught instanceof Error ? caught.message : "LLM action generation failed.");
    } finally {
      setBusy(false);
    }
  }

  async function clone() {
    if (!selectedSet) return;
    setBusy(true);
    onError(null);
    try {
      const created = await api.cloneActionSet(caseId, selectedSet.action_set_id);
      await refresh(created.action_set_id);
    } catch (caught) {
      onError(caught instanceof Error ? caught.message : "Could not create a new action version.");
    } finally {
      setBusy(false);
    }
  }

  async function confirm() {
    if (!selectedSet || !editingActions.some((item) => item.selected)) return;
    setBusy(true);
    onError(null);
    try {
      await api.updateActionSet(caseId, selectedSet.action_set_id, editingActions);
      const confirmed = await api.confirmActionSet(caseId, selectedSet.action_set_id);
      await refresh(confirmed.action_set_id);
      onConfirmed(confirmed);
    } catch (caught) {
      onError(caught instanceof Error ? caught.message : "Action confirmation failed.");
    } finally {
      setBusy(false);
    }
  }

  function updateAction(actionId: string, patch: Partial<RecommendedAction>) {
    setEditingActions((items) => items.map((item) => item.action_id === actionId ? { ...item, ...patch } : item));
  }

  const selectedCount = editingActions.filter((item) => item.selected).length;
  return (
    <section className="panel full-width">
      <div className="panel-heading action-review-heading">
        <div>
          <span className="section-kicker">LLM action review</span>
          <h2>{t(language, "actionBoard")}</h2>
          <p className="subtle">Choose and edit the actions that the treatment plans must use.</p>
        </div>
        <div className="inline-actions">
          {actionSets.length > 0 && <select aria-label="Action version" value={selectedSet?.action_set_id ?? ""} onChange={(event) => setSelectedSetId(event.target.value)}>{[...actionSets].reverse().map((item) => <option key={item.action_set_id} value={item.action_set_id}>Version {item.version} · {item.status}</option>)}</select>}
          <button type="button" onClick={generate} disabled={busy}>{busy ? "Working..." : actionSets.length ? "Regenerate with LLM" : "Generate Actions with LLM"}</button>
          {selectedSet?.status === "CONFIRMED" && <button type="button" onClick={clone} disabled={busy}>Create New Action Version</button>}
        </div>
      </div>
      {!selectedSet ? <div className="empty-block"><h3>No LLM actions yet</h3><p>Run monitoring, then generate action candidates.</p></div> : <>
        <div className="notice">{selectedSet.action_set_id} · Version {selectedSet.version} · {selectedSet.status} · {selectedSet.model}</div>
        {editable && <div className="inline-actions action-review-controls"><label><input type="checkbox" checked={selectedCount === editingActions.length && editingActions.length > 0} onChange={(event) => setEditingActions((items) => items.map((item) => ({ ...item, selected: event.target.checked })))} /> Select all</label><span>{selectedCount} selected</span><button className="primary-action" type="button" onClick={confirm} disabled={busy || selectedCount === 0}>Confirm Selected Actions</button></div>}
        <div className="action-grid">
          {editingActions.map((action) => (
            <article className={`action-item ${action.selected ? "selected" : "excluded"}`} key={action.action_id}>
              <div className="action-select-row">
                <label><input type="checkbox" checked={Boolean(action.selected)} disabled={!editable} onChange={(event) => updateAction(action.action_id, { selected: event.target.checked })} /> Include</label>
                <span className="action-id">{action.action_id}</span>
              </div>
              {editable ? <input className="action-title-input" value={action.title} onChange={(event) => updateAction(action.action_id, { title: event.target.value })} /> : <h3>{translate.action(language, action.title)}</h3>}
              <dl>
                <EditField label={t(language, "owner")} value={action.owner_role} editable={editable} onChange={(value) => updateAction(action.action_id, { owner_role: value })} />
                <div><dt>{t(language, "priority")}</dt><dd>{editable ? <select value={action.priority} onChange={(event) => updateAction(action.action_id, { priority: event.target.value })}>{["Low", "Medium", "High", "Critical"].map((item) => <option key={item}>{item}</option>)}</select> : action.priority}</dd></div>
                <EditField label={t(language, "deadline")} value={action.deadline_date ?? ""} editable={editable} type="date" onChange={(value) => updateAction(action.action_id, { deadline_date: value })} />
                <div><dt>{t(language, "exposure")}</dt><dd>{translate.exposure(language, action.related_exposure)}</dd></div>
                <div><dt>Responsible</dt><dd>{action.responsible_party ?? "UNKNOWN"}</dd></div>
                <div><dt>Status</dt><dd>{action.status}</dd></div>
              </dl>
              {action.rationale && <p className="subtle">{action.rationale}</p>}
            </article>
          ))}
        </div>
      </>}
    </section>
  );
}

function EditField({ label, value, editable, type = "text", onChange }: { label: string; value: string; editable: boolean; type?: string; onChange: (value: string) => void }) {
  return <div><dt>{label}</dt><dd>{editable ? <input type={type} value={value} onChange={(event) => onChange(event.target.value)} /> : value}</dd></div>;
}
