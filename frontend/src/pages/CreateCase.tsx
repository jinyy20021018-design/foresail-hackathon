import { useMemo, useState } from "react";
import {
  api,
  type AutofillFieldSource,
  type CaseAutofillResult,
  type CreateCasePayload,
  type FieldConflict,
  type TradeCase,
} from "../api/client";
import type { Language } from "../i18n";
import { FilePicker } from "../components/FilePicker";

type Props = {
  onCaseCreated: (tradeCase: TradeCase, targetPath?: string) => void;
  onCancel?: () => void;
  language: Language;
};

type DocumentSlot = {
  key: string;
  label: string;
  documentType: string;
  requirement: string;
  file: File | null;
  status: "Pending" | "Selected" | "Uploading" | "Uploaded" | "Extracted" | "Failed";
};

type TraceStep = {
  label: string;
  status: "Pending" | "Running" | "Completed" | "Failed";
};

const initialForm: CreateCasePayload = {
  case_name: "",
  buyer: "",
  seller: "",
  commodity: "",
  port_of_loading: "",
  port_of_discharge: "",
  final_destination: "",
  owner: "Trade Ops",
  notes: ""
};

const initialSlots: DocumentSlot[] = [
  { key: "contract", label: "Contract / PO", documentType: "CONTRACT_PO", requirement: "Required", file: null, status: "Pending" },
  { key: "booking", label: "Booking Confirmation", documentType: "BOOKING_CONFIRMATION", requirement: "Recommended", file: null, status: "Pending" },
  { key: "lc", label: "Letter of Credit", documentType: "LETTER_OF_CREDIT", requirement: "Recommended", file: null, status: "Pending" },
  { key: "insurance", label: "Insurance Certificate", documentType: "INSURANCE_CERTIFICATE", requirement: "Optional", file: null, status: "Pending" },
  { key: "other", label: "Other Supporting Documents", documentType: "OTHER", requirement: "Optional", file: null, status: "Pending" },
];

const traceLabels = [
  "Create draft case",
  "Upload contract document",
  "Upload booking confirmation",
  "Upload letter of credit",
  "Run LLM-assisted extraction",
  "Attach evidence snippets",
  "Detect field conflicts",
  "Build autofill case details",
  "Ready for human review",
];

