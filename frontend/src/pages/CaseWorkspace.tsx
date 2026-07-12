import { useEffect, useMemo, useState } from "react";
import {
  api,
  type ActionDraft,
  type ActionSet,
  type ApprovalPackage,
  type AgentRunRecord,
  type AgentRunResponse,
  type AgentRunTraceStep,
  type CifResponsibility,
  type DocumentRecord,
  type EventConfig,
  type ExternalEvent,
  type ExtractedField,
  type FieldConflict,
  type InformationGap,
  type ObligationDeadline,
  type PlanSet,
  type RecommendedAction,
  type RelevanceResult,
  type RiskSummary,
  type StatusTimelineEntry,
  type TreatmentPlan,
  type TradePerspective,
  type TradeCase,
  type WatchProfile,
  type WorkflowState
} from "../api/client";
import { ActionBoard } from "../components/ActionBoard";
import { AgentRunSummary } from "../components/AgentRunSummary";
import { AgentRunTrace } from "../components/AgentRunTrace";
import { AgentRunHistory } from "../components/AgentRunHistory";
import { CaseStatusBadge } from "../components/Badges";
import { DocumentUploadPanel } from "../components/DocumentUploadPanel";
import { EventResultsTable } from "../components/EventResultsTable";
import { ExternalEventsPanel } from "../components/ExternalEventsPanel";
import { ExtractedFieldsReview } from "../components/ExtractedFieldsReview";
import { FieldConflictPanel } from "../components/FieldConflictPanel";
import { OperationalPanels } from "../components/OperationalPanels";
import { RiskSummaryPanel } from "../components/RiskSummaryPanel";
import { StatusTimeline } from "../components/StatusTimeline";
import { WorkspaceOverview } from "../components/WorkspaceOverview";
import { TreatmentPlansPanel } from "../components/TreatmentPlansPanel";
import { WorkflowStepper } from "../components/WorkflowStepper";
import type { Language } from "../i18n";
import "../styles/fs2-overview.css";

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
  { key: "actions", label: "Actions" },
  { key: "treatment", label: "Treatment Plans" },
  { key: "audit", label: "Audit" }
];

const confirmRequiredFields = [
  "vessel",
  "port_of_loading",
  "port_of_discharge",
  "etd",
  "eta",
  "latest_shipment_date",
  "payment_method",
  "incoterm",
  "amount",
  "currency",
];

const fieldLabels: Record<string, string> = {
  vessel: "Vessel",
  port_of_loading: "Port of Loading",
  port_of_discharge: "Port of Discharge",
  etd: "ETD",
  eta: "ETA",
  latest_shipment_date: "Latest Shipment Date",
  payment_method: "Payment Method",
  incoterm: "Incoterm",
  amount: "Amount",
  currency: "Currency",
};

function workspaceAmount(tc: TradeCase): string | null {
  const amt = (tc as unknown as { amount?: number }).amount;
  const cur = (tc as unknown as { currency?: string }).currency;
  if (amt == null) return null;
  return `${cur ? cur + " " : ""}${Number(amt).toLocaleString()}`;
}

