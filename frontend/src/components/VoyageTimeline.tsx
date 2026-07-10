import { useEffect, useMemo, useState } from "react";
import { api, type Hazard, type RouteMapPayload, type TradeCase } from "../api/client";

type Props = {
  caseId: string;
  tradeCase: TradeCase;
  refreshKey?: string;
};

type Segment = { region: string; start: string; end: string };

const URGENCY_COLOR: Record<string, string> = {
  ACT_NOW: "var(--red)",
  PREPARE: "var(--amber)",
  MONITOR: "var(--blue)",
};

export function VoyageTimeline({ caseId, tradeCase, refreshKey = "" }: Props) {
  const [routeMap, setRouteMap] = useState<RouteMapPayload | null>(null);
  const [hazards, setHazards] = useState<Hazard[]>([]);

  useEffect(() => {
    let cancelled = false;
    Promise.allSettled([api.getRouteMap(caseId), api.getHazards(caseId)]).then(([mapResult, hazardResult]) => {
      if (cancelled) return;
      if (mapResult.status === "fulfilled") setRouteMap(mapResult.value);
      if (hazardResult.status === "fulfilled") setHazards(hazardResult.value);
    });
    return () => {
      cancelled = true;
    };
  }, [caseId, refreshKey]);

  const model = useMemo(() => buildModel(routeMap, hazards, tradeCase), [routeMap, hazards, tradeCase]);
  if (!model) return null;
  const { rangeStart, rangeDays, segments, hazardBars, deadlines, todayPct } = model;

  return (
    <section className="panel voyage-timeline" aria-label="Voyage timeline">
      <div className="panel-heading">
        <h2>Voyage Timeline</h2>
        <p>Where the vessel is expected, when threats hit, and when you must act — on one axis.</p>
      </div>
      <div className="timeline-axis">
        {axisTicks(rangeStart, rangeDays).map((tick) => (
          <span key={tick.date} style={{ left: `${tick.pct}%` }}>{tick.label}</span>
        ))}
      </div>
      <div className="timeline-body">
        {todayPct != null && (
          <div className="timeline-today" style={{ left: `calc(110px + (100% - 110px) * ${todayPct} / 100)` }}>
            <i /><b>Today</b>
          </div>
        )}
        <div className="timeline-lane">
          <span className="lane-name">Voyage</span>
          <div className="lane-track">
            {segments.map((segment) => {
              const geometry = barGeometry(segment.start, segment.end, rangeStart, rangeDays);
              return (
                <div
                  key={`${segment.region}-${segment.start}`}
                  className="timeline-bar voyage-bar"
                  style={{ left: `${geometry.left}%`, width: `${geometry.width}%` }}
                  title={`${segment.region}: ${segment.start} – ${segment.end}`}
                >
                  {geometry.width > 9 ? segment.region : ""}
                </div>
              );
            })}
          </div>
        </div>
        {hazardBars.map((bar) => (
          <div className="timeline-lane" key={bar.id}>
            <span className="lane-name">{bar.laneLabel}</span>
            <div className="lane-track">
              <div
                className="timeline-bar hazard-bar"
                style={{ left: `${bar.left}%`, width: `${bar.width}%`, background: bar.color }}
                title={bar.title}
              >
                {bar.width > 12 ? bar.shortTitle : ""}
              </div>
            </div>
          </div>
        ))}
        <div className="timeline-lane">
          <span className="lane-name">Deadlines</span>
          <div className="lane-track">
            {deadlines.map((deadline) => (
              <div key={deadline.label} className="timeline-flag" style={{ left: `${deadline.pct}%` }} title={`${deadline.label}: ${deadline.date}`}>
                <i /><b>{deadline.label}</b>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

function buildModel(routeMap: RouteMapPayload | null, hazards: Hazard[], tradeCase: TradeCase) {
  const positions = routeMap?.voyage_schedule?.positions ?? [];
  const etd = tradeCase.etd || positions[0]?.date;
  const eta = tradeCase.eta || positions[positions.length - 1]?.date;
  if (!etd || !eta) return null;

  const deadlineCandidates = [
    { label: "Latest shipment", date: tradeCase.latest_shipment_date },
    { label: "LC expiry", date: tradeCase.lc_expiry_date },
  ].filter((item): item is { label: string; date: string } => Boolean(item.date));

  const windowDates = hazards
    .map((hazard) => hazard.expected_impact_window)
    .filter((window): window is { start: string; end: string } => Boolean(window))
    .flatMap((window) => [window.start.slice(0, 10), window.end.slice(0, 10)]);

  const allDates = [etd, eta, todayIso(), ...deadlineCandidates.map((item) => item.date), ...windowDates].sort();
  const rangeStart = addDays(allDates[0], -2);
  const rangeEnd = addDays(allDates[allDates.length - 1], 3);
  const rangeDays = Math.max(1, diffDays(rangeStart, rangeEnd));

  const segments: Segment[] = [];
  for (const position of positions) {
    const last = segments[segments.length - 1];
    if (last && last.region === position.region) {
      last.end = position.date;
    } else {
      segments.push({ region: position.region, start: position.date, end: position.date });
    }
  }

  let previousFamily = "";
  const hazardBars = hazards
    .filter((hazard) => hazard.expected_impact_window)
    .slice(0, 5)
    .map((hazard) => {
      const window = hazard.expected_impact_window!;
      const geometry = barGeometry(window.start.slice(0, 10), window.end.slice(0, 10), rangeStart, rangeDays);
      const family = hazard.family.toLowerCase();
      const laneLabel = family === previousFamily ? "" : family;
      previousFamily = family;
      return {
        id: hazard.hazard_id,
        laneLabel,
        left: geometry.left,
        width: Math.max(geometry.width, 1.6),
        color: URGENCY_COLOR[hazard.urgency ?? "MONITOR"] ?? "var(--blue)",
        title: `${hazard.title} (${window.start.slice(0, 10)} – ${window.end.slice(0, 10)})`,
        shortTitle: hazard.title.length > 34 ? `${hazard.title.slice(0, 33)}…` : hazard.title,
      };
    });

  const deadlines = deadlineCandidates.map((item) => ({
    ...item,
    pct: clampPct((diffDays(rangeStart, item.date) / rangeDays) * 100),
  }));

  const todayPct = clampPct((diffDays(rangeStart, todayIso()) / rangeDays) * 100);

  return { rangeStart, rangeDays, segments, hazardBars, deadlines, todayPct };
}

function axisTicks(rangeStart: string, rangeDays: number) {
  const step = rangeDays > 40 ? 10 : rangeDays > 20 ? 5 : rangeDays > 10 ? 3 : 2;
  const ticks = [];
  for (let offset = 0; offset <= rangeDays; offset += step) {
    const date = addDays(rangeStart, offset);
    ticks.push({ date, label: date.slice(5), pct: clampPct((offset / rangeDays) * 100) });
  }
  return ticks;
}

function barGeometry(start: string, end: string, rangeStart: string, rangeDays: number) {
  const left = clampPct((diffDays(rangeStart, start) / rangeDays) * 100);
  const right = clampPct(((diffDays(rangeStart, end) + 1) / rangeDays) * 100);
  return { left, width: Math.max(right - left, 0.8) };
}

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

function addDays(iso: string, days: number) {
  const date = new Date(`${iso.slice(0, 10)}T00:00:00`);
  date.setDate(date.getDate() + days);
  return date.toISOString().slice(0, 10);
}

function diffDays(fromIso: string, toIso: string) {
  return Math.round((new Date(`${toIso.slice(0, 10)}T00:00:00`).getTime() - new Date(`${fromIso.slice(0, 10)}T00:00:00`).getTime()) / 86400000);
}

function clampPct(value: number) {
  return Math.min(100, Math.max(0, value));
}
