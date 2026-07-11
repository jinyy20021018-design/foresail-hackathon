import { useEffect, useMemo, useState } from "react";
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

const URGENCY_META: Record<string, { tag: string; badge: "r" | "a" | "b"; letter: string; glyph: string }> = {
  ACT_NOW: { tag: "act now", badge: "r", letter: "!", glyph: "⚠" },
  PREPARE: { tag: "prepare", badge: "a", letter: "P", glyph: "◐" },
  MONITOR: { tag: "monitor", badge: "b", letter: "M", glyph: "◷" },
};

export function WorkspaceOverview({ caseId, tradeCase, actions, riskSummary, refreshKey = "", onOpenTab }: Props) {
  const [hazards, setHazards] = useState<Hazard[]>([]);

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

  const hazardCards = sortedHazards.slice(0, 4);
  const extraHazards = Math.max(0, sortedHazards.length - 4);

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
    // derived "clear/ok" context flags from case terms
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

  return (
    <div className="fs2-overview">
      {/* hazard card row */}
      <div className="hazrow">
        {hazardCards.length === 0 && (
          <div className="haz" style={{ gridColumn: "1 / -1" }}>
            <div className="top"><span className="code">No active hazards</span><span className="tag">clear</span></div>
            <div className="win"><span>—</span><span className="dotline" /><span className="glyph">✓</span><span className="dotline" /><span className="t2">—</span></div>
            <div className="foot"><span className="mini">Run the monitoring cycle to scan for threats.</span></div>
          </div>
        )}
        {hazardCards.map((h, idx) => {
          const meta = URGENCY_META[h.urgency ?? "MONITOR"] ?? URGENCY_META.MONITOR;
          const w = h.expected_impact_window;
          const ours = Boolean(h.attribution?.our_cargo_risk || h.attribution?.our_payment_risk);
          const isBlack = idx === 0 && h.urgency === "ACT_NOW";
          return (
            <div className={`haz${isBlack ? " black" : ""}`} key={h.hazard_id}>
              <div className="top">
                <span className="code">{hazardCode(h)}</span>
                <span className={`tag${h.urgency === "ACT_NOW" ? " hot" : ""}`}>{meta.tag}</span>
              </div>
              <div className="win">
                <span>{w ? shortDate(w.start) : "—"}</span>
                <span className="dotline" />
                <span className="glyph">{meta.glyph}</span>
                <span className="dotline" />
                <span className="t2">{w ? shortDate(w.end) : (h.lead_days != null ? `${h.lead_days}d` : "—")}</span>
              </div>
              <div className="foot">
                <span className={`badge ${meta.badge}`}>{meta.letter}</span>
                <span className={`who ${ours ? "ours" : "them"}`}>{ours ? "YOUR RISK" : "CPTY"}</span>
              </div>
              <p className="haz-desc" title={h.title}>{hazardMini(h)}</p>
            </div>
          );
        })}
        {extraHazards > 0 && <div className="hazmore" onClick={() => onOpenTab?.("risks")}>+{extraHazards}</div>}
      </div>

      {/* studio grid */}
      <div className="studio">
        {/* left: countdown + tasks */}
        <div className="left">
          <div className="panel count">
            <div className="lbl">Latest shipment · {latestShipment ? shortDate(latestShipment) : "TBD"}</div>
            <div className="num hot">{daysToShipment != null ? daysToShipment : "—"}<small> days</small></div>
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

        {/* center: map + timeline */}
        <div className="panel deckpanel">
          <RouteChart caseId={caseId} tradeCase={tradeCase} refreshKey={refreshKey}>
            <TimelineLanes tradeCase={tradeCase} hazards={hazards} />
          </RouteChart>
        </div>

        {/* right: shipment info + exposure flags */}
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
              <Field label="Incoterm" value={(tradeCase.incoterm || "—").toUpperCase()} note="2020" />
              <Field label="Payment" value={tradeCase.payment_method || "—"} />
            </div>
            <div className="frow">
              <Field label="Amount" value={amountLabel(tradeCase)} />
              <Field label="Cargo" value={tradeCase.commodity || "—"} />
            </div>
            <div className="frow">
              <Field label="ETD" value={shortDate(tradeCase.etd)} />
              <Field label="ETA" value={shortDate(tradeCase.eta)} />
            </div>
            <div className="frow">
              <Field label="Latest shipment" value={latestShipment ? `${shortDate(latestShipment)}${daysToShipment != null ? ` · ${daysToShipment}d` : ""}` : "—"} warn />
              <Field label="LC expiry" value={lcExpiry ? `${shortDate(lcExpiry)}${daysToLc != null ? ` · ${daysToLc}d` : ""}` : "—"} />
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
      {/* vertical alignment grid: date ticks + today + deadline lines, spanning all lanes */}
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

/* ---------- helpers ---------- */

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
  const toPct = (d: Date) => clamp(((diffDays(rangeStart, d)) / span) * 100);
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
    latest ? { pct: toPct(latest), label: `LATEST SHIPMENT · ${shortDate(tc.latest_shipment_date)}`, color: "#C4747C" } : null,
    lc ? { pct: toPct(lc), label: `LC EXPIRY · ${shortDate(tc.lc_expiry_date)}`, color: "#5F7FD0" } : null,
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
  return `${pol} → ${pod}`;
}

function hazardCode(h: Hazard): string {
  const tag = FAMILY_TAG[h.family] ?? "RISK";
  const loc = locAbbr(h.anchor || h.title);
  return loc ? `${tag} · ${loc}` : tag;
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

function abbr(text?: string): string {
  if (!text) return "—";
  return text.length > 10 ? text.slice(0, 9) : text;
}

function actionSub(a: RecommendedAction): string {
  const when = a.deadline_date ? relativeDeadline(a.deadline_date) : a.deadline || "";
  return `${when}${a.owner_role ? ` · ${a.owner_role}` : ""}`;
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
  return fin && fin !== pod ? `${pod} → ${fin}` : pod || "TBD";
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
  if (amt == null) return "—";
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