const agentProgressSteps = [
  {
    title: "Load confirmed case facts",
    detail: "Reading vessel, route, ports, shipment window, LC deadline, and Incoterm."
  },
  {
    title: "Build watch profile",
    detail: "Preparing watched vessel, ports, route regions, and deadline sensitivity."
  },
  {
    title: "Fetch real external events",
    detail: "Calling GDELT and Open-Meteo with the narrowed real-search query window."
  },
  {
    title: "Normalize and deduplicate events",
    detail: "Converting connector output to normalized events and removing duplicates."
  },
  {
    title: "Classify relevance",
    detail: "Scoring events against this case with deterministic relevance rules."
  },
  {
    title: "Prepare action context",
    detail: "Mapping exposures to obligations, information gaps, hazards, and Incoterm responsibilities."
  }
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
  const [actionSets, setActionSets] = useState<ActionSet[]>([]);
  const [obligations, setObligations] = useState<ObligationDeadline[]>([]);
  const [gaps, setGaps] = useState<InformationGap[]>([]);
  const [treatmentPlans, setTreatmentPlans] = useState<TreatmentPlan[]>([]);
  const [planSets, setPlanSets] = useState<PlanSet[]>([]);
  const [autoPlanActionSetId, setAutoPlanActionSetId] = useState<string | null>(null);
  const [approvalPackages, setApprovalPackages] = useState<ApprovalPackage[]>([]);
  const [cifResponsibility, setCifResponsibility] = useState<CifResponsibility | null>(null);
  const [hasConfirmedFacts, setHasConfirmedFacts] = useState(false);
  const [activeTab, setActiveTab] = useState<TabKey>(() => initialTabFromUrl());
  const [isLoading, setIsLoading] = useState(true);
  const [isRunning, setIsRunning] = useState(false);
  const [agentElapsedSeconds, setAgentElapsedSeconds] = useState(0);
  const [agentProgressStep, setAgentProgressStep] = useState(0);
  const [agentRunComplete, setAgentRunComplete] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const highOpenConflicts = useMemo(
    () => conflicts.filter((conflict) => conflict.severity === "High" && conflict.status === "OPEN"),
    [conflicts]
  );
  const missingConfirmFields = useMemo(() => {
    const confirmedFieldNames = new Set(
      fields
        .filter((field) => field.review_status === "APPROVED" || field.review_status === "EDITED")
        .filter((field) => {
          const value = field.review_status === "EDITED" ? field.edited_value : field.value;
          return value !== null && value !== "";
        })
        .map((field) => field.field_name)
    );
    return confirmRequiredFields.filter((field) => !confirmedFieldNames.has(field));
  }, [fields]);

  async function refreshCase() {
    setError(null);
    const current = await api.getCase(caseId);
    setTradeCase(current);
    onCaseChange(current);
    const perspective = current.trade_perspective ?? "SELLER";
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
      actionSetItems,
      planItems,
      planSetItems,
      approvalItems,
      confirmedFacts,
      perspectiveResult
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
      api.listActionSets(caseId).catch(() => []),
      api.listTreatmentPlans(caseId).catch(() => []),
      api.listPlanSets(caseId).catch(() => []),
      api.listApprovalPackages(caseId).catch(() => []),
      api.getConfirmedFacts(caseId).then(() => true).catch(() => false),
      api.getPerspectiveAnalysis(caseId, perspective).catch(() => null)
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
    setRelevanceResults(perspectiveResult?.relevance_results ?? relevance);
    setRiskSummary(perspectiveResult?.risk_summary ?? risk);
    setActionSets(actionSetItems);
    setActions(actionSetItems[actionSetItems.length - 1]?.actions ?? perspectiveResult?.actions ?? actionItems);
    setObligations(perspectiveResult?.obligations ?? obligationItems);
    setGaps(perspectiveResult?.information_gaps ?? gapItems);
    setTreatmentPlans(perspectiveResult?.treatment_plans ?? planItems);
    setPlanSets(planSetItems);
    setApprovalPackages(approvalItems);
    setCifResponsibility(perspectiveResult?.cif_responsibility ?? null);
    const confirmStepComplete = workflowState?.steps.some(
      (step) => step.name === "Confirm Case Facts" && step.status === "COMPLETED"
    ) ?? false;
    setHasConfirmedFacts(Boolean(confirmedFacts) || confirmStepComplete);
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
          drafts: [],
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
    setActionSets([]);
    setObligations([]);
    setGaps([]);
    setTreatmentPlans([]);
    setPlanSets([]);
    setAutoPlanActionSetId(null);
    setApprovalPackages([]);
    setCifResponsibility(null);
    setHasConfirmedFacts(false);
    refreshCase()
      .catch((caught) => setError(caught instanceof Error ? caught.message : "Failed to load case workspace."))
      .finally(() => setIsLoading(false));
  }, [caseId]);

  useEffect(() => {
    if (!isRunning) {
      if (!agentRunComplete) {
        setAgentElapsedSeconds(0);
        setAgentProgressStep(0);
      }
      return;
    }
    const startedAt = Date.now();
    const timer = window.setInterval(() => {
      setAgentElapsedSeconds(Math.floor((Date.now() - startedAt) / 1000));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [isRunning, agentRunComplete]);

  async function confirmFields() {
    if (fields.length === 0 || highOpenConflicts.length > 0 || missingConfirmFields.length > 0) return;
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
    const blockedReason = !hasConfirmedFacts
      ? "Confirm case facts in Documents & Evidence before running the agent."
      : highOpenConflicts.length > 0
        ? "Resolve high-severity field conflicts before running the agent."
        : tradeCase?.status === "MONITORING"
          ? "This case is already in monitoring mode."
          : null;
    if (blockedReason) {
      setError(blockedReason);
      return;
    }
    setAgentRunComplete(false);
    setIsRunning(true);
    setAgentElapsedSeconds(0);
    setAgentProgressStep(0);
    setActiveTab("agent");
    setError(null);
    try {
      const result = await api.runAgentMonitoringCycle(caseId);
      const perspective = result.case.trade_perspective ?? "SELLER";
      const analysis = await api.getPerspectiveAnalysis(caseId, perspective).catch(() => null);
      setAgentResult(result);
      setTradeCase(result.case);
      onCaseChange(result.case);
      setWatchProfile(result.watch_profile);
      setTimeline(result.status_timeline);
      setRelevanceResults(analysis?.relevance_results ?? result.relevance_results);
      setRiskSummary(analysis?.risk_summary ?? result.risk_summary);
      setActions([]);
      setObligations(analysis?.obligations ?? result.obligations);
      setGaps(analysis?.information_gaps ?? result.information_gaps);
      setTreatmentPlans(await api.listTreatmentPlans(caseId));
      setCifResponsibility(analysis?.cif_responsibility ?? null);
      setApprovalPackages(await api.listApprovalPackages(caseId));
      setExternalEvents(await api.getExternalEvents(caseId));
      setAgentRuns(await api.getAgentRuns(caseId));
      setWorkflow(await api.getWorkflowState(caseId));
      setActiveTab("actions");
      setAgentProgressStep(agentProgressSteps.length);
      setAgentRunComplete(true);
      const generatedActionSet = await api.generateActionSet(caseId);
      const nextActionSets = await api.listActionSets(caseId);
      setActionSets(nextActionSets);
      setActions(generatedActionSet.actions);
      setWorkflow(await api.getWorkflowState(caseId));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Agent run failed.");
      await refreshCase();
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

  function handleActionSetsChange(sets: ActionSet[]) {
    setActionSets(sets);
    setActions(sets[sets.length - 1]?.actions ?? []);
  }

  async function handleActionsConfirmed(actionSet: ActionSet) {
    const sets = await api.listActionSets(caseId);
    handleActionSetsChange(sets);
    setAutoPlanActionSetId(actionSet.action_set_id);
    setActiveTab("treatment");
    setWorkflow(await api.getWorkflowState(caseId));
  }

  async function changePerspective(nextPerspective: TradePerspective) {
    if (!tradeCase || tradeCase.trade_perspective === nextPerspective) return;
    setError(null);
    try {
      const updated = await api.updatePerspective(caseId, nextPerspective);
      const analysis = await api.getPerspectiveAnalysis(caseId, nextPerspective);
      setTradeCase(updated);
      onCaseChange(updated);
      setRelevanceResults(analysis.relevance_results);
      setRiskSummary(analysis.risk_summary);
      setObligations(analysis.obligations);
      setGaps(analysis.information_gaps);
      setCifResponsibility(analysis.cif_responsibility);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Perspective update failed.");
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

  const agentRunBlockedReason = !hasConfirmedFacts
    ? "Confirm case facts in Documents & Evidence first."
    : highOpenConflicts.length > 0
      ? "Resolve high-severity conflicts first."
      : tradeCase.status === "MONITORING"
        ? "Case is already in monitoring mode."
        : null;
  const canRunAgent = agentRunBlockedReason === null;
  const latestConfirmedActionSet = [...actionSets].reverse().find((item) => item.status === "CONFIRMED");
  const canContinue = tradeCase.status === "ACTION_REQUIRED" && Boolean(latestConfirmedActionSet && planSets.some((item) => item.action_set_id === latestConfirmedActionSet.action_set_id && item.status === "COMPLETED"));
  const selectedPerspective = tradeCase.trade_perspective ?? "SELLER";

  const overviewSubtitle = [
    tradeCase.route,
    tradeCase.incoterm ? tradeCase.incoterm.toUpperCase() : null,
    tradeCase.payment_method,
    workspaceAmount(tradeCase),
    `${selectedPerspective === "SELLER" ? "Seller" : "Buyer"} seat`,
  ].filter(Boolean).join(" · ");

  return (
    <section className="page workspace-page fs2-shell">
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
            <span className="tag">Event Mode: {eventConfig?.event_source_mode ?? "Loading"}</span>
          </div>
          <p>{overviewSubtitle}</p>
          {highOpenConflicts.length > 0 && (
            <div className="warning-banner">High severity conflicts must be resolved before confirming case facts or running the agent.</div>
          )}
        </div>
        <div className="header-actions">
          <div className="perspective-toggle" aria-label="Perspective">
            <span>Perspective</span>
            {(["BUYER", "SELLER"] as TradePerspective[]).map((perspective) => (
              <button
                key={perspective}
                className={selectedPerspective === perspective ? "active" : ""}
                type="button"
                onClick={() => changePerspective(perspective)}
              >
                {perspective === "BUYER" ? "Buyer" : "Seller"}
              </button>
            ))}
          </div>
          <button
            className="secondary-action"
            type="button"
            onClick={runAgent}
            disabled={!canRunAgent || isRunning}
            title={agentRunBlockedReason ?? undefined}
          >
            <span className="run-agent-icon" aria-hidden="true">↻</span>{isRunning ? "Agent Running..." : "Run Agent Monitoring Cycle"}
          </button>
          <button className="primary-action" type="button" onClick={continueMonitoring} disabled={!canContinue}>
            {tradeCase.status === "MONITORING" ? "Monitoring Active" : "Continue Monitoring"}
          </button>
        </div>
      </div>

      {activeTab !== "overview" && (
        <div className="case-facts-bar">
          <Fact label="Vessel" value={tradeCase.vessel} />
          <Fact label="Route" value={tradeCase.route} />
          <Fact label="Incoterm" value={tradeCase.incoterm || "Not set"} />
          <Fact label="Payment" value={tradeCase.payment_method || "Not set"} />
          <Fact label="Latest shipment" value={tradeCase.latest_shipment_date || "Not set"} />
        </div>
      )}

      {error && <div className="error">{error}</div>}
      {(isRunning || agentRunComplete) && (
        <AgentRunProgressPanel
          activeStep={agentProgressStep}
          elapsedSeconds={agentElapsedSeconds}
          eventConfig={eventConfig}
          completed={agentRunComplete}
          onDismiss={() => {
            setAgentRunComplete(false);
            setAgentProgressStep(0);
            setAgentElapsedSeconds(0);
          }}
        />
      )}
      {activeTab !== "overview" && <WorkflowStepper workflow={workflow} />}

      <div className="tabs fs2-tabs">
        {tabs.map((tab) => (
          <button key={tab.key} className={activeTab === tab.key ? "active" : ""} type="button" onClick={() => setActiveTab(tab.key)}>
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === "overview" && (
        <WorkspaceOverview
          caseId={caseId}
          tradeCase={tradeCase}
          actions={actions}
          riskSummary={riskSummary}
          refreshKey={`${agentRuns.length}:${relevanceResults.length}`}
          onOpenTab={(tab) => setActiveTab(tab as TabKey)}
        />
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
          {missingConfirmFields.length > 0 && (
            <div className="warning-banner">
              Confirm Case Facts requires: {missingConfirmFields.map((field) => fieldLabels[field] ?? field).join(", ")}. Upload the missing document(s) or edit extracted fields before confirming.
            </div>
          )}
          <button
            className="primary-action section-action"
            type="button"
            onClick={confirmFields}
            disabled={fields.length === 0 || highOpenConflicts.length > 0 || missingConfirmFields.length > 0}
            title={missingConfirmFields.length > 0 ? `Missing required fields: ${missingConfirmFields.map((field) => fieldLabels[field] ?? field).join(", ")}` : undefined}
          >
            Confirm Fields
          </button>
        </>
      )}

      {activeTab === "conflicts" && (
        <>
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
        <ActionBoard caseId={caseId} actionSets={actionSets} language={language} onActionSetsChange={handleActionSetsChange} onConfirmed={handleActionsConfirmed} onError={setError} />
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
          actionSets={actionSets}
          planSets={planSets}
          autoGenerateActionSetId={autoPlanActionSetId}
          plans={treatmentPlans}
          approvalPackages={approvalPackages}
          onPlansChange={setTreatmentPlans}
          onPlanSetsChange={setPlanSets}
          onAutoGenerateHandled={() => setAutoPlanActionSetId(null)}
          onApprovalPackagesChange={setApprovalPackages}
          onError={setError}
        />
      )}

      {activeTab === "audit" && (
        <div className="workspace-grid two audit-grid">
          <StatusTimeline entries={timeline} language={language} />
          <AgentRunHistory caseId={caseId} runs={agentRuns} />
        </div>
      )}
    </section>
  );
}

function CifResponsibilityCard({ responsibility, tradeCase }: { responsibility: CifResponsibility | null; tradeCase: TradeCase }) {
  const incoterm = (responsibility?.incoterm || tradeCase.incoterm || "").toUpperCase();
  const namedPlace = responsibility?.named_destination_port || tradeCase.incoterm_named_place || "";
  const warnings = responsibility?.warnings ?? [];
  const missingIncoterm = !incoterm;
  const unsupported = Boolean(incoterm && incoterm !== "CIF");
  const missingNamedPlace = warnings.some((warning) => warning.code === "CIF_NAMED_DESTINATION_PORT_MISSING");

  return (
    <section className="panel cif-card">
      <div className="panel-heading">
        <h2>CIF Responsibility</h2>
        <span className="tag">{incoterm || "Missing"}</span>
      </div>
      {missingIncoterm ? (
        <p className="warning-banner">Incoterm is missing. CIF responsibility analysis cannot be completed.</p>
      ) : unsupported ? (
        <p className="notice">This MVP focuses on CIF. Other Incoterms are not fully supported yet.</p>
      ) : (
        <>
          {missingNamedPlace && <p className="warning-banner">CIF named destination port is missing. Responsibility analysis may be incomplete.</p>}
          <dl className="field-grid">
            <div><dt>Incoterm</dt><dd>CIF</dd></div>
            <div><dt>Named Destination Port</dt><dd>{namedPlace || "Missing"}</dd></div>
            <div><dt>Risk Transfer Point</dt><dd>{responsibility?.risk_transfer_point || "Loaded on board at port of loading"}</dd></div>
          </dl>
          <h3>Seller Responsibilities</h3>
          <ul className="rule-list">
            {(responsibility?.seller_responsibilities ?? [
              "export clearance",
              "load goods on board",
              "arrange freight",
              "arrange insurance",
              "provide shipping and insurance documents",
              "meet LC shipment and presentation deadlines"
            ]).map((item) => <li key={`seller-${item}`}>{item}</li>)}
          </ul>
          <h3>Buyer Responsibilities</h3>
          <ul className="rule-list">
            {(responsibility?.buyer_responsibilities ?? [
              "bear risk after loading",
              "import clearance",
              "import duties",
              "destination port handling / delay exposure",
              "receive cargo"
            ]).map((item) => <li key={`buyer-${item}`}>{item}</li>)}
          </ul>
        </>
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

function AgentRunProgressPanel({
  activeStep,
  elapsedSeconds,
  eventConfig,
  completed = false,
  onDismiss,
}: {
  activeStep: number;
  elapsedSeconds: number;
  eventConfig: EventConfig | null;
  completed?: boolean;
  onDismiss?: () => void;
}) {
  const mode = eventConfig?.event_source_mode ?? "REAL";
  const queryLimit = eventConfig?.external_event_query_limit ?? 3;
  const connectorText = eventConfig?.connectors?.length ? eventConfig.connectors.join(", ") : "configured connectors";

  return (
    <section className="agent-run-window" aria-live="polite">
      <div className="agent-run-window-header">
        <div>
          <span className={completed ? "run-complete-dot" : "run-live-dot"} />
          <strong>{completed ? "Agent run completed" : "Agent is running"}</strong>
          <small>
            {mode} mode · max {queryLimit} external event queries · {connectorText}
          </small>
        </div>
        <span className="tag">{elapsedSeconds}s elapsed</span>
      </div>
      <div className="agent-run-progress">
        {agentProgressSteps.map((step, index) => {
          const state = completed || index < activeStep ? "done" : index === activeStep ? "active" : "pending";
          return (
            <div className={`agent-run-progress-step ${state}`} key={step.title}>
              <span>{index + 1}</span>
              <div>
                <strong>{step.title}</strong>
                <small>{step.detail}</small>
              </div>
            </div>
          );
        })}
      </div>
      <p>
        {completed
          ? "All monitoring stages finished. Review the Agent Runs tab for the persisted trace and summary."
          : "This window tracks the live monitoring request. Steps update when the backend cycle completes."}
      </p>
      {completed && onDismiss && (
        <button className="secondary-action" type="button" onClick={onDismiss}>Dismiss</button>
      )}
    </section>
  );
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
