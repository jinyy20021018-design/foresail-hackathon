const API_BASE = "http://127.0.0.1:8000";

export type TradePerspective = "BUYER" | "SELLER";

export type TradeCase = {
  case_id: string;
  status: string;
  case_name?: string;
  buyer?: string;
  seller?: string;
  commodity?: string;
  vessel: string;
  route: string;
  port_of_loading: string;
  port_of_discharge: string;
  final_destination: string;
  etd: string;
  eta: string;
  latest_shipment_date: string;
  payment_method: string;
  incoterm: string;
  incoterm_named_place?: string;
  trade_perspective?: TradePerspective;
  owner?: string;
  notes?: string;
  created_at?: string;
  updated_at?: string;
  uploaded_files?: string[];
  mock_extraction_note?: string;
};

export type CreateCasePayload = {
  case_name?: string;
  buyer?: string;
  seller?: string;
  commodity?: string;
  port_of_loading?: string;
  port_of_discharge?: string;
  final_destination?: string;
  owner?: string;
  notes?: string;
};

export type AutofillFieldSource = {
  source_document?: string | null;
  confidence?: number | null;
  evidence?: string | null;
  review_status?: string | null;
  conflict?: boolean;
};

export type ExtractionError = {
  code: string;
  message: string;
};

export type DocumentExtractionDiagnostic = {
  document_id: string;
  filename: string;
  document_type: string;
  extraction_mode: string;
  status: "SUCCESS" | "PARTIAL" | "FAILED" | "UNSUPPORTED" | "NEEDS_VISION" | string;
  text_extraction_status: string;
  pdf_type?: "TEXT_PDF" | "SCANNED_PDF" | "UNKNOWN_PDF" | string | null;
  llm_used: boolean;
  fallback_used: boolean;
  vision_used: boolean;
  openai_file_used: boolean;
  fields_extracted_count: number;
  missing_fields: string[];
  warnings: string[];
  errors: ExtractionError[];
};

export type CaseAutofillResult = {
  case_id: string;
  status?: "SUCCESS" | "PARTIAL" | "FAILED" | "UNSUPPORTED" | "NEEDS_VISION" | string;
  extraction_mode: "LLM" | "FALLBACK" | string;
  llm_used: boolean;
  fallback_used: boolean;
  autofill: CreateCasePayload;
  extra_facts: Record<string, string | number | boolean | null>;
  field_sources: Record<string, AutofillFieldSource>;
  conflicts: FieldConflict[];
  document_diagnostics?: DocumentExtractionDiagnostic[];
  warnings: string[];
  errors?: ExtractionError[];
  document_processing_summary?: string;
};

export type CaseSummary = {
  case_id: string;
  vessel?: string | null;
  route?: string | null;
  port_of_loading?: string | null;
  port_of_discharge?: string | null;
  final_destination?: string | null;
  status?: string | null;
  risk_level?: "High" | "Medium" | "Low" | string;
  next_deadline?: {
    label: string;
    date: string;
  } | null;
  open_actions_count?: number;
  information_gaps_count?: number;
  open_conflicts_count?: number;
  high_conflicts_count?: number;
  last_agent_run_at?: string | null;
  last_agent_run_id?: string | null;
  owner?: string | null;
  updated_at?: string | null;
};

export type WatchProfile = {
  case_id: string;
  watched_vessel: string;
  watched_ports: string[];
  watched_route_regions: string[];
  shipment_window: Record<string, string>;
  deadline_sensitivity: string[];
  risk_categories: string[];
  alert_rules: string[];
};

export type RelevanceResult = {
  event_id: string;
  title: string;
  classification: "Relevant" | "Watch" | "Irrelevant";
  score: number;
  raw_score?: number;
  display_score?: number;
  matched_factors: string[];
  explanation: string;
  mapped_exposures: string[];
  source?: string | null;
  source_type?: string | null;
  event_type?: string | null;
  url?: string | null;
  confidence?: number | null;
};