export function CreateCase({ onCaseCreated, onCancel }: Props) {
  const [form, setForm] = useState<CreateCasePayload>(initialForm);
  const [slots, setSlots] = useState<DocumentSlot[]>(initialSlots);
  const [caseId, setCaseId] = useState<string | null>(null);
  const [autofill, setAutofill] = useState<CaseAutofillResult | null>(null);
  const [selectedEvidence, setSelectedEvidence] = useState<{ field: string; source: AutofillFieldSource } | null>(null);
  const [editedFields, setEditedFields] = useState<Set<string>>(new Set());
  const [trace, setTrace] = useState<TraceStep[]>(traceLabels.map((label) => ({ label, status: "Pending" })));
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const selectedFiles = useMemo(() => slots.filter((slot) => slot.file), [slots]);
  const hasExtracted = Boolean(autofill);

  function updateField(field: keyof CreateCasePayload, value: string) {
    setForm((current) => ({ ...current, [field]: value }));
    setEditedFields((current) => new Set([...current, field]));
  }

  function updateSlotFile(key: string, file: File | null) {
    setSlots((current) => current.map((slot) => slot.key === key ? { ...slot, file, status: file ? "Selected" : "Pending" } : slot));
  }

  function setTraceStatus(label: string, status: TraceStep["status"]) {
    setTrace((current) => current.map((step) => step.label === label ? { ...step, status } : step));
  }

  async function extractCaseDetails() {
    if (selectedFiles.length === 0) return;
    setError(null);
    setIsLoading(true);
    setAutofill(null);
    setSelectedEvidence(null);
    setTrace(traceLabels.map((label) => ({ label, status: "Pending" })));
    try {
      setTraceStatus("Create draft case", "Running");
      const draft = await api.createCase({ notes: "Draft case created from uploaded trade documents." });
      setCaseId(draft.case_id);
      setTraceStatus("Create draft case", "Completed");

      for (const slot of selectedFiles) {
        const traceLabel = uploadTraceLabel(slot.key);
        setTraceStatus(traceLabel, "Running");
        setSlots((current) => current.map((item) => item.key === slot.key ? { ...item, status: "Uploading" } : item));
        await api.uploadDocument(draft.case_id, slot.file as File, slot.documentType);
        setSlots((current) => current.map((item) => item.key === slot.key ? { ...item, status: "Uploaded" } : item));
        setTraceStatus(traceLabel, "Completed");
      }

      setTraceStatus("Run LLM-assisted extraction", "Running");
      const extractResult = await api.extractDocuments(draft.case_id);
      const extractedCount = extractResult.extracted_fields?.length ?? 0;
      if (extractedCount === 0) {
        const diagnosticMessage = extractResult.document_diagnostics
          ?.flatMap((item) => item.errors?.map((error) => error.message) ?? [])
          .find(Boolean);
        throw new Error(
          diagnosticMessage ?? "No reliable fields were extracted from the uploaded documents. Check file format and try again."
        );
      }
      setTraceStatus("Run LLM-assisted extraction", "Completed");
      setTraceStatus("Attach evidence snippets", "Completed");
      setTraceStatus("Detect field conflicts", "Completed");

      setTraceStatus("Build autofill case details", "Running");
      let result: CaseAutofillResult;
      try {
        result = await api.autofillFromDocuments(draft.case_id);
      } catch {
        result = await api.getCaseAutofill(draft.case_id);
      }
      setAutofill(result);
      if (result.status !== "FAILED" && Object.keys(result.autofill ?? {}).length > 0) {
        setForm(result.autofill);
      }
      if (result.status === "FAILED") {
        const autofillError = result.errors?.[0]?.message ?? "Autofill could not build case details from extracted fields.";
        setTraceStatus("Build autofill case details", "Failed");
        setError(autofillError);
        setSlots((current) => current.map((slot) => slot.file ? { ...slot, status: "Failed" } : slot));
        return;
      }
      setTraceStatus("Build autofill case details", "Completed");
      setTraceStatus("Ready for human review", "Completed");
      setSlots((current) => current.map((slot) => slot.file ? { ...slot, status: "Extracted" } : slot));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Extract case details failed.");
      setTrace((current) => current.map((step) => step.status === "Running" ? { ...step, status: "Failed" } : step));
    } finally {
      setIsLoading(false);
    }
  }

  async function continueToReview() {
    setError(null);
    setIsLoading(true);
    try {
      const currentCaseId = caseId ?? (await api.createCase(cleanPayload(form))).case_id;
      let updated = await api.updateCaseDetails(currentCaseId, cleanPayload(form));
      if (autofill?.extra_facts && Object.keys(autofill.extra_facts).length > 0) {
        updated = await api.applyExtractedFacts(currentCaseId, autofill.extra_facts);
      }
      onCaseCreated(updated, `/cases/${updated.case_id}?tab=documents`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Continue to review failed.");
    } finally {
      setIsLoading(false);
    }
  }

  async function createBlankCase() {
    setError(null);
    setIsLoading(true);
    try {
      const tradeCase = await api.createCase(cleanPayload(form));
      onCaseCreated(tradeCase);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Failed to create blank case.");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <section className="create-layout">
      <header className="create-header">
        <div>
          <div className="page-kicker">Case Library / New Case</div>
          <h1>Create New Case</h1>
          <p className="lead">Upload trade documents, extract transaction facts, then review exceptions.</p>
        </div>
        <button className="secondary-action" type="button" onClick={onCancel} disabled={isLoading}>Back to Case Library</button>
      </header>

      <nav className="create-progress" aria-label="Case creation progress">
        <div className="active"><span>1</span><div><strong>Upload documents</strong><small>Select trade records</small></div></div>
        <div className={autofill ? "complete" : ""}><span>2</span><div><strong>Extract facts</strong><small>Match values and evidence</small></div></div>
        <div><span>3</span><div><strong>Review case</strong><small>Resolve exceptions</small></div></div>
      </nav>

      {error && <div className="error">{error}</div>}

      <section className="panel full-width create-upload-panel">
        <div className="create-panel-heading">
          <div>
            <span className="section-kicker">Step 1</span>
            <h2>Upload trade documents</h2>
            <p>Start with the contract, then add supporting records to improve matching confidence.</p>
          </div>
          <span className="upload-format-tag">TXT · DOCX · text-based PDF</span>
        </div>
        <div className="document-slot-grid">
          {slots.map((slot) => (
            <div className="document-slot" key={slot.key}>
              <div>
                <strong>{slot.label}</strong>
                <small className={`document-requirement ${slot.requirement.toLowerCase()}`}>{slot.requirement}</small>
              </div>
              <FilePicker accept=".txt,.docx,.pdf" fileName={slot.file?.name} onChange={(files) => updateSlotFile(slot.key, files?.[0] ?? null)} />
              <div className="inline-actions">
                <span className={`document-status ${slot.status.toLowerCase()}`}>{slot.status}</span>
                {slot.file && <button type="button" onClick={() => updateSlotFile(slot.key, null)}>Remove</button>}
              </div>
            </div>
          ))}
        </div>
        <div className="create-upload-footer">
          <div><strong>{selectedFiles.length} document{selectedFiles.length === 1 ? "" : "s"} selected</strong><span>Scanned PDF OCR is not supported yet.</span></div>
          <button className="primary-action" type="button" onClick={extractCaseDetails} disabled={selectedFiles.length === 0 || isLoading}>
            {isLoading ? "Extracting..." : "Extract Case Details"}
          </button>
        </div>
      </section>

      {(isLoading || caseId || autofill) && <DocumentProcessingTrace trace={trace} />}

      {autofill?.warnings.map((warning) => <div className="warning-banner" key={warning}>{warning}</div>)}
      {autofill?.errors?.map((error) => <div className="error" key={error.code}>{error.message}</div>)}
      {autofill?.fallback_used && <div className="warning-banner">LLM extraction is unavailable. The system used fallback extraction.</div>}
      {autofill && <ExtractionStatus result={autofill} />}

      {(autofill || caseId) && <section className="panel full-width">
        <div className="panel-heading">
          <h2>3. Auto-filled Case Details</h2>
          <span className="tag">{hasExtracted ? "Draft extracted facts" : "Manual draft"}</span>
        </div>
        <div className="form-grid">
          {caseFields.map((field) => (
            <label key={field.name} className={field.name === "notes" ? "form-span" : undefined}>
              <span>{field.label}</span>
              {field.name === "notes" ? (
                <textarea value={String(form[field.name] ?? "")} onChange={(event) => updateField(field.name, event.target.value)} />
              ) : (
                <input value={String(form[field.name] ?? "")} onChange={(event) => updateField(field.name, event.target.value)} />
              )}
              <FieldSourceBadge
                field={field.name}
                source={autofill?.field_sources[field.name]}
                edited={editedFields.has(field.name)}
                onView={setSelectedEvidence}
              />
            </label>
          ))}
        </div>
      </section>}

      {selectedEvidence && <EvidencePanel field={selectedEvidence.field} source={selectedEvidence.source} mode={autofill?.extraction_mode ?? "FALLBACK"} />}
      {autofill && <ExtractedFactsCard result={autofill} onViewEvidence={setSelectedEvidence} />}
      {autofill?.conflicts && autofill.conflicts.length > 0 && <ConflictSummary conflicts={autofill.conflicts} caseId={autofill.case_id} />}

      {(autofill || caseId) && <section className="panel full-width">
        <div className="panel-heading">
          <h2>4. Review & Continue</h2>
          <span className="tag">Human review required</span>
        </div>
        <p className="subtle">Auto-filled fields are draft extracted facts, not confirmed facts. Continue to review evidence, resolve conflicts, and confirm case facts in the Case Workspace.</p>
        <div className="form-actions">
          <button className="primary-action" type="button" onClick={continueToReview} disabled={isLoading}>
            {hasExtracted ? "Continue to Review" : "Create Case and Review"}
          </button>
          <button className="secondary-action" type="button" onClick={onCancel} disabled={isLoading}>Cancel</button>
        </div>
      </section>}

      <details className="panel full-width create-advanced">
        <summary><span><strong>Advanced options</strong><small>Create a case without extracting documents</small></span><span>＋</span></summary>
        <div><p className="subtle">Create a blank case for manual entry. Documents must be uploaded before monitoring can run.</p><button className="secondary-action" type="button" onClick={createBlankCase} disabled={isLoading}>Create Blank Case</button></div>
      </details>
    </section>
  );
}

const caseFields: Array<{ name: keyof CreateCasePayload; label: string }> = [
  { name: "case_name", label: "Case Name" },
  { name: "buyer", label: "Buyer" },
  { name: "seller", label: "Seller" },
  { name: "commodity", label: "Commodity" },
  { name: "port_of_loading", label: "Port of Loading" },
  { name: "port_of_discharge", label: "Port of Discharge" },
  { name: "final_destination", label: "Final Destination" },
  { name: "owner", label: "Owner" },
  { name: "notes", label: "Notes" },
];

function cleanPayload(form: CreateCasePayload): CreateCasePayload {
  return Object.fromEntries(Object.entries(form).filter(([, value]) => value !== undefined && String(value).trim() !== "")) as CreateCasePayload;
}

function uploadTraceLabel(key: string) {
  if (key === "contract") return "Upload contract document";
  if (key === "booking") return "Upload booking confirmation";
  if (key === "lc") return "Upload letter of credit";
  return "Upload contract document";
}

function FieldSourceBadge({ field, source, edited, onView }: { field: string; source?: AutofillFieldSource; edited: boolean; onView: (value: { field: string; source: AutofillFieldSource }) => void }) {
  if (!source && !edited) return <small>Manual entry</small>;
  return (
    <small>
      {edited ? "Manually edited" : `Auto-filled from ${source?.source_document ?? "document"} · confidence ${source?.confidence ?? "-"}`}
      {source?.conflict ? " · Conflict detected" : ""}
      {source && <button className="link-button evidence-link" type="button" onClick={() => onView({ field, source })}>Evidence</button>}
    </small>
  );
}

function EvidencePanel({ field, source, mode }: { field: string; source: AutofillFieldSource; mode: string }) {
  return (
    <section className="panel full-width evidence-viewer">
      <div className="panel-heading"><h2>Field Evidence</h2><span className="tag">{mode}</span></div>
      <dl className="field-grid">
        <div><dt>Field</dt><dd>{field}</dd></div>
        <div><dt>Source</dt><dd>{source.source_document || "-"}</dd></div>
        <div><dt>Confidence</dt><dd>{source.confidence ?? "-"}</dd></div>
        <div><dt>Review Status</dt><dd>{source.review_status || "PENDING"}</dd></div>
      </dl>
      <p><mark>{source.evidence || "No evidence snippet available."}</mark></p>
    </section>
  );
}

function ExtractionStatus({ result }: { result: CaseAutofillResult }) {
  const status = result.status ?? "PARTIAL";
  const isFailure = ["FAILED", "UNSUPPORTED", "NEEDS_VISION"].includes(status);
  return (
    <section className="panel full-width">
      <div className="panel-heading">
        <h2>2. Extract Case Details</h2>
        <span className={isFailure ? "badge status-action-required" : "tag"}>{status}</span>
      </div>
      <p className="subtle">{result.document_processing_summary}</p>
      {isFailure ? (
        <div className="error">
          Extraction failed. No reliable fields were extracted.
        </div>
      ) : status === "PARTIAL" ? (
        <div className="warning-banner">Partial extraction. Some fields were extracted, but key fields may be missing.</div>
      ) : (
        <div className="success-banner">Fields extracted successfully. Please review evidence before confirming facts.</div>
      )}
      <div className="mini-metrics">
        <div><strong>{result.extraction_mode}</strong><span>Extraction Mode</span></div>
        <div><strong>{result.llm_used ? "Yes" : "No"}</strong><span>LLM Used</span></div>
        <div><strong>{result.fallback_used ? "Yes" : "No"}</strong><span>Fallback Used</span></div>
        <div><strong>{result.document_diagnostics?.some((item) => item.status === "NEEDS_VISION") ? "Yes" : "No"}</strong><span>Vision Required</span></div>
      </div>
      {result.document_diagnostics && result.document_diagnostics.length > 0 && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Document</th>
                <th>Status</th>
                <th>Mode</th>
                <th>PDF Type</th>
                <th>Fields</th>
                <th>Missing Fields</th>
                <th>Messages</th>
              </tr>
            </thead>
            <tbody>
              {result.document_diagnostics.map((item) => (
                <tr key={item.document_id}>
                  <td>{item.filename}</td>
                  <td>{item.status}</td>
                  <td>{item.extraction_mode}</td>
                  <td>{item.pdf_type ?? "-"}</td>
                  <td>{item.fields_extracted_count}</td>
                  <td>{item.missing_fields.join(", ") || "-"}</td>
                  <td>{[...item.warnings, ...item.errors.map((error) => error.message)].join(" ") || "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function ExtractedFactsCard({ result, onViewEvidence }: { result: CaseAutofillResult; onViewEvidence: (value: { field: string; source: AutofillFieldSource }) => void }) {
  return (
    <section className="panel full-width">
      <div className="panel-heading"><h2>Extracted Transaction Facts</h2><span className="tag">Pending review</span></div>
      <div className="field-grid">
        {Object.entries(result.extra_facts).map(([field, value]) => (
          <div key={field}>
            <dt>{field.replace(/_/g, " ")}</dt>
            <dd>{String(value)}</dd>
            <FieldSourceBadge field={field} source={result.field_sources[field]} edited={false} onView={onViewEvidence} />
          </div>
        ))}
      </div>
    </section>
  );
}

function ConflictSummary({ conflicts, caseId }: { conflicts: FieldConflict[]; caseId: string }) {
  return (
    <section className="panel full-width">
      <div className="panel-heading"><h2>Field Conflicts</h2><span className="badge status-action-required">{conflicts.length} open</span></div>
      <div className="warning-banner">High severity conflicts detected. Please review conflicts before confirming case facts.</div>
      <ul className="rule-list">
        {conflicts.map((conflict) => (
          <li key={conflict.conflict_id}>
            <strong>{conflict.field_name} conflict</strong>: {conflict.explanation} Severity: {conflict.severity}. Status: {conflict.status}.
          </li>
        ))}
      </ul>
      <button className="secondary-action" type="button" onClick={() => window.location.assign(`/cases/${caseId}?tab=conflicts`)}>
        Review in Case Workspace
      </button>
    </section>
  );
}

function DocumentProcessingTrace({ trace }: { trace: TraceStep[] }) {
  const activeCount = trace.filter((step) => step.status !== "Pending").length;
  return (
    <details className="panel full-width trace-disclosure" open={activeCount > 0}>
      <summary><span><strong>Document Processing</strong><small>{activeCount > 0 ? `${activeCount} steps updated` : "Trace appears when extraction starts"}</small></span><span className="tag">{activeCount}/{trace.length}</span></summary>
      <ol className="agent-trace">
          {trace.map((step, index) => (
            <li key={step.label}>
              <span className="trace-step-number">{index + 1}</span>
              <div><div className="trace-title"><strong>{step.label}</strong><span>{step.status}</span></div></div>
            </li>
          ))}
        </ol>
    </details>
  );
}
