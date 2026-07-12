import { useEffect, useState, type ReactNode } from "react";
import { api, type Hazard, type RouteMapPayload, type TradeCase } from "../api/client";
import { RouteLeafletMap } from "./RouteLeafletMap";

type Props = {
  caseId: string;
  tradeCase: TradeCase;
  refreshKey?: string;
  selectedHazard?: Hazard | null;
  focusRequest?: number;
  onClearSelectedHazard?: () => void;
  children?: ReactNode;
};

export function RouteChart({ caseId, tradeCase, refreshKey = "", selectedHazard = null, focusRequest = 0, onClearSelectedHazard, children }: Props) {
  const [routeMap, setRouteMap] = useState<RouteMapPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

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

  const seasonal = routeMap?.seasonal_baseline ?? [];
  const ready = !loading && !error;

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
        {selectedHazard && (
          <button type="button" className="rc-clear-focus" onClick={onClearSelectedHazard}>
            Show full route
          </button>
        )}
      </div>

      <div className={`rc-stage${ready ? " rc-stage-map" : ""}`}>
        {loading && <div className="rc-empty">Plotting voyage…</div>}
        {error && !loading && <div className="rc-empty rc-empty-err">{error}</div>}
        {ready && <RouteLeafletMap routeMap={routeMap} tradeCase={tradeCase} selectedHazard={selectedHazard} focusRequest={focusRequest} />}
      </div>

      <div className="rc-legend">
        <span>
          <i className="rc-lg-route" />
          Course
        </span>
        <span>
          <i className="rc-lg-tc" />
          Typhoon cone
        </span>
        <span>
          <i className="rc-lg-vessel" />
          Vessel (est.)
        </span>
        <span>
          <i className="rc-lg-transfer" />
          CIF transfer
        </span>
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
