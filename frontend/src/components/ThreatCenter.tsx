import { useEffect, useState } from "react";
import { api, type Hazard, type RecommendedAction } from "../api/client";

type Props = {
  caseId: string;
  actions: RecommendedAction[];
  refreshKey?: string;
  onOpenActions?: () => void;
};

const URGENCY_ORDER: Record<string, number> = { ACT_NOW: 0, PREPARE: 1, MONITOR: 2 };
const URGENCY_LABEL: Record<string, string> = { ACT_NOW: "Act now", PREPARE: "Prepare", MONITOR: "Monitor" };

export function ThreatCenter({ caseId, actions, refreshKey = "", onOpenActions }: Props) {
  const [hazards, setHazards] = useState<Hazard[]>([]);

  useEffect(() => {
    let cancelled = false;
    api.getHazards(caseId)
      .then((payload) => {
        if (!cancelled) setHazards(payload);
      })
      .catch(() => {
        if (!cancelled) setHazards([]);
      });
    return () => {
      cancelled = true;
    };
  }, [caseId, refreshKey]);

  const groups = (["ACT_NOW", "PREPARE", "MONITOR"] as const)
    .map((tier) => ({ tier, items: hazards.filter((hazard) => (hazard.urgency ?? "MONITOR") === tier) }))
    .filter((group) => group.items.length > 0);
  const newCount = hazards.filter((hazard) => hazard.lifecycle === "NEW").length;
  const escalatedCount = hazards.filter((hazard) => hazard.lifecycle === "ESCALATED").length;
  const ongoingCount = hazards.filter((hazard) => hazard.lifecycle === "ONGOING").length;
  const earliestDeadline = actions
    .map((action) => action.deadline_date)
    .filter((value): value is string => Boolean(value))
    .sort()[0];
  const deadlineDays = earliestDeadline ? daysFromToday(earliestDeadline) : null;

  return (
    <section className="panel threat-center" aria-label="Threat center">
      <div className="threat-center-head">
        <div>
          <h2>Threat Center</h2>
          <p>
            {hazards.length === 0
              ? "No active hazards. Run the agent monitoring cycle to scan for threats."
              : `Since last run: ${newCount} new · ${escalatedCount} escalated · ${ongoingCount} ongoing`}
          </p>
        </div>
        {earliestDeadline && (
          <button type="button" className="deadline-chip" onClick={onOpenActions}>
            <b>{deadlineDays === 0 ? "Due today" : deadlineDays === 1 ? "Due tomorrow" : `${deadlineDays} days`}</b>
            <span>earliest action deadline · {earliestDeadline}</span>
          </button>
        )}
      </div>
      {groups.map((group) => (
        <div key={group.tier} className={`threat-group urgency-${group.tier.toLowerCase()}`}>
          <div className="threat-group-head">
            <span className={`urgency-badge urgency-${group.tier.toLowerCase()}`}>{URGENCY_LABEL[group.tier]}</span>
            <b>{group.items.length}</b>
            <p>{group.items[0].recommended_posture}</p>
          </div>
          <div className="threat-cards">
            {group.items.map((hazard) => (
              <ThreatCard key={hazard.hazard_id} hazard={hazard} />
            ))}
          </div>
        </div>
      ))}
    </section>
  );
}

function ThreatCard({ hazard }: { hazard: Hazard }) {
  const urgency = hazard.urgency ?? "MONITOR";
  const window = hazard.expected_impact_window;
  const ourRisk = hazard.attribution?.our_cargo_risk || hazard.attribution?.our_payment_risk;
  return (
    <article className={`threat-card urgency-${urgency.toLowerCase()}`}>
      <div className="threat-card-badges">
        <span className={`lifecycle-badge lifecycle-${hazard.lifecycle.toLowerCase()}`}>{hazard.lifecycle}</span>
        <span className={`classification-badge ${hazard.classification === "Relevant" ? "relevant" : "watch"}`}>
          {hazard.classification}
        </span>
        {hazard.corroborated && <span className="corroborated-badge">✓ multi-source</span>}
        {ourRisk != null && <span className={`risk-owner-badge ${ourRisk ? "ours" : ""}`}>{ourRisk ? "Your risk" : "Counterparty"}</span>}
      </div>
      <h3>{hazard.title}</h3>
      <div className="threat-card-meta">
        {window && (
          <span>
            Impact {shortDate(window.start)}
            {window.end !== window.start ? ` – ${shortDate(window.end)}` : ""}
            {typeof hazard.lead_days === "number" && hazard.lead_days >= 0 ? ` · in ${hazard.lead_days}d` : ""}
          </span>
        )}
        <span>{hazard.sources.length} source{hazard.sources.length === 1 ? "" : "s"}</span>
      </div>
    </article>
  );
}

function daysFromToday(iso: string): number {
  const target = new Date(`${iso}T00:00:00`);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return Math.round((target.getTime() - today.getTime()) / 86400000);
}

function shortDate(value: string) {
  const parts = value.slice(0, 10).split("-");
  return parts.length === 3 ? `${parts[1]}-${parts[2]}` : value;
}
