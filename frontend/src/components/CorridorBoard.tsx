import { useEffect, useState } from "react";
import { api, type CorridorState } from "../api/client";
import "../styles/viz.css";

const STATE_RANK: Record<string, number> = { RED: 0, AMBER: 1, GREEN: 2 };
const TREND_GLYPH: Record<string, string> = { UP: "▲", DOWN: "▼", STABLE: "—" };

function stateClass(state: string): string {
  const s = state.toUpperCase();
  return s === "RED" ? "red" : s === "AMBER" ? "amber" : "green";
}

export function CorridorBoard({ onRoute }: { onRoute?: string[] }) {
  const [corridors, setCorridors] = useState<CorridorState[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api
      .getCorridors()
      .then((res) => {
        if (!cancelled) setCorridors(res.corridors);
      })
      .catch(() => {
        if (!cancelled) setCorridors([]);
      })
      .finally(() => {
        if (!cancelled) setLoaded(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const routeSet = new Set((onRoute ?? []).map((c) => c.toLowerCase()));
  const sorted = [...corridors].sort((a, b) => {
    const onA = routeSet.has(a.corridor_id) ? 0 : 1;
    const onB = routeSet.has(b.corridor_id) ? 0 : 1;
    if (onA !== onB) return onA - onB;
    return (STATE_RANK[a.state.toUpperCase()] ?? 3) - (STATE_RANK[b.state.toUpperCase()] ?? 3);
  });

  const elevated = corridors.filter((c) => c.state.toUpperCase() !== "GREEN").length;

  if (!loaded) return null;

  return (
    <div className="viz-card corridor-board">
      <div className="viz-head">
        <div>
          <span className="viz-kicker">Corridor risk state machine</span>
          <h3>Global shipping corridors</h3>
        </div>
        <span className="viz-badge-count">{elevated} elevated · {corridors.length} watched</span>
      </div>
      <div className="corridor-grid">
        {sorted.map((c) => {
          const cls = stateClass(c.state);
          const onRouteHere = routeSet.has(c.corridor_id);
          const signalPct = Math.max(4, Math.min(100, Math.round((c.signal / 2) * 100)));
          return (
            <div key={c.corridor_id} className={`corridor-cell ${cls}${onRouteHere ? " on-route" : ""}`}>
              <div className="corridor-top">
                <span className={`corridor-dot ${cls}`} aria-hidden="true" />
                <span className="corridor-name" title={c.name}>{c.name}</span>
                {onRouteHere && <span className="corridor-onroute">ON ROUTE</span>}
              </div>
              <div className="corridor-state-row">
                <span className={`corridor-state-tag ${cls}`}>{c.state.toUpperCase()}</span>
                <span className={`corridor-trend ${c.trend === "UP" ? "up" : c.trend === "DOWN" ? "down" : ""}`}>
                  {TREND_GLYPH[c.trend] ?? "—"} {c.trend}
                </span>
                {c.baseline_state.toUpperCase() !== c.state.toUpperCase() && (
                  <span className="corridor-base">base {c.baseline_state}</span>
                )}
              </div>
              <div className="corridor-signal-track" title={`Escalation signal ${c.signal.toFixed(2)}`}>
                <div className={`corridor-signal-fill ${cls}`} style={{ width: `${signalPct}%` }} />
              </div>
              {c.escalation_triggers?.[0] && (
                <p className="corridor-trigger">Next: {c.escalation_triggers[0]}</p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
