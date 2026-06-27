import { useState } from "react";
import { api, type DocumentRecord } from "../api/client";
import { type Language } from "../i18n";
import { FilePicker } from "./FilePicker";

type Props = {
  caseId: string;
  documents: DocumentRecord[];
  onDocumentsChange: (documents: DocumentRecord[]) => void;
  onError: (message: string) => void;
  language: Language;
};

export function DocumentUploadPanel({ caseId, documents, onDocumentsChange, onError }: Props) {
  const [documentType, setDocumentType] = useState("CONTRACT_PO");
  const [isUploading, setIsUploading] = useState(false);

  async function uploadFiles(files: FileList | null) {
    if (!files || files.length === 0) {
      return;
    }
    setIsUploading(true);
    try {
      const uploaded: DocumentRecord[] = [];
      for (const file of Array.from(files)) {
        uploaded.push(await api.uploadDocument(caseId, file, documentType));
      }
      onDocumentsChange([...documents, ...uploaded]);
    } catch (error) {
      onError(error instanceof Error ? error.message : "Upload failed.");
    } finally {
      setIsUploading(false);
    }
  }

  return (
    <section className="panel full-width">
      <div className="panel-heading">
        <h2>Document Upload</h2>
        <span className="tag">MVP 2.0</span>
      </div>
      <div className="upload-row">
        <select value={documentType} onChange={(event) => setDocumentType(event.target.value)}>
          <option value="CONTRACT_PO">Contract / PO</option>
          <option value="BOOKING_CONFIRMATION">Booking / Shipping Notice</option>
          <option value="LETTER_OF_CREDIT">Letter of Credit</option>
          <option value="INSURANCE_CERTIFICATE">Insurance Certificate</option>
        </select>
        <FilePicker multiple accept=".txt,.docx,.pdf,.png,.jpg,.jpeg" disabled={isUploading} onChange={uploadFiles} />
      </div>
      {isUploading && <p className="subtle">Uploading...</p>}
      {documents.length > 0 && (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Document</th>
                <th>Type</th>
                <th>Parse Status</th>
                <th>Extraction</th>
                <th>Mode</th>
                <th>PDF Type</th>
                <th>Fields</th>
                <th>Messages</th>
              </tr>
            </thead>
            <tbody>
              {documents.map((document) => (
                <tr key={document.document_id}>
                  <td>{document.filename}</td>
                  <td>{document.document_type}</td>
                  <td>{document.parse_status}</td>
                  <td>{document.extraction_status ?? "NOT_RUN"}</td>
                  <td>{document.extraction_mode ?? "-"}</td>
                  <td>{document.pdf_type ?? "-"}</td>
                  <td>{document.fields_extracted_count ?? 0}</td>
                  <td>
                    {document.extraction_diagnostics
                      ? [
                          ...document.extraction_diagnostics.warnings,
                          ...document.extraction_diagnostics.errors.map((error) => error.message)
                        ].join(" ") || "-"
                      : "-"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