export type ExternalEvent = {
  event_id: string;
  case_id?: string | null;
  agent_run_id?: string | null;
  source: string;
  source_type: string;
  event_type: string;
  title: string;
  description: string;
  event_time?: string | null;
  published_at?: string | null;
  locations: string[];
  affected_ports: string[];
  affected_routes: string[];
  affected_vessels: string[];
  severity: string;
  confidence: number;
  url?: string | null;
  dedup_key: string;
  created_at: string;
  matched_query_ids?: string[];
  matched_terms?: string[];
};

export type EventConfig = {
  event_source_mode: "MOCK" | "REAL" | "HYBRID" | string;
  connectors: string[];
  gdelt_enabled?: boolean;
  open_meteo_enabled?: boolean;
  gdelt_lookback_days?: number;
  gdelt_max_records?: number;
  external_event_query_limit?: number;
  real_event_location_limit?: number;
  open_meteo_forecast_days?: number;
  real_search_enabled?: boolean;
  real_search_provider?: string;
  real_search_lookback_days?: number;
  configured_feeds_count?: number;
  use_llm_event_extraction?: boolean;
};

export type EventIngestionResult = {
  mode: string;
  connectors_called: string[];
  events_raw_count: number;
  events_normalized_count: number;
  events_deduped_count: number;
  events: ExternalEvent[];
  connector_errors: Array<{ connector: string; error: string }>;
  connector_results?: Array<Record<string, unknown>>;
  search_summary?: Record<string, unknown>;
  deduplication?: Record<string, unknown>;
};

export type ExternalEventQuery = {
  query_id: string;
  query_text: string;
  query_type: string;
  priority: string;
  source_hint: string;
  created_from: string[];
};

export type ExternalEventSearchResult = {
  case_id: string;
  mode: string;
  queries_generated: ExternalEventQuery[];
  gdelt_articles_fetched?: number;
  gdelt_events_extracted?: ExternalEvent[];
  weather_locations_checked?: number;
  weather_events_extracted?: ExternalEvent[];
  rss_items_fetched?: number;
  rss_items_matched?: number;
  events_extracted: ExternalEvent[];
  events_extracted_count: number;
  connector_errors: Array<{ connector?: string; query_id?: string; query?: string; location?: string; feed_url?: string; title?: string; error: string }>;
  warnings: string[];
  deduplication: Record<string, unknown>;
};

export type RealEventConfig = {
  event_source_mode: string;
  gdelt_enabled: boolean;
  open_meteo_enabled: boolean;
  gdelt_lookback_days: number;
  gdelt_max_records: number;
  external_event_query_limit?: number;
  real_event_location_limit?: number;
  open_meteo_forecast_days: number;
  use_llm_event_extraction: boolean;
};

export type RiskExposure = {
  category: string;
  impact: string;
  severity: string;
  party_perspective?: TradePerspective;
  affected_party?: string;
  responsible_party?: string;
  incoterm_basis?: string;
  cif_scenario?: string;
  evidence_event_ids: string[];
  trigger_event_ids?: string[];
  watch_event_ids?: string[];
};

export type RiskSummary = {
  triggered: boolean;
  trigger_events: string[];
  watch_events_considered?: string[];
  trade_perspective?: TradePerspective;
  incoterm_basis?: string;
  exposures: RiskExposure[];
};

export type RecommendedAction = {
  action_id: string;
  title: string;
  owner_role: string;
  priority: string;
  deadline: string;
  status: string;
  related_exposure: string;
  party_perspective?: TradePerspective;
  responsible_party?: "BUYER" | "SELLER" | "SHARED" | "UNKNOWN" | string;
  incoterm_basis?: string;
};

export type StatusTimelineEntry = {
  status: string;
  reason: string;
};

export type AgentRunTraceStep = {
  step: number;
  step_number?: number;
  name: string;
  trace_id?: string;
  step_name?: string;
  status: string;
  description: string;
  tool_or_service: string;
  output_summary: string;
};

export type DocumentRecord = {
  document_id: string;
  case_id: string;
  document_type: string;
  filename: string;
  file_path: string;
  uploaded_at: string;
  parse_status: string;
  extraction_status?: string;
  extraction_mode?: string | null;
  pdf_type?: string | null;
  fields_extracted_count?: number;
  extraction_diagnostics?: DocumentExtractionDiagnostic | null;
  raw_text: string;
};

