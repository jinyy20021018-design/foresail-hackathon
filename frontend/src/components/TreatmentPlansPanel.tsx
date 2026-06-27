import { useMemo, useState } from "react";
import {
  api,
  type ActionDraft,
  type ApprovalPackage,
  type InformationGap,
  type ObligationDeadline,
  type RecommendedAction,
  type RelevanceResult,
  type RiskSummary,
  type TreatmentPlan,
} from "../api/client";
import { RiskBadge } from "./Badges";

type Props = {
  caseId: string;
  hasConfirmedFacts: boolean;
  hasAgentRuns: boolean;
  highOpenConflictsCount: number;
  relevanceResults: RelevanceResult[];
  riskSummary: RiskSummary | null;
  obligations: ObligationDeadline[];
  gaps: InformationGap[];
  actions: RecommendedAction[];
  drafts: ActionDraft[];
  plans: TreatmentPlan[];
  approvalPackages: ApprovalPackage[];
  onPlansChange: (plans: TreatmentPlan[]) => void;
  onApprovalPackagesChange: (packages: ApprovalPackage[]) => void;
  onError: (message: string | null) => void;
};

export function TreatmentPlansPanel({
  caseId,
  hasConfirmedFacts,
  hasAgentRuns,
  highOpenConflictsCount,
  relevanceResults,
  riskSummary,
  obligations,
  gaps,
  actions,
  drafts,
  plans,
  approvalPackages,
  onPlansChange,
  onApprovalPackagesChange,
  onError,
}: Props) {
  const [selectedPlanId, setSelectedPlanId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const selectedPlan = useMemo(
    () => plans.find((plan) => plan.plan_id === selectedPlanId) || plans.find((plan) => plan.status === "RECOMMENDED") || plans[0],
    [plans, selectedPlanId]
  );
  const selectedPackage = selectedPlan ? approvalPackages.find((item) => item.plan_id === selectedPlan.plan_id) : undefined;
  const canGeneratePlans = hasConfirmedFacts || highOpenConflictsCount > 0;
  const isConflictSafeFlow = !hasConfirmedFacts && highOpenConflictsCount > 0;

  async function refreshPlans() {
    onPlansChange(await api.listTreatmentPlans(caseId));
  }

  async function refreshApprovals() {
    onApprovalPackagesChange(await api.listApprovalPackages(caseId));
  }

  async function generatePlans() {
    setIsLoading(true);
    onError(null);
    try {
      const result = await api.generateTreatmentPlans(caseId);
      onPlansChange(result.plans);
      setSelectedPlanId(result.recommended_plan_id);
      await refreshApprovals();
    } catch (caught) {
      onError(caught instanceof Error ? caught.message : "Treatment plan generation failed.");
    } finally {
      setIsLoading(false);
    }
  }

  async function selectPlan(planId: string) {
    await api.selectTreatmentPlan(caseId, planId);
    setSelectedPlanId(planId);
    await refreshPlans();
  }

  async function archivePlan(planId: string) {
    await api.archiveTreatmentPlan(caseId, planId);
    await refreshPlans();
  }

  async function generateApproval(planId: string) {
    await api.generateApprovalPackage(caseId, planId);
    setSelectedPlanId(planId);
    await refreshApprovals();
  }

  async function updateApproval(status: string) {
    if (!selectedPackage) return;
    await api.updateApprovalPackageStatus(caseId, selectedPackage.approval_package_id, status, `${status} in MVP review.`);
    await refreshApprovals();
  }

  if (!canGeneratePlans && plans.length === 0) {
    return (
      <section className="panel full-width prerequisite-panel">
        <span className="prerequisite-icon">3</span>
        <div>
          <span className="section-kicker">Treatment planning</span>
          <h2>Confirm the case facts first</h2>
          <p>Treatment options depend on the agreed shipment value, dates, route, and contractual obligations.</p>
          <ol><li className="complete">Upload documents</li><li>Review extracted facts</li><li>Confirm case facts</li><li>Generate treatment options</li></ol>
        </div>
      </section>
    );
  }

  return (
    <section>
      <div className="panel full-width">
        <div className="panel-heading">
          <div>
            <h2>Treatment Plans</h2>
            <p className="subtle">Generate and compare structured risk treatment options for this case.</p>
          </div>
          <button
            className="primary-action"
            type="button"
            onClick={generatePlans}
            disabled={!canGeneratePlans || isLoading}
            title={!canGeneratePlans ? "Confirmed case facts are required before generating treatment plans." : undefined}
          >
            {isLoading ? "Generating..." : "Generate Treatment Plans"}
          </button>
        </div>
        {!hasConfirmedFacts && highOpenConflictsCount === 0 && (
          <div className="warning-banner">Confirmed case facts are required before generating treatment plans.</div>
        )}
        {isConflictSafeFlow && (
          <div className="warning-banner">High severity conflicts are open. Only a low-cost conflict-resolution plan can be generated until conflicts are resolved.</div>
        )}
        {!hasAgentRuns && <div className="notice">No risk analysis available yet. Run Agent Monitoring Cycle first, or generate fallback plans after confirming facts.</div>}
        {hasConfirmedFacts && highOpenConflictsCount > 0 && <div className="warning-banner">Unresolved High conflicts exist. Low-cost treatment can be drafted, but high-cost treatment should not be submitted.</div>}
      </div>

      <div className="workspace-grid">
        <section className="panel">
          <div className="panel-heading"><h2>Current Risk Summary</h2></div>
          <MetricLine label="Relevant events" value={relevanceResults.filter((item) => item.classification === "Relevant").length} />
          <MetricLine label="Risk exposures" value={riskSummary?.exposures.length ?? 0} />
          <MetricLine label="High obligations" value={obligations.filter((item) => item.severity === "High").length} />
          <MetricLine label="Information gaps" value={gaps.length} />
          <MetricLine label="Open actions" value={actions.length + drafts.length} />
        </section>

        <section className="panel">
          <div className="panel-heading"><h2>Approval Summary</h2></div>
          {!selectedPlan ? <p className="empty-state">Select a treatment plan to review its approval package.</p> : !selectedPackage ? (
            <p className="empty-state">No approval package has been generated for this plan.</p>
          ) : (
            <>
              <h3>{selectedPackage.title}</h3>
              <p>{selectedPackage.summary}</p>
              <dl className="field-grid">
                <div><dt>Status</dt><dd>{selectedPackage.approval_status}</dd></div>
                <div><dt>Cost</dt><dd>{selectedPackage.estimated_cost_level}</dd></div>
                <div><dt>Scope</dt><dd>{selectedPackage.approval_scope || "EXECUTION_APPROVAL"}</dd></div>
                <div><dt>Roles</dt><dd>{selectedPackage.approval_roles.join(", ") || "None"}</dd></div>
                <div><dt>Decision Note</dt><dd>{selectedPackage.decision_note || "None"}</dd></div>
              </dl>
              <div className="inline-actions">
                {["SUBMITTED", "APPROVED", "REJECTED", "NEEDS_MORE_INFO", "ARCHIVED"].map((status) => (
                  <button type="button" key={status} onClick={() => updateApproval(status)}>{status}</button>
                ))}
              </div>
            </>
          )}
        </section>
      </div>

      {plans.length === 0 ? <div className="empty-block"><h3>No treatment plans yet</h3><p>Generate plans after confirming case facts.</p></div> : (
        <>
          <div className="plan-grid">
            {plans.map((plan) => (
              <article className={`plan-card ${selectedPlan?.plan_id === plan.plan_id ? "selected" : ""}`} key={plan.plan_id}>
                <div className="panel-heading">
                  <div>
                    <span className="action-id">{plan.plan_id} | {plan.plan_type}</span>
                    <h3>{plan.plan_name}</h3>
                  </div>
                  {plan.status === "RECOMMENDED" && <span className="badge status-action-required">Recommended</span>}
                </div>
                <p>{plan.summary}</p>
                <dl className="field-grid">
                  <div><dt>Cost</dt><dd>{plan.estimated_cost_level} {plan.estimated_cost_amount ? `${plan.estimated_cost_amount} ${plan.estimated_cost_currency}` : ""}</dd></div>
                  <div><dt>Time</dt><dd>{plan.estimated_time_to_execute || "TBD"}</dd></div>
                  <div><dt>Approval</dt><dd>{plan.approval_required ? "Required" : "Not required"}</dd></div>
                  <div><dt>Status</dt><dd>{plan.status}</dd></div>
                  <div><dt>Perspective</dt><dd>{plan.perspective || "SELLER"}</dd></div>
                  <div><dt>Incoterm</dt><dd>{plan.incoterm_basis || "N/A"}</dd></div>
                  <div><dt>Covered Risks</dt><dd>{plan.covered_risks.length}</dd></div>
                  <div><dt>Residual Risks</dt><dd>{plan.residual_risks.length}</dd></div>
                </dl>
                <p className="subtle">{plan.rationale}</p>
                <div className="inline-actions">
                  <button type="button" onClick={() => setSelectedPlanId(plan.plan_id)}>View Details</button>
                  <button type="button" onClick={() => selectPlan(plan.plan_id)}>Select Plan</button>
                  <button type="button" onClick={() => generateApproval(plan.plan_id)}>Generate Approval Package</button>
                  <button type="button" onClick={() => archivePlan(plan.plan_id)}>Archive</button>
                </div>
              </article>
            ))}
          </div>

          <section className="panel full-width">
            <div className="panel-heading"><h2>Plan Comparison</h2></div>
            <div className="table-wrap">
              <table>
                <thead><tr><th>Plan</th><th>Cost</th><th>Amount</th><th>Time</th><th>Covered</th><th>Residual</th><th>Approval</th><th>Recommendation</th><th>Status</th></tr></thead>
                <tbody>
                  {plans.map((plan) => (
                    <tr key={plan.plan_id}>
                      <td>{plan.plan_name}</td>
                      <td>{plan.estimated_cost_level}</td>
                      <td>{plan.estimated_cost_amount ?? "-"} {plan.estimated_cost_currency ?? ""}</td>
                      <td>{plan.estimated_time_to_execute}</td>
                      <td>{plan.covered_risks.length}</td>
                      <td>{plan.residual_risks.length}</td>
                      <td>{plan.approval_required ? "Yes" : "No"}</td>
                      <td>{plan.recommendation_level}</td>
                      <td>{plan.status}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {selectedPlan && <PlanDetails plan={selectedPlan} />}
        </>
      )}
    </section>
  );
}

function MetricLine({ label, value }: { label: string; value: number }) {
  return <p className="metric-line"><span>{label}</span><strong>{value}</strong></p>;
}

function PlanDetails({ plan }: { plan: TreatmentPlan }) {
  return (
    <div className="workspace-grid">
      <section className="panel">
        <div className="panel-heading"><h2>Plan Details</h2></div>
        <p className="subtle">Perspective: {plan.perspective || "SELLER"} | Incoterm basis: {plan.incoterm_basis || "N/A"}</p>
        <p>{plan.summary}</p>
        <ListBlock title="Required Actions" items={plan.required_actions} />
        <ListBlock title="Covered Risks" items={plan.covered_risks} />
        <ListBlock title="Preconditions" items={plan.preconditions} />
        <ListBlock title="Assumptions" items={plan.assumptions} />
        <ListBlock title="Recheck Triggers" items={plan.recheck_triggers} />
        <ListBlock title="Approval Roles" items={plan.approval_roles} empty="No approval required." />
      </section>
      <section className="panel">
        <div className="panel-heading"><h2>Residual Risks</h2><span className="tag">{plan.residual_risks.length}</span></div>
        {plan.residual_risks.map((risk) => (
          <article className="residual-risk" key={risk.residual_risk_id}>
            <div className="panel-heading">
              <h3>{risk.risk_title}</h3>
              <RiskBadge value={risk.severity} />
            </div>
            <p>{risk.description}</p>
            <small>Reason: {risk.reason_not_fully_covered}</small>
            <small>Trigger: {risk.monitoring_trigger}</small>
            <small>Owner: {risk.owner_role} | Status: {risk.status}</small>
          </article>
        ))}
      </section>
    </div>
  );
}

function ListBlock({ title, items, empty = "None" }: { title: string; items: string[]; empty?: string }) {
  return (
    <>
      <h3>{title}</h3>
      {items.length === 0 ? <p className="empty-state">{empty}</p> : <ul className="rule-list">{items.map((item) => <li key={item}>{item}</li>)}</ul>}
    </>
  );
}
