import { useEffect, useMemo, useRef, useState } from "react";
import {
  api,
  type Hazard,
  type RecommendedAction,
  type RiskSummary,
  type TradeCase,
} from "../api/client";
import { RouteChart } from "./RouteChart";
import "../styles/fs2-overview.css";

type Props = {
  caseId: string;
  tradeCase: TradeCase;
  actions: RecommendedAction[];
  riskSummary: RiskSummary | null;
  refreshKey?: string;
  onOpenTab?: (tab: string) => void;
};

const FAMILY_TAG: Record<string, string> = {
  WEATHER: "WX",
  VESSEL: "VSL",
  PORT: "PORT",
  GEOPOLITICAL: "GEO",
  POLICY: "POLICY",
  CORRIDOR: "ROUTE",
  OTHER: "RISK",
};

const FAMILY_LABEL: Record<string, string> = {
  WEATHER: "Weather",
  VESSEL: "Vessel",
  PORT: "Port",
  GEOPOLITICAL: "Geopolitical",
  POLICY: "Policy",
  CORRIDOR: "Route",
  OTHER: "Risk",
};

const ANCHOR_LABEL: Record<string, string> = {
  ECS: "East China Sea",
  SCS: "South China Sea",
  AS: "Arabian Sea",
  SOH: "Strait of Hormuz",
  GH: "Gulf of Hormuz",
  IO: "Indian Ocean",
  IOC: "Indian Ocean",
  MALACCA: "Strait of Malacca",
  JEBEL_ALI: "Jebel Ali",
  SHANGHAI: "Shanghai",
};

const URGENCY_META: Record<string, { tag: string; tone: "hot" | "warn" | "watch" }> = {
  ACT_NOW: { tag: "Act now", tone: "hot" },
  PREPARE: { tag: "Prepare", tone: "warn" },
  MONITOR: { tag: "Monitor", tone: "watch" },
};