export type ExtractedField = {
  field_id: string;
  case_id: string;
  field_name: string;
  display_name: string;
  value: string | number | boolean | null;
  source_document_id: string;
  source_document_name: string;
  evidence_text: string;
  page_number: number | null;
  confidence: number;
  requires_confirmation: boolean;
  review_status: string;
  edited_value: string | number | boolean | null;
};

export type ConfirmedFacts = Record<string, string | number | boolean | null>;

export type ObligationDeadline = {
  obligation_id: string;
  name: string;
  source: string;
  deadline_date: string;
  current_assessment: string;
  severity: string;
  recommended_action: string;
  status: string;
};

export type InformationGap = {
  gap_id: string;
  title: string;
  reason: string;
  blocks_decision: string;
  owner_role: string;
  priority: string;
  status: string;
};

export type ActionDraft = {
  draft_id: string;
  draft_type: string;
  title: string;
  recipient_role: string;
  body: string;
  related_actions: string[];
  status: string;
  requires_user_review: boolean;
  rejection_reason?: string;
};

export type ResidualRisk = {
  residual_risk_id: string;
  case_id: string;
  plan_id: string;
  risk_title: string;
  description: string;
  severity: string;
  reason_not_fully_covered: string;
  monitoring_trigger: string;
  owner_role: string;
  status: string;
  perspective?: TradePerspective;
  incoterm_basis?: string;
  created_at: string;
  updated_at: string;
};

export type TreatmentPlan = {
  plan_id: string;
  case_id: string;
  plan_type: "LOW_COST" | "BALANCED" | "MAX_PROTECTION" | string;
  plan_name: string;
  summary: string;
  recommendation_level: string;
  estimated_cost_level: string;
  estimated_cost_amount: number | null;
  estimated_cost_currency: string | null;
  estimated_time_to_execute: string | null;
  approval_required: boolean;
  approval_roles: string[];
  covered_risks: string[];
  residual_risks: ResidualRisk[];
  required_actions: string[];
  linked_action_ids: string[];
  linked_gap_ids: string[];
  linked_obligation_ids: string[];
  assumptions: string[];
  preconditions: string[];
  recheck_triggers: string[];
  rationale: string;
  status: string;
  perspective?: TradePerspective;
  incoterm_basis?: string;
  created_at: string;
  updated_at: string;
};

export type ApprovalPackage = {
  approval_package_id: string;
  case_id: string;
  plan_id: string;
  title: string;
  summary: string;
  recommended_plan_name: string;
  estimated_cost_level: string;
  estimated_cost_amount: number | null;
  estimated_cost_currency: string | null;
  covered_risks: string[];
  residual_risks: string[];
  required_actions: string[];
  approval_roles: string[];
  approval_status: string;
  decision_note: string | null;
  approval_scope?: string;
  conflict_safe_mode?: boolean;
  perspective?: TradePerspective;
  incoterm_basis?: string;
  created_at: string;
  updated_at: string;
};

export type CifResponsibility = {
  case_id: string;
  incoterm: string;
  incoterm_basis: string;
  named_destination_port: string;
  supported: boolean;
  risk_transfer_point: string;
  seller_responsibilities: string[];
  buyer_responsibilities: string[];
  cost_responsibility: Record<string, string>;
  warnings: Array<{ code: string; message: string }>;
};

export type PerspectiveAnalysis = {
  case_id: string;
  trade_perspective: TradePerspective;
  cif_responsibility: CifResponsibility;
  risk_summary: RiskSummary;
  obligations: ObligationDeadline[];
  information_gaps: InformationGap[];
  actions: RecommendedAction[];
  treatment_plans: TreatmentPlan[];
  relevance_results: RelevanceResult[];
};

export type FieldConflict = {
  conflict_id: string;
  case_id: string;
  field_name: string;
  severity: string;
  status: string;
  values: Array<{ value: string | number | boolean | null; source_document_name: string; field_id: string }>;
  explanation: string;
  recommended_resolution: string;
};

export type FieldEvidence = {
  field_name: string;
  display_name: string;
  value: string | number | boolean | null;
  source_document_id: string;
  source_document_name: string;
  page_number: number | null;
  evidence_text: string;
  confidence: number;
  review_status: string;
};

