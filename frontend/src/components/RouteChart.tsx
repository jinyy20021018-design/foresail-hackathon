import { useEffect, useMemo, useState, type ReactNode } from "react";
import { api, type RouteMapPayload, type TradeCase } from "../api/client";
import { RouteLeafletMap } from "./RouteLeafletMap";

type Props = {
  caseId: string;
  tradeCase: TradeCase;
  refreshKey?: string;
  children?: ReactNode;
};

type Pt = { x: number; y: number };
type GeoPt = { lat: number; lng: number };

const W = 760;
const H = 456;
const PAD = 58;

export function RouteChart({ caseId, tradeCase, refreshKey = "", children }: Props) {
  const [routeMap, setRouteMap] = useState<RouteMapPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [view, setView] = useState<"map" | "legs" | "weather">("map");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    api
      .getRouteMap(caseId)
      .then((payload) => {
        if (!cancelled) setRouteMap(payload);
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed to load route geometry.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [caseId, refreshKey]);

  const model = useMemo(() => buildModel(routeMap), [routeMap]);
  const seasonal = routeMap?.seasonal_baseline ?? [];

  return (
    <div className="rc-panel">
      <div className="rc-head">
        <div className="rc-title">
          <span className="rc-title-ic" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none">
              <path d="M12 21s-7-5.5-7-11a7 7 0 0 1 14 0c0 5.5-7 11-7 11Z" />
              <circle cx="12" cy="10" r="2.5" />
            </svg>
          </span>
          <h2>Route Risk Deck</h2>
        </div>
        <div className="rc-seg" role="tablist">
          {(["map", "legs", "weather"] as const).map((v) => (
            <button key={v} type="button" className={view === v ? "on" : ""} onClick={() => setView(v)}>
              {v === "map" ? "Map" : v === "legs" ? "Legs" : "Weather"}
            </button>
          ))}
        </div>
      </div>

      <div className={`rc-stage${view === "map" ? " rc-stage-map" : ""}`}>
        {loading && <div className="rc-empty">Plotting voyage…</div>}
        {error && !loading && <div className="rc-empty rc-empty-err">{error}</div>}
        {!loading && !error && view === "map" && <RouteLeafletMap routeMap={routeMap} tradeCase={tradeCase} />}
        {!loading && !error && view !== "map" && model && (
          <svg viewBox={`0 0 ${W} ${H}`} className="rc-svg" role="img" aria-label={`Voyage chart from ${model.origin.display_name} to ${model.dest.display_name}`}>
            <defs>
              <linearGradient id="rcSeaDepth" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#5F7FD0" stopOpacity="0.16" />
                <stop offset="55%" stopColor="#5F7FD0" stopOpacity="0.06" />
                <stop offset="100%" stopColor="#5F7FD0" stopOpacity="0.02" />
              </linearGradient>
              <radialGradient id="rcSeaGlow" cx="70%" cy="15%" r="72%">
                <stop offset="0%" stopColor="#8AA6EC" stopOpacity="0.20" />
                <stop offset="60%" stopColor="#8AA6EC" stopOpacity="0" />
              </radialGradient>
              <radialGradient id="rcSeaGlow2" cx="20%" cy="88%" r="64%">
                <stop offset="0%" stopColor="#5F7FD0" stopOpacity="0.11" />
                <stop offset="62%" stopColor="#5F7FD0" stopOpacity="0" />
              </radialGradient>
              <linearGradient id="rcRouteGrad" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0%" stopColor="#7C9BE6" />
                <stop offset="100%" stopColor="#5F7FD0" />
              </linearGradient>
            </defs>

            {/* soft blue sea depth (cutout glass field) */}
            <rect x="0" y="0" width={W} height={H} fill="url(#rcSeaDepth)" />
            <rect x="0" y="0" width={W} height={H} fill="url(#rcSeaGlow)" />
            <rect x="0" y="0" width={W} height={H} fill="url(#rcSeaGlow2)" />

            {/* faint lat/lng grid */}
            <g className="rc-grid">
              {[0.25, 0.5, 0.75].map((f) => (
                <line key={`h${f}`} x1={0} x2={W} y1={H * f} y2={H * f} />
              ))}
              {[0.25, 0.5, 0.75].map((f) => (
                <line key={`v${f}`} y1={0} y2={H} x1={W * f} x2={W * f} />
              ))}
            </g>

            {/* inland dashed link */}
            {model.finalPt && (
              <path
                className="rc-inland"
                d={`M ${model.destPt.x} ${model.destPt.y} L ${model.finalPt.x} ${model.finalPt.y}`}
              />
            )}

            {/* route glow + base + flowing dots */}
            <path className="rc-route-glow" d={model.routeD} />
            <path className="rc-route-base" d={model.routeD} />
            <path className="rc-route-flow" d={model.routeD} />

            {/* typhoons */}
            {model.typhoonShapes.map((tc) => (
              <g key={tc.name} className="rc-tc">
                <g className="rc-tc-cones">
                  {tc.pts.map((p, i) => (
                    <circle key={i} className="rc-cone" cx={p.x} cy={p.y} r={p.r} />
                  ))}
                </g>
                <path className="rc-tc-track" d={tc.trackD} />
                {tc.head && (
                  <>
                    <circle className="rc-tc-ripple" cx={tc.head.x} cy={tc.head.y} r={6} />
                    <circle className="rc-tc-eye" cx={tc.head.x} cy={tc.head.y} r={5} />
                    <g transform={`translate(${clampX(tc.head.x + 12)} ${tc.head.y})`}>
                      <rect className="rc-chip-bg rc-chip-red" x={0} y={-9} rx={7} width={130} height={18} />
                      <text className="rc-chip-tx rc-chip-tx-red" x={9} y={3.5}>
                        {tc.name.replace(" (simulated)", "")} · {tc.maxWind} kt
                      </text>
                    </g>
                  </>
                )}
              </g>
            ))}

            {/* ports */}
            <PortNode pt={model.originPt} label={model.origin.display_name} sub={`POL · ETD ${shortDate(tradeCase.etd)}`} anchor="up" transfer />
            <PortNode pt={model.destPt} label={model.dest.display_name} sub={`POD · ETA ${shortDate(tradeCase.eta)}`} anchor="down" />
            {model.finalPt && model.finalDest && (
              <PortNode pt={model.finalPt} label={model.finalDest.display_name} sub="Final · inland" anchor="up" muted />
            )}

            {/* vessel */}
            {model.vesselPt && (
              <g className="rc-vessel">
                <circle className="rc-vessel-halo" cx={model.vesselPt.x} cy={model.vesselPt.y} r={9} />
                <circle className="rc-vessel-dot" cx={model.vesselPt.x} cy={model.vesselPt.y} r={6} />
                <path
                  d={`M ${model.vesselPt.x - 2.4} ${model.vesselPt.y - 1} L ${model.vesselPt.x + 3} ${model.vesselPt.y + 1} L ${model.vesselPt.x - 1.4} ${model.vesselPt.y + 2.6} Z`}
                  fill="#fff"
                />
                <text className="rc-vessel-tx" x={model.vesselPt.x - 12} y={model.vesselPt.y + 20} textAnchor="middle">
                  VESSEL · TODAY
                </text>
              </g>
            )}
          </svg>
        )}
      </div>

      <div className="rc-legend">
        <span><i className="rc-lg-route" />Course</span>
        <span><i className="rc-lg-tc" />Typhoon cone</span>
        <span><i className="rc-lg-vessel" />Vessel (est.)</span>
        <span><i className="rc-lg-transfer" />CIF transfer</span>
        {seasonal.length > 0 && (
          <span className="rc-lg-season">
            Seasonal: {seasonal.slice(0, 2).map((s) => `${s.region} ${s.level}`).join(" · ")}
          </span>
        )}
      </div>
      {children}
    </div>
  );
}

function PortNode({
  pt,
  label,
  sub,
  anchor,
  transfer = false,
  muted = false,
}: {
  pt: Pt;
  label: string;
  sub: string;
  anchor: "up" | "down";
  transfer?: boolean;
  muted?: boolean;
}) {
  const pillW = Math.max(58, label.length * 7.2 + 18);
  const pillY = anchor === "up" ? pt.y - 30 : pt.y + 12;
  const subY = anchor === "up" ? pt.y - 40 : pt.y + 42;
  return (
    <g className={`rc-port${muted ? " rc-port-muted" : ""}`}>
      {transfer && (
        <g transform={`translate(${pt.x} ${pt.y})`}>
          <rect className="rc-transfer" x={-5} y={-5} width={10} height={10} rx={2} transform="rotate(45)" />
        </g>
      )}
      <circle className="rc-port-dot" cx={pt.x} cy={pt.y} r={4.5} />
      <g transform={`translate(${clampPill(pt.x, pillW)} ${pillY})`}>
        <rect className="rc-port-pill" x={0} y={0} rx={9} width={pillW} height={20} />
        <text className="rc-port-tx" x={pillW / 2} y={14} textAnchor="middle">{label}</text>
      </g>
      <text className="rc-port-sub" x={pt.x} y={subY} textAnchor="middle">{sub}</text>
    </g>
  );
}

function buildModel(rm: RouteMapPayload | null) {
  if (!rm) return null;
  const coords: GeoPt[] = (rm.geometry.coordinates || []).map(([lat, lng]) => ({ lat, lng }));
  if (coords.length < 2) return null;
  const origin = rm.geometry.origin;
  const dest = rm.geometry.destination;
  const finalDest = rm.geometry.final_destination;
  const vessel = rm.vessel_position ?? null;
  const typhoons = rm.typhoon_tracks ?? [];

  const allGeo: GeoPt[] = [...coords];
  if (vessel) allGeo.push({ lat: vessel.lat, lng: vessel.lng });
  typhoons.forEach((t) => t.points.forEach((p) => allGeo.push({ lat: p.lat, lng: p.lng })));
  if (finalDest?.lat != null && finalDest?.lng != null) allGeo.push({ lat: finalDest.lat, lng: finalDest.lng });

  const lats = allGeo.map((p) => p.lat);
  const lngs = allGeo.map((p) => p.lng);
  const latMin = Math.min(...lats);
  const latMax = Math.max(...lats);
  const lngMin = Math.min(...lngs);
  const lngMax = Math.max(...lngs);
  const latSpan = latMax - latMin || 1;
  const lngSpan = lngMax - lngMin || 1;

  const project = (lat: number, lng: number): Pt => ({
    x: PAD + ((lng - lngMin) / lngSpan) * (W - 2 * PAD),
    y: PAD + (1 - (lat - latMin) / latSpan) * (H - 2 * PAD),
  });

  const midLat = (latMin + latMax) / 2;
  const kmPerLng = 111.32 * Math.cos((midLat * Math.PI) / 180);
  const pxPerKm = (W - 2 * PAD) / (lngSpan * kmPerLng) || 0.02;

  const routePts = coords.map((c) => project(c.lat, c.lng));
  const routeD = smoothPath(routePts);

  const originPt = origin.lat != null ? project(origin.lat, origin.lng as number) : routePts[0];
  const destPt = dest.lat != null ? project(dest.lat, dest.lng as number) : routePts[routePts.length - 1];
  const finalPt = finalDest?.lat != null ? project(finalDest.lat, finalDest.lng as number) : null;
  const vesselPt = vessel ? project(vessel.lat, vessel.lng) : null;

  const typhoonShapes = typhoons.map((t) => {
    const pts = t.points.map((p) => ({
      ...project(p.lat, p.lng),
      r: Math.max(7, p.cone_radius_km * pxPerKm),
    }));
    const trackD = pts.map((p, i) => `${i === 0 ? "M" : "L"} ${p.x} ${p.y}`).join(" ");
    const maxWind = Math.max(...t.points.map((p) => p.max_wind_kt));
    return { name: t.name, pts, trackD, maxWind, head: pts[0] };
  });

  return { routeD, routePts, originPt, destPt, finalPt, vesselPt, typhoonShapes, origin, dest, finalDest };
}

function smoothPath(pts: Pt[]) {
  if (pts.length < 2) return "";
  let d = `M ${pts[0].x} ${pts[0].y}`;
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[i - 1] || pts[i];
    const p1 = pts[i];
    const p2 = pts[i + 1];
    const p3 = pts[i + 2] || p2;
    const cp1x = p1.x + (p2.x - p0.x) / 6;
    const cp1y = p1.y + (p2.y - p0.y) / 6;
    const cp2x = p2.x - (p3.x - p1.x) / 6;
    const cp2y = p2.y - (p3.y - p1.y) / 6;
    d += ` C ${cp1x.toFixed(1)} ${cp1y.toFixed(1)}, ${cp2x.toFixed(1)} ${cp2y.toFixed(1)}, ${p2.x.toFixed(1)} ${p2.y.toFixed(1)}`;
  }
  return d;
}

function clampX(x: number) {
  return Math.min(W - 140, Math.max(6, x));
}
function clampPill(x: number, pillW: number) {
  return Math.min(W - pillW - 6, Math.max(6, x - pillW / 2));
}
function shortDate(value?: string) {
  if (!value) return "TBD";
  const parts = value.slice(0, 10).split("-");
  return parts.length === 3 ? `${parts[1]}-${parts[2]}` : value;
}
