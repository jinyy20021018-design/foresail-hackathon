import type { ObligationDeadline } from "../api/client";
import "../styles/viz.css";

function daysUntil(iso: string): number | null {
  if (!iso) return null;
  const d = new Date(`${iso}T00:00:00`);
  if (Number.isNaN(d.getTime())) return null;
  return Math.round((d.getTime() - Date.now()) / 86_400_000);
}

function shortDate(iso: string): string {
  const d = new Date(`${iso}T00:00:00`);
  if (Number.isNaN(d.getTime())) return iso || "—";
  return new Intl.DateTimeFormat("en", { month: "short", day: "numeric" }).format(d);
}

// Urgency of a deadline drives its colour: the fewer days left, the hotter.
function urgencyTone(days: number | null): string {
  if (days == null) return "faint";
  if (days <= 3) return "red";
  if (days <= 10) return "amber";
  return "green";
}

export function DeadlineMatrix({ obligations }: { obligations: ObligationDeadline[] }) {
  const dated = obligations
    .filter((o) => o.deadline_date)
    .map((o) => ({ ...o, days: daysUntil(o.deadline_date) }))
    .sort((a, b) => (a.days ?? 9999) - (b.days ?? 9999));
  if (dated.length === 0) return null;

  const horizon = Math.max(30, ...dated.map((o) => o.days ?? 0));
  const earliest = dated[0];

  return (
    <div className="viz-card deadline-matrix">
      <div className="viz-head">
        <div>
          <span className="viz-kicker">Deadline countdown</span>
          <h3>Obligations on the clock</h3>
        </div>
        {earliest.days != null && (
          <span className={`dl-earliest ${urgencyTone(earliest.days)}`}>
            {earliest.days <= 0 ? "Due now" : `${earliest.days}d to first deadline`}
          </span>
        )}
      </div>
      <div className="dl-rows">
        {dated.map((o) => {
          const tone = urgencyTone(o.days);
          const pct = o.days == null ? 100 : Math.max(4, Math.min(100, Math.round((o.days / horizon) * 100)));
          return (
            <div className="dl-row" key={o.obligation_id}>
              <div className="dl-name">
                <span className={`dl-dot ${tone}`} />
                <span title={o.name}>{o.name}</span>
              </div>
              <div className="dl-track">
                <div className={`dl-fill ${tone}`} style={{ width: `${pct}%` }} />
              </div>
              <div className="dl-meta">
                <strong className={tone}>{o.days == null ? "—" : o.days <= 0 ? "now" : `${o.days}d`}</strong>
                <span>{shortDate(o.deadline_date)}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