export type WorkflowState = {
  case_id: string;
  current_step: string;
  steps: Array<{ name: string; status: string }>;
};

export type AgentRunRecord = {
  agent_run_id: string;
  case_id: string;
  started_at: string;
  completed_at: string;
  status_before: string;
  status_after: string;
  events_scanned: number;
  relevant_count: number;
  watch_count: number;
  irrelevant_count: number;
  summary: string;
  run_status: string;
  obligations_at_risk_count?: number;
  information_gaps_count?: number;
  drafts_generated_count?: number;
  actions_generated_count?: number;
  triggered_exposures?: string[];
};

export type AgentRunResponse = {
  agent_run_id: string;
  case_id: string;
  status_before: string;
  status_after: string;
  summary: string;
  summary_source: "llm" | "deterministic" | "deterministic_fallback";
  llm_enabled: boolean;
  llm_required: boolean;
  trace: AgentRunTraceStep[];
  events_scanned: number;
  relevant_count: number;
  watch_count: number;
  irrelevant_count: number;
  case: TradeCase;
  watch_profile: WatchProfile;
  relevance_results: RelevanceResult[];
  risk_summary: RiskSummary;
  obligations: ObligationDeadline[];
  information_gaps: InformationGap[];
  action_drafts: ActionDraft[];
  actions: RecommendedAction[];
  status_timeline: StatusTimelineEntry[];
  unresolved_high_conflicts?: FieldConflict[];
  treatment_plans?: TreatmentPlan[];
  recommended_treatment_plan_id?: string;
  approval_package?: ApprovalPackage | null;
};

export type MonitorResponse = {
  case: TradeCase;
  relevance_results: RelevanceResult[];
  risk_summary: RiskSummary;
  actions: RecommendedAction[];
  status_timeline: StatusTimelineEntry[];
};

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options?.headers ?? {})
    },
    ...options
  });

  if (!response.ok) {
    let message = `API request failed: ${response.status}`;
    try {
      const body = await response.json();
      if (typeof body?.detail === "string" && body.detail.trim()) {
        message = body.detail;
      } else if (typeof body?.message === "string" && body.message.trim()) {
        message = body.message;
      }
    } catch {
      // Keep the status-only fallback if the response is not JSON.
    }
    throw new Error(message);
  }

  return response.json() as Promise<T>;
}

