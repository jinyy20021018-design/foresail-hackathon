import { useEffect, useMemo, useRef, useState } from "react";
import { api, type CaseSummary, type TradeCase } from "../api/client";
import { CaseStatusBadge, RiskBadge } from "../components/Badges";
import { GuideWelcome } from "../components/guide/GuideWelcome";
import { GUIDE_RESTART_EVENT, guideStore } from "../components/guide/guideContent";
import "../styles/guide.css";

type Props = {
  caseIds: string[];
  onNavigate: (path: string) => void;
  onRegisterCase: (tradeCase: TradeCase) => void;
  onForgetCase: (caseId: string) => void;
};

export function CaseLibrary({ caseIds, onNavigate, onForgetCase }: Props) {
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("ALL");
  const [risk, setRisk] = useState("ALL");
  const [owner, setOwner] = useState("ALL");
  const [isLoading, setIsLoading] = useState(false);
  const [isSeeding, setIsSeeding] = useState(false);
  const [deletingCaseId, setDeletingCaseId] = useState<string | null>(null);
  const [pendingDeleteCase, setPendingDeleteCase] = useState<CaseSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [fallbackWarning, setFallbackWarning] = useState<string | null>(null);
  const seedAttempted = useRef(false);
  const [showWelcome, setShowWelcome] = useState(false);

  // First-time landing greets the user here, then steers them into creating a
  // case. Once the user has skipped, nothing shows again.
  useEffect(() => {
    if (!guideStore.welcomeSeen() && !guideStore.skipped()) setShowWelcome(true);
  }, []);

  useEffect(() => {
    const restart = () => {
      guideStore.reset();
      setShowWelcome(true);
    };
    window.addEventListener(GUIDE_RESTART_EVENT, restart);
    return () => window.removeEventListener(GUIDE_RESTART_EVENT, restart);
  }, []);

  async function seedBoard() {
    setIsSeeding(true);
    try {
      const result = await api.seedBoard();
      setCases(result.cases);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Failed to seed monitoring board.");
      const response = await api.listCases().catch(() => null);
      if (response) setCases(response.cases);
    } finally {
      setIsSeeding(false);
    }
  }

  async function loadCases() {
    setIsLoading(true);
    setError(null);
    setFallbackWarning(null);
    try {
      const response = await api.listCases();
      if (response.cases.length === 0 && !seedAttempted.current) {
        seedAttempted.current = true;
        setIsLoading(false);
        await seedBoard();
        return;
      }
      setCases(response.cases);
    } catch {
      setFallbackWarning("Using local fallback case list because backend case library API is unavailable.");
      try {
        setCases(await loadFallbackCases(caseIds));
      } catch (caught) {
        setError(caught instanceof Error ? caught.message : "Failed to load cases.");
      }
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void loadCases();
  }, [caseIds.join("|")]);

  async function deleteCase(caseId: string) {
    setDeletingCaseId(caseId);
    setError(null);
    try {
      await api.deleteCase(caseId);
      setCases((currentCases) => currentCases.filter((caseSummary) => caseSummary.case_id !== caseId));
      onForgetCase(caseId);
      setPendingDeleteCase(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : `Failed to delete ${caseId}.`);
    } finally {
      setDeletingCaseId(null);
    }
  }

  const filteredCases = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return cases.filter((caseSummary) => {
      const riskLevel = caseSummary.risk_level || "Low";
      const ownerName = caseSummary.owner || "Trade Ops";
      const haystack = [
        caseSummary.case_id,
        caseSummary.vessel,
        caseSummary.route,
        caseSummary.port_of_loading,
        caseSummary.port_of_discharge,
        caseSummary.final_destination,
        ownerName,
      ].join(" ").toLowerCase();
      return (
        (!normalizedQuery || haystack.includes(normalizedQuery)) &&
        (status === "ALL" || caseSummary.status === status) &&
        (risk === "ALL" || riskLevel === risk) &&
        (owner === "ALL" || ownerName === owner)
      );
    });
  }, [cases, owner, query, risk, status]);

  const summary = useMemo(() => {
    const actionRequired = cases.filter((item) => item.status === "ACTION_REQUIRED").length;
    const atRisk = cases.filter((item) => item.risk_level === "High" || item.status === "AT_RISK" || item.status === "ACTION_REQUIRED").length;
    const gaps = cases.reduce((total, item) => total + (item.information_gaps_count ?? 0), 0);
    const deadlines = cases.filter((item) => isWithinSevenDays(item.next_deadline?.date)).length;
    return [
      { label: "Total Cases", count: cases.length, description: "All tracked trade cases", tone: "blue", icon: "∑" },
      { label: "At Risk", count: atRisk, description: "Material exposure", tone: "red", icon: "!" },
      { label: "Action Required", count: actionRequired, description: "Needs your decision", tone: "orange", icon: "↯" },
      { label: "Deadlines in 7 Days", count: deadlines, description: "Upcoming shipment dates", tone: "amber", icon: "◷" },
      { label: "Open Info Gaps", count: gaps, description: "Missing decision inputs", tone: "blue", icon: "◇" }
    ];
  }, [cases]);

  return (
    <section className="page">
      <div className="page-header">
        <div>
          <h1>Case Library</h1>
          <p>Monitor all trade cases and take action on risks.</p>
        </div>
        <div className="header-actions">
          <button className="secondary-action" type="button" onClick={loadCases} disabled={isLoading}>Refresh</button>
          <button className="primary-action" type="button" onClick={() => onNavigate("/cases/new")}>Create New Case</button>
        </div>
      </div>

      {fallbackWarning && <div className="warning-banner">{fallbackWarning}</div>}
      {error && <div className="error">{error}</div>}

      <div className="summary-card-grid">
        {summary.map((item) => (
          <article className="summary-card" key={item.label}>
            <span className={`summary-icon ${item.tone}`}>{item.icon}</span>
            <div>
              <small>{item.label}</small>
              <strong>{item.count}</strong>
              <p>{item.description}</p>
            </div>
          </article>
        ))}
      </div>

      <div className="filter-bar">
        <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search cases by Case ID, vessel, route, or customer..." />
        <select value={status} onChange={(event) => setStatus(event.target.value)}>
          <option value="ALL">All Status</option>
          <option value="ACTIVE">ACTIVE</option>
          <option value="WATCHING">WATCHING</option>
          <option value="AT_RISK">AT_RISK</option>
          <option value="ACTION_REQUIRED">ACTION_REQUIRED</option>
          <option value="MONITORING">MONITORING</option>
        </select>
        <select value={risk} onChange={(event) => setRisk(event.target.value)}>
          <option value="ALL">All Risk</option>
          <option value="High">High</option>
          <option value="Medium">Medium</option>
          <option value="Low">Low</option>
        </select>
        <select value={owner} onChange={(event) => setOwner(event.target.value)}>
          <option value="ALL">All Owners</option>
          <option value="Trade Ops">Trade Ops</option>
          <option value="Jenny Li">Jenny Li</option>
          <option value="Michael Wong">Michael Wong</option>
        </select>
      </div>

      <section className="panel case-list-panel" aria-label={`${filteredCases.length} of ${cases.length} cases`}>
        {isSeeding ? (
          <div className="empty-block">
            <h3>Seeding monitoring board…</h3>
            <p>Building demo trade cases and running the monitoring agent against live corridor and weather signals.</p>
          </div>
        ) : isLoading ? <p className="empty-state">Loading cases...</p> : filteredCases.length === 0 ? (
          <div className="empty-block">
            <h3>No cases yet</h3>
            <p>Create a demo case or a new case to start the monitoring workflow.</p>
            <button className="primary-action" type="button" onClick={() => onNavigate("/cases/new")}>Create New Case</button>
          </div>
        ) : (
          <div className="case-list">
            <div className="case-list-head" aria-hidden="true">
              <span>Case</span><span>Decision</span><span>Next deadline</span><span>Work queue</span><span>Last run</span><span />
            </div>
            {filteredCases.map((caseSummary) => (
              <article className="case-list-row" key={caseSummary.case_id}>
                <div className="case-identity">
                  <button className="case-id-link" type="button" onClick={() => onNavigate(`/cases/${caseSummary.case_id}`)}>{caseSummary.case_id}</button>
                  <strong>{caseSummary.vessel || "Unknown Vessel"}</strong>
                  <span className="case-route">{caseSummary.route || routePorts(caseSummary) || "Route unavailable"}</span>
                  <small>Owner: {caseSummary.owner || "Trade Ops"}</small>
                </div>
                <div className="case-decision">
                  <CaseStatusBadge value={caseSummary.status || "DRAFT"} />
                  <RiskBadge value={caseSummary.risk_level || "Low"} />
                </div>
                <div className="case-deadline">
                  <strong>{formatDate(caseSummary.next_deadline?.date)}</strong>
                  <small>{caseSummary.next_deadline?.label || "No active deadline"}</small>
                </div>
                <div className="case-work-queue">
                  <QueueMetric label="Actions" value={caseSummary.open_actions_count ?? 0} />
                  <QueueMetric label="Gaps" value={caseSummary.information_gaps_count ?? 0} />
                  <QueueMetric label="Conflicts" value={caseSummary.open_conflicts_count ?? 0} critical={(caseSummary.high_conflicts_count ?? 0) > 0} />
                </div>
                <div className="case-last-run">
                  <strong>{caseSummary.last_agent_run_id || "Not run"}</strong>
                  <small>{formatTimestamp(caseSummary.last_agent_run_at)}</small>
                </div>
                <div className="case-row-actions">
                  <button
                    className="case-delete-button"
                    type="button"
                    aria-label={`Delete ${caseSummary.case_id}`}
                    title={`Delete ${caseSummary.case_id}`}
                    disabled={deletingCaseId === caseSummary.case_id}
                    onClick={() => setPendingDeleteCase(caseSummary)}
                  >
                    {deletingCaseId === caseSummary.case_id ? "..." : "Del"}
                  </button>
                  <button
                    className="case-open-button"
                    type="button"
                    aria-label={`Open ${caseSummary.case_id}`}
                    title={`Open ${caseSummary.case_id}`}
                    onClick={() => onNavigate(`/cases/${caseSummary.case_id}`)}
                  >
                    →
                  </button>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>

      {pendingDeleteCase && (
        <div
          className="confirm-modal-backdrop"
          role="presentation"
          onClick={() => {
            if (deletingCaseId !== pendingDeleteCase.case_id) setPendingDeleteCase(null);
          }}
        >
          <section
            className="confirm-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-case-title"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="confirm-modal-icon">!</div>
            <div className="confirm-modal-body">
              <span className="section-kicker">Delete case</span>
              <h2 id="delete-case-title">Delete {pendingDeleteCase.case_id}?</h2>
              <p>
                This will remove the case workspace, saved documents, extracted fields, agent runs, risks, gaps, drafts,
                and treatment outputs for this case.
              </p>
              <div className="delete-case-preview">
                <strong>{pendingDeleteCase.vessel || "Unknown Vessel"}</strong>
                <span>{pendingDeleteCase.route || routePorts(pendingDeleteCase) || "Route unavailable"}</span>
              </div>
            </div>
            <div className="confirm-modal-actions">
              <button className="secondary-action" type="button" onClick={() => setPendingDeleteCase(null)} disabled={deletingCaseId === pendingDeleteCase.case_id}>
                Cancel
              </button>
              <button className="danger-action" type="button" onClick={() => void deleteCase(pendingDeleteCase.case_id)} disabled={deletingCaseId === pendingDeleteCase.case_id}>
                {deletingCaseId === pendingDeleteCase.case_id ? "Deleting..." : "Delete Case"}
              </button>
            </div>
          </section>
        </div>
      )}

      {showWelcome && (
        <GuideWelcome
          onStart={() => {
            guideStore.markWelcomeSeen();
            setShowWelcome(false);
            onNavigate("/cases/new");
          }}
          onSkip={() => {
            guideStore.markWelcomeSeen();
            guideStore.setSkipped();
            setShowWelcome(false);
          }}
        />
      )}
    </section>
  );
}

async function loadFallbackCases(caseIds: string[]): Promise<CaseSummary[]> {
  return Promise.all(
    caseIds.map(async (caseId) => {
      const [tradeCase, actions, gaps, runs, conflicts] = await Promise.all([
        api.getCase(caseId),
        api.getActions(caseId).catch(() => []),
        api.getInformationGaps(caseId).catch(() => []),
        api.getAgentRuns(caseId).catch(() => []),
        api.getFieldConflicts(caseId).catch(() => [])
      ]);
      const openConflicts = conflicts.filter((conflict) => conflict.status === "OPEN");
      const highConflicts = openConflicts.filter((conflict) => conflict.severity === "High");
      const latestRun = runs[runs.length - 1];
      return {
        case_id: tradeCase.case_id,
        vessel: tradeCase.vessel,
        route: tradeCase.route,
        port_of_loading: tradeCase.port_of_loading,
        port_of_discharge: tradeCase.port_of_discharge,
        final_destination: tradeCase.final_destination,
        status: tradeCase.status,
        risk_level: highConflicts.length > 0 ? "High" : inferRiskLevel(tradeCase.status, gaps.length),
        next_deadline: tradeCase.latest_shipment_date ? { label: "Latest shipment", date: tradeCase.latest_shipment_date } : null,
        open_actions_count: actions.length,
        information_gaps_count: gaps.length,
        open_conflicts_count: openConflicts.length,
        high_conflicts_count: highConflicts.length,
        last_agent_run_at: latestRun?.completed_at || latestRun?.started_at || null,
        last_agent_run_id: latestRun?.agent_run_id || null,
        owner: "Trade Ops",
        updated_at: null,
      };
    })
  );
}

function inferRiskLevel(statusValue: string | null | undefined, gapsCount: number) {
  if (statusValue === "ACTION_REQUIRED" || statusValue === "AT_RISK") return "High";
  if (gapsCount > 0) return "Medium";
  return "Low";
}

function isWithinSevenDays(value: string | null | undefined) {
  if (!value) return false;
  const deadline = new Date(value);
  if (Number.isNaN(deadline.getTime())) return false;
  const now = new Date();
  const diff = deadline.getTime() - now.getTime();
  return diff >= 0 && diff <= 7 * 24 * 60 * 60 * 1000;
}

function routePorts(caseSummary: CaseSummary) {
  return [caseSummary.port_of_loading, caseSummary.port_of_discharge, caseSummary.final_destination].filter(Boolean).join(" / ");
}

function QueueMetric({ label, value, critical = false }: { label: string; value: number; critical?: boolean }) {
  return <span className={critical ? "queue-metric critical" : "queue-metric"}><b>{value}</b><small>{label}</small></span>;
}

function formatDate(value: string | null | undefined) {
  if (!value) return "No deadline";
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("en", { month: "short", day: "numeric", year: "numeric" }).format(date);
}

function formatTimestamp(value: string | null | undefined) {
  if (!value) return "No agent activity";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("en", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }).format(date);
}
