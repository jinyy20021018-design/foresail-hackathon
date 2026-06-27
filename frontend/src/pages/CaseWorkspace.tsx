import { useEffect, useMemo, useState } from "react";
import {
  api,
  type ActionDraft,
  type ApprovalPackage,
  type AgentRunRecord,
  type AgentRunResponse,
  type AgentRunTraceStep,
  type DocumentRecord,
  type EventConfig,
  type ExternalEvent,
  type ExtractedField,
  type FieldConflict,
  type InformationGap,
  type ObligationDeadline,
  type RecommendedAction,
  type RelevanceResult,
  type RiskSummary,
  type StatusTimelineEntry,
  type TreatmentPlan,
  type TradeCase,
  type WatchProfile,
  type WorkflowState
} from "../api/client";
import { ActionBoard } from "../components/ActionBoard";
import { AgentRunSummary } from "../components/AgentRunSummary";
import { AgentRunTrace } from "../components/AgentRunTrace";
import { AgentRunHistory } from "../components/AgentRunHistory";
import { CaseStatusBadge } from "../components/Badges";
import { CaseSnapshot } from "../components/CaseSnapshot";
import { DocumentUploadPanel } from "../components/DocumentUploadPanel";
import { EventResultsTable } from "../components/EventResultsTable";
import { ExternalEventsPanel } from "../components/ExternalEventsPanel";
import { ExtractedFieldsReview } from "../components/ExtractedFieldsReview";
import { FieldConflictPanel } from "../components/FieldConflictPanel";
import { OperationalPanels } from "../components/OperationalPanels";
import { RiskSummaryPanel } from "../components/RiskSummaryPanel";
import { RouteRiskMap } from "../components/RouteRiskMap";
import { StatusTimeline } from "../components/StatusTimeline";
import { TreatmentPlansPanel } from "../components/TreatmentPlansPanel";
import { WatchProfilePanel } from "../components/WatchProfilePanel";
import { WorkflowStepper } from "../components/WorkflowStepper";
import type { Language } from "../i18n";

type TabKey = "overview" | "documents" | "conflicts" | "agent" | "events" | "risks" | "actions" | "treatment" | "audit";

type Props = {
  caseId: string;
  language: Language;
  onCaseChange: (tradeCase: TradeCase) => void;
  onNavigate: (path: string) => void;
};

const tabs: Array<{ key: TabKey; label: string }> = [
  { key: "overview", label: "Overview" },
  { key: "documents", label: "Documents & Evidence" },
  { key: "conflicts", label: "Conflicts" },
  { key: "agent", label: "Agent Runs" },
  { key: "events", label: "External Events" },
  { key: "risks", label: "Risks & Obligations" },
  { key: "actions", label: "Actions & Drafts" },
  { key: "treatment", label: "Treatment Plans" },
  { key: "audit", label: "Audit" }
];