export const api = {
  listCases: () => request<{ cases: CaseSummary[] }>("/api/cases"),
  createCase: (payload: CreateCasePayload) =>
    request<TradeCase>("/api/cases", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  updateCaseDetails: (caseId: string, payload: CreateCasePayload) =>
    request<TradeCase>(`/api/cases/${caseId}/details`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  createDemoCase: () => request<TradeCase>("/api/cases/demo", { method: "POST" }),
  createCleanDemoCase: () => request<TradeCase>("/api/cases/demo/clean", { method: "POST" }),
  createConflictDemoCase: () => request<TradeCase>("/api/cases/demo/conflict", { method: "POST" }),
  getCase: (caseId: string) => request<TradeCase>(`/api/cases/${caseId}`),
  uploadCase: (fileNames: string[]) =>
    request<TradeCase>("/api/cases/upload", {
      method: "POST",
      body: JSON.stringify({ file_names: fileNames })
    }),
  getWatchProfile: (caseId: string) => request<WatchProfile>(`/api/cases/${caseId}/watch-profile`),
  getRelevanceResults: (caseId: string) => request<RelevanceResult[]>(`/api/cases/${caseId}/relevance-results`),
  getEventConfig: () => request<EventConfig>("/api/events/config"),
  getRealEventConfig: () => request<RealEventConfig>("/api/events/real-config"),
  getExternalEvents: (caseId: string) => request<ExternalEvent[]>(`/api/cases/${caseId}/external-events`),
  getAgentRunExternalEvents: (caseId: string, agentRunId: string) =>
    request<ExternalEvent[]>(`/api/cases/${caseId}/agent-runs/${agentRunId}/external-events`),
  fetchExternalEvents: (caseId: string) =>
    request<EventIngestionResult>(`/api/cases/${caseId}/external-events/fetch`, { method: "POST" }),
  getExternalEventQueries: (caseId: string) =>
    request<{ case_id: string; queries: ExternalEventQuery[] }>(`/api/cases/${caseId}/external-event-queries`),
  searchExternalEvents: (caseId: string) =>
    request<ExternalEventSearchResult>(`/api/cases/${caseId}/external-events/search`, { method: "POST" }),
  getRiskSummary: (caseId: string) => request<RiskSummary>(`/api/cases/${caseId}/risk-summary`),
  getActions: (caseId: string) => request<RecommendedAction[]>(`/api/cases/${caseId}/actions`),
  getCifResponsibility: (caseId: string) => request<CifResponsibility>(`/api/cases/${caseId}/cif-responsibility`),
  getPerspectiveAnalysis: (caseId: string, perspective: TradePerspective) =>
    request<PerspectiveAnalysis>(`/api/cases/${caseId}/perspective-analysis?perspective=${perspective}`),
  updatePerspective: (caseId: string, perspective: TradePerspective) =>
    request<TradeCase>(`/api/cases/${caseId}/perspective`, {
      method: "PUT",
      body: JSON.stringify({ trade_perspective: perspective })
    }),
  uploadDocument: async (caseId: string, file: File, documentType: string) => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("document_type", documentType);
    const response = await fetch(`${API_BASE}/api/cases/${caseId}/documents/upload`, {
      method: "POST",
      body: formData
    });
    if (!response.ok) {
      throw new Error(`Document upload failed: ${response.status}`);
    }
    return response.json() as Promise<DocumentRecord>;
  },
  getDocuments: (caseId: string) => request<DocumentRecord[]>(`/api/cases/${caseId}/documents`),
  extractDocuments: (caseId: string) =>
    request<{ documents: DocumentRecord[]; extracted_fields: ExtractedField[]; parse_errors: unknown[]; document_diagnostics?: DocumentExtractionDiagnostic[]; status?: string }>(
      `/api/cases/${caseId}/documents/extract`,
      { method: "POST" }
    ),
  autofillFromDocuments: (caseId: string) =>
    request<CaseAutofillResult>(`/api/cases/${caseId}/autofill-from-documents`, { method: "POST" }),
  getCaseAutofill: (caseId: string) => request<CaseAutofillResult>(`/api/cases/${caseId}/autofill`),
  getExtractedFields: (caseId: string) => request<ExtractedField[]>(`/api/cases/${caseId}/extracted-fields`),
  getFieldEvidence: (caseId: string, fieldId: string) =>
    request<FieldEvidence>(`/api/cases/${caseId}/extracted-fields/${fieldId}/evidence`),
  approveField: (caseId: string, fieldId: string) =>
    request<ExtractedField>(`/api/cases/${caseId}/extracted-fields/${fieldId}/approve`, { method: "POST" }),
  editField: (caseId: string, fieldId: string, value: string) =>
    request<ExtractedField>(`/api/cases/${caseId}/extracted-fields/${fieldId}/edit`, {
      method: "POST",
      body: JSON.stringify({ value })
    }),
  rejectField: (caseId: string, fieldId: string) =>
    request<ExtractedField>(`/api/cases/${caseId}/extracted-fields/${fieldId}/reject`, { method: "POST" }),
  confirmFields: (caseId: string) =>
    request<ConfirmedFacts>(`/api/cases/${caseId}/confirm-fields`, { method: "POST" }),
  getConfirmedFacts: (caseId: string) => request<ConfirmedFacts>(`/api/cases/${caseId}/confirmed-facts`),
  getObligations: (caseId: string) => request<ObligationDeadline[]>(`/api/cases/${caseId}/obligations`),
  getInformationGaps: (caseId: string) => request<InformationGap[]>(`/api/cases/${caseId}/information-gaps`),
  getActionDrafts: (caseId: string) => request<ActionDraft[]>(`/api/cases/${caseId}/action-drafts`),
  getFieldConflicts: (caseId: string) => request<FieldConflict[]>(`/api/cases/${caseId}/field-conflicts`),
  resolveFieldConflict: (caseId: string, conflictId: string, resolvedValue: string, resolutionNote = "Resolved in MVP demo") =>
    request<FieldConflict>(`/api/cases/${caseId}/field-conflicts/${conflictId}/resolve`, {
      method: "POST",
      body: JSON.stringify({ resolved_value: resolvedValue, resolution_note: resolutionNote, resolved_by: "user" })
    }),
  getWorkflowState: (caseId: string) => request<WorkflowState>(`/api/cases/${caseId}/workflow-state`),
  getAgentRuns: (caseId: string) => request<AgentRunRecord[]>(`/api/cases/${caseId}/agent-runs`),
  getAgentRun: (caseId: string, agentRunId: string) =>
    request<AgentRunRecord>(`/api/cases/${caseId}/agent-runs/${agentRunId}`),
  getAgentRunTrace: (caseId: string, agentRunId: string) =>
    request<AgentRunTraceStep[]>(`/api/cases/${caseId}/agent-runs/${agentRunId}/trace`),
  markDraftInReview: (caseId: string, draftId: string) =>
    request<ActionDraft>(`/api/cases/${caseId}/action-drafts/${draftId}/mark-in-review`, { method: "POST" }),
  markDraftReady: (caseId: string, draftId: string) =>
    request<ActionDraft>(`/api/cases/${caseId}/action-drafts/${draftId}/mark-ready`, { method: "POST" }),
  rejectDraft: (caseId: string, draftId: string, reason: string) =>
    request<ActionDraft>(`/api/cases/${caseId}/action-drafts/${draftId}/reject`, {
      method: "POST",
      body: JSON.stringify({ reason })
    }),
  archiveDraft: (caseId: string, draftId: string) =>
    request<ActionDraft>(`/api/cases/${caseId}/action-drafts/${draftId}/archive`, { method: "POST" }),
  regenerateDraft: (caseId: string, draftId: string) =>
    request<ActionDraft>(`/api/cases/${caseId}/action-drafts/${draftId}/regenerate`, { method: "POST" }),
  runAgentMonitoringCycle: (caseId: string) =>
    request<AgentRunResponse>(`/api/cases/${caseId}/agent-run`, { method: "POST" }),
  generateTreatmentPlans: (caseId: string) =>
    request<{ case_id: string; recommended_plan_id: string; plans: TreatmentPlan[]; conflict_safe_mode?: boolean; allowed_plan_types?: string[] }>(
      `/api/cases/${caseId}/treatment-plans/generate`,
      { method: "POST" }
    ),
  listTreatmentPlans: (caseId: string) => request<TreatmentPlan[]>(`/api/cases/${caseId}/treatment-plans`),
  getTreatmentPlan: (caseId: string, planId: string) =>
    request<TreatmentPlan>(`/api/cases/${caseId}/treatment-plans/${planId}`),
  selectTreatmentPlan: (caseId: string, planId: string) =>
    request<TreatmentPlan>(`/api/cases/${caseId}/treatment-plans/${planId}/select`, { method: "POST" }),
  archiveTreatmentPlan: (caseId: string, planId: string) =>
    request<TreatmentPlan>(`/api/cases/${caseId}/treatment-plans/${planId}/archive`, { method: "POST" }),
  generateApprovalPackage: (caseId: string, planId: string) =>
    request<ApprovalPackage>(`/api/cases/${caseId}/treatment-plans/${planId}/approval-package`, { method: "POST" }),
  listApprovalPackages: (caseId: string) => request<ApprovalPackage[]>(`/api/cases/${caseId}/approval-packages`),
  updateApprovalPackageStatus: (caseId: string, approvalPackageId: string, status: string, decisionNote: string) =>
    request<ApprovalPackage>(`/api/cases/${caseId}/approval-packages/${approvalPackageId}/status`, {
      method: "POST",
      body: JSON.stringify({ status, decision_note: decisionNote })
    }),
  monitorCase: (caseId: string) => request<MonitorResponse>(`/api/cases/${caseId}/monitor`, { method: "POST" }),
  continueMonitoring: (caseId: string) =>
    request<{ case: TradeCase; status_timeline: StatusTimelineEntry[] }>(`/api/cases/${caseId}/continue-monitoring`, {
      method: "POST"
    }),
  getStatusTimeline: (caseId: string) => request<StatusTimelineEntry[]>(`/api/cases/${caseId}/status-timeline`)
};