export function WorkspaceOverview({ caseId, tradeCase, actions, riskSummary, refreshKey = "", onOpenTab }: Props) {
  const [hazards, setHazards] = useState<Hazard[]>([]);
  const [selectedHazardId, setSelectedHazardId] = useState<string | null>(null);
  const [mapFocusRequest, setMapFocusRequest] = useState(0);
  const mapPanelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .getHazards(caseId)
      .then((h) => {
        if (!cancelled) setHazards(h);
      })
      .catch(() => {
        if (!cancelled) setHazards([]);
      });
    return () => {
      cancelled = true;
    };
  }, [caseId, refreshKey]);

  const sortedHazards = useMemo(() => {
    const order: Record<string, number> = { ACT_NOW: 0, PREPARE: 1, MONITOR: 2 };
    const ours = (h: Hazard) => (h.attribution?.our_cargo_risk || h.attribution?.our_payment_risk ? 0 : 1);
    return [...hazards].sort((a, b) => {
      const u = (order[a.urgency ?? "MONITOR"] ?? 2) - (order[b.urgency ?? "MONITOR"] ?? 2);
      if (u !== 0) return u;
      return ours(a) - ours(b);
    });
  }, [hazards]);

  const selectedHazard = useMemo(
    () => sortedHazards.find((h) => h.hazard_id === selectedHazardId) ?? null,
    [selectedHazardId, sortedHazards],
  );

  useEffect(() => {
    if (selectedHazardId && !selectedHazard) {
      setSelectedHazardId(null);
    }
  }, [selectedHazard, selectedHazardId]);

  const hazardCards = sortedHazards.slice(0, 3);
  const extraHazards = Math.max(0, sortedHazards.length - hazardCards.length);

  const latestShipment = tradeCase.latest_shipment_date;
  const daysToShipment = latestShipment ? daysFromToday(latestShipment) : null;
  const lcExpiry = tradeCase.lc_expiry_date;
  const daysToLc = lcExpiry ? daysFromToday(lcExpiry) : null;

  const sortedActions = useMemo(() => {
    return [...actions].sort((a, b) => {
      const da = a.deadline_date ?? "9999";
      const db = b.deadline_date ?? "9999";
      if (da !== db) return da < db ? -1 : 1;
      const pr: Record<string, number> = { High: 0, Medium: 1, Low: 2 };
      return (pr[a.priority] ?? 1) - (pr[b.priority] ?? 1);
    });
  }, [actions]);
  const taskItems = sortedActions.slice(0, 5);

  const exposures = riskSummary?.exposures ?? [];
  const perspective = (tradeCase.trade_perspective ?? "SELLER").toUpperCase();
  const flagChips = useMemo(() => {
    const seen = new Set<string>();
    const chips: Array<{ label: string; kind: "risk" | "on" | "neutral" }> = [];
    for (const exp of exposures) {
      if (seen.has(exp.category)) continue;
      seen.add(exp.category);
      const isRisk = String(exp.severity).toLowerCase() === "high" || exp.affected_party === perspective;
      chips.push({ label: exp.category, kind: isRisk ? "risk" : "neutral" });
    }
    if (String(tradeCase.incoterm || "").toUpperCase().startsWith("CIF")) {
      chips.push({ label: "Seller insurance in place", kind: "on" });
    }
    if (String(tradeCase.payment_method || "").toUpperCase().includes("LC")) {
      chips.push({ label: "LC terms confirmed", kind: "on" });
    }
    return chips.slice(0, 8);
  }, [exposures, perspective, tradeCase.incoterm, tradeCase.payment_method]);

  const countdownNote = hazardCards.some((h) => h.urgency === "ACT_NOW")
    ? "An act-now hazard sits on the shipment window. Review the amendment decision today."
    : "Monitoring the shipment window against the latest external signals.";

  const gaugePct = daysToShipment != null ? Math.max(6, Math.min(100, 100 - daysToShipment * 5)) : 30;

  const selectHazard = (hazard: Hazard) => {
    setSelectedHazardId(hazard.hazard_id);
    setMapFocusRequest((current) => current + 1);
    window.requestAnimationFrame(() => {
      mapPanelRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  };

  return (
    <div className="fs2-overview">
      <section className="route-alerts" aria-label="Route alerts">
        <div className="route-alerts-head">
          <div>
            <h2>Route alerts</h2>
            <p>{sortedHazards.length ? `${sortedHazards.length} active risks on this route` : "No active route risks"}</p>
          </div>
          {sortedHazards.length > 0 && (
            <button type="button" className="alert-link" onClick={() => onOpenTab?.("risks")}>
              View all alerts
            </button>
          )}
        </div>

        <div className="hazrow">
          {hazardCards.length === 0 && (
            <div className="haz haz-empty" style={{ gridColumn: "1 / -1" }}>
              <div className="top">
                <span className="code">No active hazards</span>
                <span className="tag watch">Clear</span>
              </div>
              <p className="haz-desc">Run the monitoring cycle to scan for route, vessel, weather, and contract threats.</p>
            </div>
          )}

          {hazardCards.map((h) => {
            const meta = URGENCY_META[h.urgency ?? "MONITOR"] ?? URGENCY_META.MONITOR;
            const ours = Boolean(h.attribution?.our_cargo_risk || h.attribution?.our_payment_risk);
            const selected = h.hazard_id === selectedHazardId;
            return (
              <button
                type="button"
                className={`haz alert-card ${selected ? "selected" : ""}`}
                key={h.hazard_id}
                onClick={() => selectHazard(h)}
                aria-pressed={selected}
              >
                <div className="top">
                  <span className="code">{hazardLabel(h)}</span>
                  <span className={`tag ${meta.tone}`}>{meta.tag}</span>
                </div>
                <p className="haz-desc" title={h.title}>{hazardMini(h)}</p>
                <div className="haz-meta">
                  <span>Impact: {impactWindowLabel(h)}</span>
                  <span className={`who ${ours ? "ours" : "them"}`}>{ours ? "Affects you" : "Counterparty exposure"}</span>
                </div>
              </button>
            );
          })}

          {extraHazards > 0 && (
            <button type="button" className="hazmore" onClick={() => onOpenTab?.("risks")}>
              +{extraHazards}
            </button>
          )}
        </div>
      </section>

      <div className="studio">
        <div className="left">
          <div className="panel count">
            <div className="lbl">Latest shipment - {latestShipment ? shortDate(latestShipment) : "TBD"}</div>
            <div className="num hot">{daysToShipment != null ? daysToShipment : "-"}<small> days</small></div>
            <p className="note">{countdownNote}</p>
            <div className="gaugewrap"><div className="gauge" style={{ width: `${gaugePct}%` }} /></div>
          </div>
          <div className="blackcard">
            <div className="bh"><h2>Next actions</h2><b>{taskItems.length}</b></div>
            {taskItems.length === 0 && <div className="task"><div><div className="tt">No actions yet</div><div className="ts">Run the monitoring cycle</div></div></div>}
            {taskItems.map((a, idx) => (
              <div className={`task${idx === 0 ? " next" : ""}`} key={a.action_id}>
                <span className="ti">
                  <svg viewBox="0 0 24 24"><path d="M4 6h16M4 12h16M4 18h10" /></svg>
                </span>
                <div>
                  <div className="tt">{a.title}</div>
                  <div className="ts">{actionSub(a)}</div>
                </div>
                {idx === 0 && <span className="upnext">UP NEXT</span>}
              </div>
            ))}
          </div>
        </div>

        <div className="panel deckpanel" ref={mapPanelRef}>
          <RouteChart
            caseId={caseId}
            tradeCase={tradeCase}
            refreshKey={refreshKey}
            selectedHazard={selectedHazard}
            focusRequest={mapFocusRequest}
            onClearSelectedHazard={() => setSelectedHazardId(null)}
          >
            <TimelineLanes tradeCase={tradeCase} hazards={hazards} />
          </RouteChart>
        </div>

        <div className="right">
          <div className="panel form">
            <div className="fh"><h2>Shipment information</h2></div>
            <div className="frow">
              <Field label="Status" value={statusLabel(tradeCase.status)} warn={tradeCase.status === "ACTION_REQUIRED" || tradeCase.status === "AT_RISK"} />
              <Field label="Seat" value={perspective === "SELLER" ? "Seller" : "Buyer"} note="AUTO" />
            </div>
            <Od label="Origin" value={tradeCase.port_of_loading || "TBD"} note={originCode(tradeCase)} />
            <Od label="Destination" value={destLabel(tradeCase)} note={destCode(tradeCase)} />
            <div className="frow">
              <Field label="Incoterm" value={(tradeCase.incoterm || "-").toUpperCase()} note="2020" />
              <Field label="Payment" value={tradeCase.payment_method || "-"} />
            </div>
            <div className="frow">
              <Field label="Amount" value={amountLabel(tradeCase)} />
              <Field label="Cargo" value={tradeCase.commodity || "-"} />
            </div>
            <div className="frow">
              <Field label="ETD" value={shortDate(tradeCase.etd)} />
              <Field label="ETA" value={shortDate(tradeCase.eta)} />
            </div>
            <div className="frow">
              <Field label="Latest shipment" value={latestShipment ? `${shortDate(latestShipment)}${daysToShipment != null ? ` - ${daysToShipment}d` : ""}` : "-"} warn />
              <Field label="LC expiry" value={lcExpiry ? `${shortDate(lcExpiry)}${daysToLc != null ? ` - ${daysToLc}d` : ""}` : "-"} />
            </div>
          </div>
          <div className="panel form">
            <div className="fh"><h2>Exposure flags</h2></div>
            <div className="chips">
              {flagChips.length === 0 && <span className="fchip">No exposures mapped yet</span>}
              {flagChips.map((c, i) => (
                <span key={`${c.label}-${i}`} className={`fchip${c.kind === "risk" ? " risk" : c.kind === "on" ? " on" : ""}`}>{c.label}</span>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function Field({ label, value, warn = false, note }: { label: string; value: string; warn?: boolean; note?: string }) {
  return (
    <div className="field">
      <label>{label}</label>
      <div className={`val${warn ? " warn" : ""}`}>{value}{note && <span>{note}</span>}</div>
    </div>
  );
}

function Od({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="od">
      <div className="l">{label}</div>
      <div className="v">{value}{note && <span>{note}</span>}</div>
    </div>
  );
}

function TimelineLanes({ tradeCase, hazards }: { tradeCase: TradeCase; hazards: Hazard[] }) {
  const model = useMemo(() => buildTimeline(tradeCase, hazards), [tradeCase, hazards]);
  if (!model) return null;
  const { voyage, weather, policy, deadlines, todayPct, ticks } = model;
  return (
    <div className="lanewrap">
      <div className="tl-grid">
        <span className="tl-grid-col1" />
        <div className="tl-grid-lines">
          {ticks.map((t, i) => <span key={`k${i}`} className="tl-tick" style={{ left: `${t.pct}%` }} />)}
          {deadlines.map((d, i) => <span key={`d${i}`} className="tl-vline" style={{ left: `${d.pct}%`, background: d.color }} />)}
          {todayPct != null && <span className="tl-vline tl-today" style={{ left: `${todayPct}%` }} />}
        </div>
      </div>

      <div className="lane"><span className="ln">Voyage</span>
        <div className="track">
          <div className="bar voy" style={{ left: `${voyage.left}%`, width: `${voyage.width}%` }} title={voyage.label}>{voyage.width > 24 ? voyage.label : ""}</div>
        </div>
      </div>
      <div className="lane"><span className="ln">Weather</span>
        <div className="track">
          {weather.length === 0 && <span className="lane-empty">No weather events on route</span>}
          {weather.map((b, i) => <div key={i} className="bar rr" style={{ left: `${b.left}%`, width: `${b.width}%` }} title={b.title}>{b.width > 10 ? b.short : ""}</div>)}
        </div>
      </div>
      <div className="lane"><span className="ln">Policy</span>
        <div className="track">
          {policy.length === 0 && <span className="lane-empty">No policy events on route</span>}
          {policy.map((b, i) => <div key={i} className="bar rb" style={{ left: `${b.left}%`, width: `${b.width}%` }} title={b.title}>{b.width > 10 ? b.short : ""}</div>)}
        </div>
      </div>
      <div className="lane lane-deadline"><span className="ln">Deadline</span>
        <div className="track">
          {deadlines.map((d, i) => (
            <div key={i} className={`dl-tag${d.pct > 55 ? " flag-end" : ""}${i % 2 ? " dl-low" : ""}`} style={{ left: `${d.pct}%`, color: d.color }}>{d.label}</div>
          ))}
        </div>
      </div>

      <div className="lane tl-axis"><span className="ln" />
        <div className="track">
          {ticks.map((t, i) => <span key={i} className="tl-axtick" style={{ left: `${t.pct}%` }}>{t.label}</span>)}
          {todayPct != null && <span className="tl-axtoday" style={{ left: `${todayPct}%` }}>TODAY</span>}
        </div>
      </div>
    </div>
  );
}

function buildTimeline(tc: TradeCase, hazards: Hazard[]) {
  const etd = parseDate(tc.etd);
  const eta = parseDate(tc.eta);
  if (!etd || !eta) return null;
  const latest = parseDate(tc.latest_shipment_date);
  const lc = parseDate(tc.lc_expiry_date);
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  const windows = hazards
    .map((h) => h.expected_impact_window)
    .filter((w): w is { start: string; end: string } => Boolean(w))
    .flatMap((w) => [parseDate(w.start), parseDate(w.end)])
    .filter((d): d is Date => Boolean(d));
  const all = [etd, eta, today, latest, lc, ...windows].filter((d): d is Date => Boolean(d));
  const rangeStart = addDays(new Date(Math.min(...all.map((d) => d.getTime()))), -2);
  const rangeEnd = addDays(new Date(Math.max(...all.map((d) => d.getTime()))), 3);
  const span = Math.max(1, diffDays(rangeStart, rangeEnd));
  const toPct = (d: Date) => clamp((diffDays(rangeStart, d) / span) * 100);
  const bar = (s: Date, e: Date) => {
    const left = toPct(s);
    const right = toPct(addDays(e, 1));
    return { left, width: Math.max(2, right - left) };
  };

  const voyage = { ...bar(etd, eta), label: voyageLabel(tc) };
  const weather = hazards
    .filter((h) => (h.family === "WEATHER" || h.family === "CORRIDOR") && h.expected_impact_window)
    .slice(0, 3)
    .map((h) => {
      const w = h.expected_impact_window!;
      return { ...bar(parseDate(w.start)!, parseDate(w.end)!), title: h.title, short: hazardCode(h) };
    });
  const policy = hazards
    .filter((h) => (h.family === "POLICY" || h.family === "GEOPOLITICAL") && h.expected_impact_window)
    .slice(0, 2)
    .map((h) => {
      const w = h.expected_impact_window!;
      return { ...bar(parseDate(w.start)!, parseDate(w.end)!), title: h.title, short: hazardCode(h) };
    });
  const deadlines = [
    latest ? { pct: toPct(latest), label: `LATEST SHIPMENT - ${shortDate(tc.latest_shipment_date)}`, color: "#C4747C" } : null,
    lc ? { pct: toPct(lc), label: `LC EXPIRY - ${shortDate(tc.lc_expiry_date)}`, color: "#5F7FD0" } : null,
  ].filter((d): d is { pct: number; label: string; color: string } => Boolean(d));
  const todayPct = today >= rangeStart && today <= rangeEnd ? toPct(today) : null;

  const stepDays = span <= 21 ? 7 : span <= 45 ? 14 : Math.max(7, Math.round(span / 42) * 7);
  const ticks: { pct: number; label: string }[] = [];
  for (let t = new Date(rangeStart); diffDays(t, rangeEnd) >= 0; t = addDays(t, stepDays)) {
    ticks.push({ pct: toPct(t), label: t.toLocaleDateString("en-US", { month: "short", day: "numeric" }) });
  }

  return { voyage, weather, policy, deadlines, todayPct, ticks };
}

function voyageLabel(tc: TradeCase) {
  const pol = abbr(tc.port_of_loading);
  const pod = abbr(tc.port_of_discharge);
  return `${pol} -> ${pod}`;
}

function hazardCode(h: Hazard): string {
  const tag = FAMILY_TAG[h.family] ?? "RISK";
  const loc = locAbbr(h.anchor || h.title);
  return loc ? `${tag} - ${loc}` : tag;
}

function hazardLabel(h: Hazard): string {
  const family = FAMILY_LABEL[h.family] ?? "Risk";
  const anchor = readableAnchor(h.anchor || h.title);
  return anchor ? `${family} - ${anchor}` : family;
}

function hazardMini(h: Hazard): string {
  return h.title.replace(/^(High|Watch) weather risk near /i, "").replace(/^Typhoon /i, "");
}

function locAbbr(text?: string): string {
  if (!text) return "";
  const cleaned = text.replace(/[^a-zA-Z\s]/g, " ").trim();
  const words = cleaned.split(/\s+/).filter(Boolean);
  if (words.length === 0) return "";
  if (words.length >= 2) return words.slice(0, 3).map((w) => w[0].toUpperCase()).join("");
  return words[0].slice(0, 3).toUpperCase();
}

function readableAnchor(text?: string): string {
  if (!text) return "";
  const raw = text.trim();
  const direct = ANCHOR_LABEL[raw.toUpperCase()];
  if (direct) return direct;
  const cleaned = raw.replace(/[_-]+/g, " ").replace(/\s+/g, " ").trim();
  if (!cleaned) return "";
  if (cleaned.length <= 4 && cleaned === cleaned.toUpperCase()) return cleaned;
  return cleaned.replace(/\b\w/g, (c) => c.toUpperCase());
}

function impactWindowLabel(h: Hazard): string {
  const w = h.expected_impact_window;
  if (w) return `${shortDate(w.start)}-${shortDate(w.end)}`;
  if (h.lead_days != null) return `${h.lead_days}d lead`;
  return "Route watch";
}

function abbr(text?: string): string {
  if (!text) return "-";
  return text.length > 10 ? text.slice(0, 9) : text;
}

function actionSub(a: RecommendedAction): string {
  const when = a.deadline_date ? relativeDeadline(a.deadline_date) : a.deadline || "";
  return `${when}${a.owner_role ? ` - ${a.owner_role}` : ""}`;
}

function relativeDeadline(iso: string): string {
  const d = daysFromToday(iso);
  if (d === 0) return "Due today";
  if (d === 1) return "Due tomorrow";
  if (d < 0) return `Overdue ${Math.abs(d)}d`;
  return `Due ${shortDate(iso)}`;
}

function statusLabel(s: string): string {
  return (s || "").replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function destLabel(tc: TradeCase): string {
  const pod = tc.port_of_discharge || "";
  const fin = tc.final_destination || "";
  return fin && fin !== pod ? `${pod} -> ${fin}` : pod || "TBD";
}

function originCode(tc: TradeCase): string {
  return (tc.port_of_loading || "").length ? "" : "";
}

function destCode(_tc: TradeCase): string {
  return "";
}

function amountLabel(tc: TradeCase): string {
  const amt = (tc as unknown as { amount?: number }).amount;
  const cur = (tc as unknown as { currency?: string }).currency;
  if (amt == null) return "-";
  return `${cur ? cur + " " : ""}${Number(amt).toLocaleString()}`;
}

function shortDate(value?: string): string {
  if (!value) return "TBD";
  const d = parseDate(value);
  if (!d) return value;
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function parseDate(value?: string | null): Date | null {
  if (!value) return null;
  const d = new Date(`${String(value).slice(0, 10)}T00:00:00`);
  return isNaN(d.getTime()) ? null : d;
}

function daysFromToday(iso: string): number {
  const target = parseDate(iso);
  if (!target) return 0;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return Math.round((target.getTime() - today.getTime()) / 86400000);
}

function addDays(d: Date, n: number): Date {
  const x = new Date(d);
  x.setDate(x.getDate() + n);
  return x;
}

function diffDays(a: Date, b: Date): number {
  return Math.round((b.getTime() - a.getTime()) / 86400000);
}

function clamp(v: number): number {
  return Math.min(100, Math.max(0, v));
}
