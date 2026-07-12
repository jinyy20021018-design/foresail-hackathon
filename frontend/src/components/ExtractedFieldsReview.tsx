import { Fragment, useState } from "react";
import { api, type DocumentRecord, type ExtractedField, type FieldEvidence } from "../api/client";
import { type Language } from "../i18n";

type Props = {
  caseId: string;
  fields: ExtractedField[];
  onFieldsChange: (fields: ExtractedField[]) => void;
  onDocumentsChange?: (documents: DocumentRecord[]) => void;
  onError: (message: string) => void;
  language: Language;
  canExtract?: boolean;
};

export function ExtractedFieldsReview({ caseId, fields, onFieldsChange, onDocumentsChange, onError, canExtract = true }: Props) {
  const [evidence, setEvidence] = useState<FieldEvidence | null>(null);
  const [editingFieldId, setEditingFieldId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");
  const [view, setView] = useState<"review" | "all">("review");
  const [busyFieldId, setBusyFieldId] = useState<string | null>(null);
  const [isExtracting, setIsExtracting] = useState(false);
  const [isApprovingAll, setIsApprovingAll] = useState(false);
  const [evidenceLoadingId, setEvidenceLoadingId] = useState<string | null>(null);

  const needsReview = fields.filter((field) => !isApproved(field));
  const bulkApprovable = needsReview.filter((field) => field.review_status.toUpperCase() !== "REJECTED");
  const approvedCount = fields.length - needsReview.length;
  const visibleFields = view === "review" ? needsReview : fields;
  const averageConfidence = fields.length
    ? Math.round(fields.reduce((sum, field) => sum + field.confidence, 0) / fields.length * 100)
    : 0;

  async function refresh() {
    onFieldsChange(await api.getExtractedFields(caseId));
  }

  async function extract() {
    if (!canExtract) {
      onError("Upload at least one document before extracting fields.");
      return;
    }
    setIsExtracting(true);
    try {
      const result = await api.extractDocuments(caseId);
      onFieldsChange(result.extracted_fields);
      onDocumentsChange?.(result.documents);
      setEvidence(null);
      setView("review");
    } catch (error) {
      onError(error instanceof Error ? error.message : "Extraction failed.");
    } finally {
      setIsExtracting(false);
    }
  }

  async function approve(fieldId: string) {
    await runFieldAction(fieldId, () => api.approveField(caseId, fieldId));
  }

  async function approveAll() {
    if (bulkApprovable.length === 0) return;
    setIsApprovingAll(true);
    try {
      const results = await Promise.allSettled(bulkApprovable.map((field) => api.approveField(caseId, field.field_id)));
      await refresh();
      const failures = results.filter((result) => result.status === "rejected").length;
      if (failures) onError(`${failures} fields could not be accepted. Please review them individually.`);
    } catch (error) {
      onError(error instanceof Error ? error.message : "Could not accept all fields.");
    } finally {
      setIsApprovingAll(false);
    }
  }

  function beginEdit(field: ExtractedField) {
    setEditingFieldId(field.field_id);
    setEditValue(String(field.edited_value ?? field.value ?? ""));
  }

  async function saveEdit(fieldId: string) {
    await runFieldAction(fieldId, () => api.editField(caseId, fieldId, editValue));
    setEditingFieldId(null);
  }

  async function reject(fieldId: string) {
    await runFieldAction(fieldId, () => api.rejectField(caseId, fieldId));
  }

  async function runFieldAction(fieldId: string, action: () => Promise<unknown>) {
    setBusyFieldId(fieldId);
    try {
      await action();
      await refresh();
    } catch (error) {
      onError(error instanceof Error ? error.message : "Could not update this field.");
    } finally {
      setBusyFieldId(null);
    }
  }

  async function selectField(field: ExtractedField) {
    if (evidence?.field_name === field.field_name) {
      setEvidence(null);
      return;
    }
    setEvidenceLoadingId(field.field_id);
    try {
      setEvidence(await api.getFieldEvidence(caseId, field.field_id));
    } catch (error) {
      onError(error instanceof Error ? error.message : "Could not load source evidence.");
    } finally {
      setEvidenceLoadingId(null);
    }
  }

  return (
    <section className="panel full-width extracted-review">
      <div className="review-header">
        <div>
          <span className="section-kicker">Document verification</span>
          <h2>Review extracted facts</h2>
          <p>The system matches values across contracts, letters of credit, and shipping documents. Review exceptions before turning matched values into confirmed case facts.</p>
        </div>
        <div className="review-header-actions">
          <button className="secondary-action" type="button" onClick={extract} disabled={!canExtract || isExtracting} title={!canExtract ? "Upload a document first" : "Run document extraction again"}>
            {isExtracting ? "Extracting…" : "Re-run extraction"}
          </button>
        </div>
      </div>

      {fields.length === 0 ? (
        <div className="review-empty">
          <span>1</span><div><strong>Upload documents first</strong><p>Then run extraction to turn document text into reviewable case facts.</p></div>
        </div>
      ) : (
        <>
          <div className="review-summary" aria-label="Extraction review summary">
            <span><b className={needsReview.length ? "warning-text" : "success-text"}>{needsReview.length}</b> need review</span>
            <span><b>{approvedCount}</b> confirmed</span>
            <span><b>{averageConfidence}%</b> average confidence</span>
          </div>

          <div className="review-toolbar">
            <div className="review-view-toggle" role="tablist" aria-label="Filter extracted fields">
              <button type="button" role="tab" aria-selected={view === "review"} className={view === "review" ? "active" : ""} onClick={() => setView("review")}>Needs review <span>{needsReview.length}</span></button>
              <button type="button" role="tab" aria-selected={view === "all"} className={view === "all" ? "active" : ""} onClick={() => setView("all")}>All fields <span>{fields.length}</span></button>
            </div>
            <div className="review-toolbar-actions">
              <p>Accept, edit, or exclude extracted values.</p>
              {bulkApprovable.length > 0 && <button className="primary-action" type="button" data-guide="doc-accept-all" onClick={() => void approveAll()} disabled={isApprovingAll}>
                {isApprovingAll ? "Accepting…" : `Accept all ${bulkApprovable.length}`}
              </button>}
            </div>
          </div>

          <div className="table-wrap extracted-fields-table">
              {visibleFields.length === 0 ? (
                <div className="review-complete"><span>✓</span><div><strong>Everything is confirmed</strong><p>No extracted fields need attention.</p></div><button type="button" onClick={() => setView("all")}>View all fields</button></div>
              ) : (
                <table>
                  <thead><tr><th>Case fact</th><th>Extracted value</th><th>Confidence</th><th>Review state</th><th>Action</th></tr></thead>
                  <tbody>
                    {visibleFields.map((field) => {
                      const approved = isApproved(field);
                      const rejected = field.review_status.toUpperCase() === "REJECTED";
                      const busy = busyFieldId === field.field_id;
                      return (
                        <Fragment key={field.field_id}>
                        <tr className={evidence?.field_name === field.field_name ? "selected-row" : undefined}>
                          <td><strong>{field.display_name}</strong><button className="evidence-link" type="button" aria-expanded={evidence?.field_name === field.field_name} onClick={() => void selectField(field)}>{evidenceLoadingId === field.field_id ? "Loading…" : evidence?.field_name === field.field_name ? "Hide details" : "View details"}</button></td>
                          <td>{editingFieldId === field.field_id
                            ? (field.field_name === "trade_perspective"
                              ? <select className="inline-edit-input" value={editValue} onChange={(event) => setEditValue(event.target.value)} aria-label={`Edit ${field.display_name}`} autoFocus>
                                  <option value="SELLER">SELLER</option>
                                  <option value="BUYER">BUYER</option>
                                </select>
                              : <input className="inline-edit-input" value={editValue} onChange={(event) => setEditValue(event.target.value)} aria-label={`Edit ${field.display_name}`} autoFocus />)
                            : <span className="extracted-value">{String(field.edited_value ?? field.value ?? "Not found")}</span>}</td>
                          <td><Confidence value={field.confidence} /></td>
                          <td><ReviewState status={field.review_status} /></td>
                          <td>
                            <div className="review-actions">
                              {editingFieldId === field.field_id ? <>
                                <button className="review-primary" type="button" disabled={busy} onClick={() => void saveEdit(field.field_id)}>Save change</button>
                                <button type="button" disabled={busy} onClick={() => setEditingFieldId(null)}>Cancel</button>
                              </> : <>
                                {!approved && <button className="review-primary" type="button" disabled={busy} onClick={() => void approve(field.field_id)}>{rejected ? "Accept instead" : "Accept"}</button>}
                                <button type="button" disabled={busy} onClick={() => beginEdit(field)}>Edit</button>
                                {!approved && !rejected && <button className="review-reject" type="button" disabled={busy} onClick={() => void reject(field.field_id)}>Exclude</button>}
                              </>}
                            </div>
                          </td>
                        </tr>
                        {evidence?.field_name === field.field_name && (
                          <tr className="inline-evidence-row">
                            <td colSpan={5}>
                              <div className="inline-evidence">
                                <div className="inline-evidence-meta">
                                  <span className="section-kicker">Source evidence</span>
                                  <strong>{evidence.source_document_name}</strong>
                                  <small>{evidence.page_number ? `Page ${evidence.page_number}` : "Page not available"}</small>
                                </div>
                                <div>
                                  <span className="section-kicker">Extracted value</span>
                                  <strong>{String(evidence.value ?? "Not found")}</strong>
                                  <Confidence value={evidence.confidence} />
                                </div>
                                <div className="inline-evidence-quote">
                                  <span className="section-kicker">Matching document text</span>
                                  <blockquote>“{evidence.evidence_text}”</blockquote>
                                </div>
                                <button className="inline-evidence-close" type="button" aria-label="Close evidence details" onClick={() => setEvidence(null)}>×</button>
                              </div>
                            </td>
                          </tr>
                        )}
                        </Fragment>
                      );
                    })}
                  </tbody>
                </table>
              )}
          </div>
        </>
      )}
    </section>
  );
}

function isApproved(field: ExtractedField) {
  return field.review_status.toUpperCase() === "APPROVED";
}

function Confidence({ value }: { value: number }) {
  const percent = Math.round(value * 100);
  const tone = percent >= 90 ? "high" : percent >= 70 ? "medium" : "low";
  return <span className={`confidence ${tone}`}><i><span style={{ width: `${percent}%` }} /></i><b>{percent}%</b></span>;
}

function ReviewState({ status }: { status: string }) {
  const normalized = status.toUpperCase();
  const approved = normalized === "APPROVED";
  const rejected = normalized === "REJECTED";
  return <span className={`review-state ${approved ? "approved" : rejected ? "rejected" : "pending"}`}><i />{approved ? "Confirmed" : rejected ? "Excluded" : "Needs review"}</span>;
}