export function CaseWorkspace({ caseId, language, onCaseChange, onNavigate }: Props) {
  const [tradeCase, setTradeCase] = useState<TradeCase | null>(null);
  const [watchProfile, setWatchProfile] = useState<WatchProfile | null>(null);
  const [timeline, setTimeline] = useState<StatusTimelineEntry[]>([]);
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [fields, setFields] = useState<ExtractedField[]>([]);
  const [conflicts, setConflicts] = useState<FieldConflict[]>([]);
  const [workflow, setWorkflow] = useState<WorkflowState | null>(null);
  const [agentRuns, setAgentRuns] = useState<AgentRunRecord[]>([]);
  const [agentResult, setAgentResult] = useState<AgentRunResponse | null>(null);
  const [eventConfig, setEventConfig] = useState<EventConfig | null>(null);
  const [externalEvents, setExternalEvents] = useState<ExternalEvent[]>([]);
  const [relevanceResults, setRelevanceResults] = useState<RelevanceResult[]>([]);
  const [riskSummary, setRiskSummary] = useState<RiskSummary | null>(null);
  const [actions, setActions] = useState<RecommendedAction[]>([]);
  const [obligations, setObligations] = useState<ObligationDeadline[]>([]);
  const [gaps, setGaps] = useState<InformationGap[]>([]);
  const [drafts, setDrafts] = useState<ActionDraft[]>([]);
  const [treatmentPlans, setTreatmentPlans] = useState<TreatmentPlan[]>([]);
  const [approvalPackages, setApprovalPackages] = useState<ApprovalPackage[]>([]);
  const [hasConfirmedFacts, setHasConfirmedFacts] = useState(false);
  const [activeTab, setActiveTab] = useState<TabKey>(() => initialTabFromUrl());
  const [isLoading, setIsLoading] = useState(true);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const highOpenConflicts = useMemo(
    () => conflicts.filter((conflict) => conflict.severity === "High" && conflict.status === "OPEN"),
    [conflicts]
  );

  async function refreshCase() {
    setError(null);
    const current = await api.getCase(caseId);
    setTradeCase(current);
    onCaseChange(current);
    const [
      profile,
      statusTimeline,
      docs,
      extracted,
      fieldConflicts,
      workflowState,
      runs,
      config,
      storedEvents,
      relevance,
      risk,
      actionItems,
      obligationItems,
      gapItems,
      draftItems,
      planItems,
      approvalItems,
      confirmedFacts
    ] = await Promise.all([
      api.getWatchProfile(caseId).catch(() => null),
      api.getStatusTimeline(caseId).catch(() => []),
      api.getDocuments(caseId).catch(() => []),
      api.getExtractedFields(caseId).catch(() => []),
      api.getFieldConflicts(caseId).catch(() => []),
      api.getWorkflowState(caseId).catch(() => null),
      api.getAgentRuns(caseId).catch(() => []),
      api.getEventConfig().catch(() => null),
      api.getExternalEvents(caseId).catch(() => []),
      api.getRelevanceResults(caseId).catch(() => []),
      api.getRiskSummary(caseId).catch(() => null),
      api.getActions(caseId).catch(() => []),
      api.getObligations(caseId).catch(() => []),
      api.getInformationGaps(caseId).catch(() => []),
      api.getActionDrafts(caseId).catch(() => []),
      api.listTreatmentPlans(caseId).catch(() => []),
      api.listApprovalPackages(caseId).catch(() => []),
      api.getConfirmedFacts(caseId).then(() => true).catch(() => false)
    ]);
    setWatchProfile(profile);
    setTimeline(statusTimeline);
    setDocuments(docs);
    setFields(extracted);
    setConflicts(fieldConflicts);
    setWorkflow(workflowState);
    setAgentRuns(runs);
    setEventConfig(config);
    setExternalEvents(storedEvents);
    setRelevanceResults(relevance);
    setRiskSummary(risk);
    setActions(actionItems);
    setObligations(obligationItems);
    setGaps(gapItems);
    setDrafts(draftItems);
    setTreatmentPlans(planItems);
    setApprovalPackages(approvalItems);
    setHasConfirmedFacts(confirmedFacts);
    const latestRun = latestAgentRun(runs);
    if (latestRun) {
      const latestTrace = await api.getAgentRunTrace(caseId, latestRun.agent_run_id).catch(() => []);
      setAgentResult(
        hydrateAgentRunResult({
          run: latestRun,
          tradeCase: current,
          watchProfile: profile,
          relevanceResults: relevance,
          riskSummary: risk,
          obligations: obligationItems,
          gaps: gapItems,
          drafts: draftItems,
          actions: actionItems,
          statusTimeline,
          trace: latestTrace,
        })
      );
    } else {
      setAgentResult(null);
    }
  }

  useEffect(() => {
    setIsLoading(true);
    setTradeCase(null);
    setWatchProfile(null);
    setTimeline([]);
    setDocuments([]);
    setFields([]);
    setConflicts([]);
    setWorkflow(null);
    setAgentRuns([]);
    setAgentResult(null);
    setEventConfig(null);
    setExternalEvents([]);
    setRelevanceResults([]);
    setRiskSummary(null);
    setActions([]);
    setObligations([]);
    setGaps([]);
    setDrafts([]);
    setTreatmentPlans([]);
    setApprovalPackages([]);
    setHasConfirmedFacts(false);
    refreshCase()
      .catch((caught) => setError(caught instanceof Error ? caught.message : "Failed to load case workspace."))
      .finally(() => setIsLoading(false));
  }, [caseId]);

  async function confirmFields() {
    if (fields.length === 0 || highOpenConflicts.length > 0) return;
    setError(null);
    try {
      const facts = await api.confirmFields(caseId);
      const nextCase = { ...tradeCase, ...facts, status: "ACTIVE" } as TradeCase;
      setTradeCase(nextCase);
      onCaseChange(nextCase);
      setHasConfirmedFacts(true);
      await refreshCase();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Confirm fields failed.");
    }
  }

  async function runAgent() {
    if (!hasConfirmedFacts || highOpenConflicts.length > 0) return;
    setIsRunning(true);
    setError(null);
    try {
      const result = await api.runAgentMonitoringCycle(caseId);
      setAgentResult(result);
      setTradeCase(result.case);
      onCaseChange(result.case);
      setWatchProfile(result.watch_profile);
      setTimeline(result.status_timeline);
      setRelevanceResults(result.relevance_results);
      setRiskSummary(result.risk_summary);
      setActions(result.actions);
      setObligations(result.obligations);
      setGaps(result.information_gaps);
      setDrafts(result.action_drafts);
      setTreatmentPlans(await api.listTreatmentPlans(caseId));
      setApprovalPackages(await api.listApprovalPackages(caseId));
      setExternalEvents(await api.getExternalEvents(caseId));
      setAgentRuns(await api.getAgentRuns(caseId));
      setWorkflow(await api.getWorkflowState(caseId));
      setActiveTab("agent");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Agent run failed.");
    } finally {
      setIsRunning(false);
    }
  }

  async function continueMonitoring() {
    setError(null);
    try {
      const result = await api.continueMonitoring(caseId);
      setTradeCase(result.case);
      onCaseChange(result.case);
      setTimeline(result.status_timeline);
      await refreshCase();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Continue monitoring failed.");
    }
  }

  if (isLoading) {
    return <section className="page"><p className="empty-state">Loading case workspace...</p></section>;
  }

  if (!tradeCase) {
    return (
      <section className="page">
        <div className="error">Case not found: {caseId}</div>
        <button className="secondary-action" type="button" onClick={() => onNavigate("/cases")}>Back to Case Library</button>
      </section>
    );
  }

  const canRunAgent = hasConfirmedFacts && highOpenConflicts.length === 0 && tradeCase.status !== "MONITORING";
  const canContinue = tradeCase.status === "ACTION_REQUIRED";

  return (
    <section className="page workspace-page">
      <div className="breadcrumb">
        <button type="button" onClick={() => onNavigate("/cases")}>Case Library</button>
        <span>/</span>
        <strong>{tradeCase.case_id}</strong>
      </div>

      <div className="workspace-header">
        <div>
          <div className="title-row">
            <h1>{tradeCase.vessel} Trade Watch</h1>
          <CaseStatusBadge value={tradeCase.status} />
            <span className="tag">Event Mode: {eventConfig?.event_source_mode ?? "MOCK"}</span>
          </div>
          <p>Live trade-risk workspace for {tradeCase.route}</p>
          {highOpenConflicts.length > 0 && (
            <div className="warning-banner">High severity conflicts must be resolved before confirming case facts or running the agent.</div>
          )}
        </div>
        <div className="header-actions">
          <button className="secondary-action" type="button" onClick={runAgent} disabled={!canRunAgent || isRunning}>
            <span className="run-agent-icon" aria-hidden="true">↻</span>{isRunning ? "Agent Running..." : "Run Agent Monitoring Cycle"}
          </button>
          <button className="primary-action" type="button" onClick={continueMonitoring} disabled={!canContinue}>
            {tradeCase.status === "MONITORING" ? "Monitoring Active" : "Continue Monitoring"}
          </button>
        </div>
      </div>

      <div className="case-facts-bar">
        <Fact label="Vessel" value={tradeCase.vessel} />
        <Fact label="Route" value={tradeCase.route} />
        <Fact label="Incoterm" value={tradeCase.incoterm || "Not set"} />
        <Fact label="Payment" value={tradeCase.payment_method || "Not set"} />
        <Fact label="Latest shipment" value={tradeCase.latest_shipment_date || "Not set"} />
      </div>

      {error && <div className="error">{error}</div>}
      <WorkflowStepper workflow={workflow} />

      <div className="tabs">
        {tabs.map((tab) => (
          <button key={tab.key} className={activeTab === tab.key ? "active" : ""} type="button" onClick={() => setActiveTab(tab.key)}>
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === "overview" && (
        <>
          <div className="workspace-metrics">
            <WorkspaceMetric icon="shield" tone="red" label="Risk Level" value={tradeCase.status} detail={`${riskSummary?.exposures.length ?? 0} exposures detected`} onClick={() => setActiveTab("risks")} />
            <WorkspaceMetric icon="check" tone="blue" label="Open Actions" value={String(actions.length)} detail="Recommended next steps" onClick={() => setActiveTab("actions")} />
            <WorkspaceMetric icon="info" tone="amber" label="Info Gaps" value={String(gaps.length)} detail="Missing decision inputs" onClick={() => setActiveTab("risks")} />
            <WorkspaceMetric icon="agent" tone="green" label="Agent Runs" value={String(agentRuns.length)} detail="Visible audit trail" onClick={() => setActiveTab("agent")} />
          </div>
          <div className="workspace-grid">
            <CaseSnapshot tradeCase={tradeCase} language={language} />
            {watchProfile && <WatchProfilePanel profile={watchProfile} language={language} />}
          </div>
          <RouteRiskMap tradeCase={tradeCase} />
          <div className="workspace-grid">
            <LatestAgentRunCard runs={agentRuns} result={agentResult} />
            <StatusTimeline entries={timeline} language={language} />
          </div>
        </>
      )}

      {activeTab === "documents" && (
        <>
          <DocumentUploadPanel
            caseId={caseId}
            documents={documents}
            onDocumentsChange={async (nextDocuments) => {
              setDocuments(nextDocuments);
              setWorkflow(await api.getWorkflowState(caseId));
            }}
            onError={setError}
            language={language}
          />
          <ExtractedFieldsReview
            caseId={caseId}
            fields={fields}
            canExtract={documents.length > 0}
            onFieldsChange={async (nextFields) => {
              setFields(nextFields);
              setConflicts(await api.getFieldConflicts(caseId));
              setWorkflow(await api.getWorkflowState(caseId));
            }}
            onDocumentsChange={setDocuments}
            onError={setError}
            language={language}
          />
          <button className="primary-action section-action" type="button" onClick={confirmFields} disabled={fields.length === 0 || highOpenConflicts.length > 0}>
            Confirm Fields
          </button>
        </>
      )}

      {activeTab === "conflicts" && (
        <>
          {highOpenConflicts.length > 0 && <div className="warning-banner">Resolve all High OPEN conflicts before confirming case facts.</div>}
          <FieldConflictPanel
            caseId={caseId}
            conflicts={conflicts}
            onConflictsChange={async (nextConflicts) => {
              setConflicts(nextConflicts);
              setWorkflow(await api.getWorkflowState(caseId));
            }}
          />
        </>
      )}

      {activeTab === "agent" && (
        <>
          <AgentRunSummary result={agentResult} language={language} />
          <AgentRunHistory caseId={caseId} runs={agentRuns} />
          <AgentRunTrace trace={agentResult?.trace ?? []} language={language} />
        </>
      )}

      {activeTab === "events" && (
        <ExternalEventsPanel
          caseId={caseId}
          config={eventConfig}
          events={externalEvents}
          hasConfirmedFacts={hasConfirmedFacts}
          highOpenConflictsCount={highOpenConflicts.length}
          onEventsChange={setExternalEvents}
          onError={setError}
        />
      )}

      {activeTab === "risks" && (
        <>
          <EventResultsTable results={relevanceResults} language={language} />
          <RiskSummaryPanel summary={riskSummary} language={language} />
          <OperationalPanels obligations={obligations} gaps={gaps} drafts={[]} caseId={caseId} onDraftsChange={() => undefined} showDrafts={false} />
        </>
      )}

      {activeTab === "actions" && (
        <>
          <ActionBoard actions={actions} language={language} />
          <OperationalPanels obligations={[]} gaps={[]} drafts={drafts} caseId={caseId} onDraftsChange={setDrafts} showObligations={false} showGaps={false} />
        </>
      )}

      {activeTab === "treatment" && (
        <TreatmentPlansPanel
          caseId={caseId}
          hasConfirmedFacts={hasConfirmedFacts}
          hasAgentRuns={agentRuns.length > 0}
          highOpenConflictsCount={highOpenConflicts.length}
          relevanceResults={relevanceResults}
          riskSummary={riskSummary}
          obligations={obligations}
          gaps={gaps}
          actions={actions}
          drafts={drafts}
          plans={treatmentPlans}
          approvalPackages={approvalPackages}
          onPlansChange={setTreatmentPlans}
          onApprovalPackagesChange={setApprovalPackages}
          onError={setError}
        />
      )}

      {activeTab === "audit" && (
        <div className="workspace-grid two">
          <StatusTimeline entries={timeline} language={language} />
          <AgentRunHistory caseId={caseId} runs={agentRuns} />
        </div>
      )}
    </section>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return <div><span>{label}</span><strong>{value}</strong></div>;
}

function WorkspaceMetric({ icon, tone, label, value, detail, onClick }: { icon: "shield" | "check" | "info" | "agent"; tone: string; label: string; value: string; detail: string; onClick: () => void }) {
  return <button className="workspace-metric" type="button" onClick={onClick}><span className={`metric-icon ${tone}`}><MetricGlyph name={icon} /></span><span><b>{label}</b><strong>{value}</strong><small>{detail}</small></span><em>View details →</em></button>;
}

function MetricGlyph({ name }: { name: "shield" | "check" | "info" | "agent" }) {
  if (name === "shield") return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3 19 6v5c0 4.7-2.8 8-7 10-4.2-2-7-5.3-7-10V6l7-3Z"/><path d="M12 7v10"/></svg>;
  if (name === "check") return <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="4" y="4" width="16" height="16" rx="4"/><path d="m8.5 12 2.3 2.4 4.8-5"/></svg>;
  if (name === "info") return <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8"/><path d="M12 11v5M12 8h.01"/></svg>;
  return <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="8" r="3"/><path d="M6.5 19c.6-3.3 2.4-5 5.5-5s4.9 1.7 5.5 5M17.5 11.5h3M19 10v3"/></svg>;
}

function LatestAgentRunCard({ runs, result }: { runs: AgentRunRecord[]; result: AgentRunResponse | null }) {
  const latest = latestAgentRun(runs);
  return (
    <section className="panel agent-summary-card">
      <div className="panel-heading">
        <h2>Agent Summary</h2>
        {latest && <span className="tag">{latest.run_status}</span>}
      </div>
      {!latest && !result ? (
        <p className="empty-state">No agent run yet.</p>
      ) : (
        <>
          <div className="mini-metrics">
            <div><strong>{result?.events_scanned ?? latest?.events_scanned ?? 0}</strong><span>Events Scanned</span></div>
            <div><strong>{result?.relevant_count ?? latest?.relevant_count ?? 0}</strong><span>Relevant</span></div>
            <div><strong>{result?.watch_count ?? latest?.watch_count ?? 0}</strong><span>Watch</span></div>
            <div><strong>{result?.irrelevant_count ?? latest?.irrelevant_count ?? 0}</strong><span>Irrelevant</span></div>
          </div>
          <p className="agent-summary-text">{result?.summary ?? latest?.summary}</p>
        </>
      )}
    </section>
  );
}

function latestAgentRun(runs: AgentRunRecord[]) {
  const sortedRuns = [...runs].sort((left, right) => {
    const leftTime = Date.parse(left.completed_at || left.started_at || "");
    const rightTime = Date.parse(right.completed_at || right.started_at || "");
    return leftTime - rightTime;
  });
  return sortedRuns[sortedRuns.length - 1];
}

function initialTabFromUrl(): TabKey {
  const requested = new URLSearchParams(window.location.search).get("tab");
  const allowed: TabKey[] = ["overview", "documents", "conflicts", "agent", "events", "risks", "actions", "treatment", "audit"];
  return allowed.includes(requested as TabKey) ? requested as TabKey : "overview";
}

function hydrateAgentRunResult({
  run,
  tradeCase,
  watchProfile,
  relevanceResults,
  riskSummary,
  obligations,
  gaps,
  drafts,
  actions,
  statusTimeline,
  trace,
}: {
  run: AgentRunRecord;
  tradeCase: TradeCase;
  watchProfile: WatchProfile | null;
  relevanceResults: RelevanceResult[];
  riskSummary: RiskSummary | null;
  obligations: ObligationDeadline[];
  gaps: InformationGap[];
  drafts: ActionDraft[];
  actions: RecommendedAction[];
  statusTimeline: StatusTimelineEntry[];
  trace: AgentRunTraceStep[];
}): AgentRunResponse {
  return {
    agent_run_id: run.agent_run_id,
    case_id: run.case_id,
    status_before: run.status_before,
    status_after: run.status_after,
    summary: run.summary || "Latest agent run restored from history.",
    summary_source: "deterministic",
    llm_enabled: false,
    llm_required: false,
    trace: trace.map((step) => ({
      step: step.step ?? step.step_number ?? 0,
      name: step.name ?? step.step_name ?? "Agent Step",
      trace_id: step.trace_id,
      step_name: step.step_name,
      status: step.status,
      description: step.description,
      tool_or_service: step.tool_or_service,
      output_summary: step.output_summary,
    })),
    events_scanned: run.events_scanned,
    relevant_count: run.relevant_count,
    watch_count: run.watch_count,
    irrelevant_count: run.irrelevant_count,
    case: tradeCase,
    watch_profile: watchProfile ?? {
      case_id: tradeCase.case_id,
      watched_vessel: tradeCase.vessel,
      watched_ports: [tradeCase.port_of_loading, tradeCase.port_of_discharge, tradeCase.final_destination].filter(Boolean),
      watched_route_regions: [],
      shipment_window: {},
      deadline_sensitivity: [],
      risk_categories: [],
      alert_rules: [],
    },
    relevance_results: relevanceResults,
    risk_summary: riskSummary ?? { triggered: false, trigger_events: [], watch_events_considered: [], exposures: [] },
    obligations,
    information_gaps: gaps,
    action_drafts: drafts,
    actions,
    status_timeline: statusTimeline,
    unresolved_high_conflicts: [],
  };
}
