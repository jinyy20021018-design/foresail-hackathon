import L, { type LatLngExpression } from "leaflet";
import "leaflet/dist/leaflet.css";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { api, type RouteMapPayload, type TradeCase } from "../api/client";

type Props = {
  caseId: string;
  tradeCase: TradeCase;
  refreshKey?: string;
};

export function RouteRiskMap({ caseId, tradeCase, refreshKey = "" }: Props) {
  const [seat, setSeat] = useState<"seller" | "buyer">("seller");
  const [routeMap, setRouteMap] = useState<RouteMapPayload | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const sellerView = seat === "seller";
  const loadingPort = tradeCase.port_of_loading || "Port of loading";
  const dischargePort = tradeCase.port_of_discharge || tradeCase.final_destination || "Port of discharge";
  const deadline = tradeCase.latest_shipment_date || "contract deadline";
  const incoterm = (tradeCase.incoterm || "CIF").toUpperCase();
  const primaryThreat = routeMap?.threat_summary.primary_threat;
  const neutralMessage = routeMap?.threat_summary.neutral_message;

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    setLoadError(null);
    api.getRouteMap(caseId)
      .then((payload) => {
        if (!cancelled) setRouteMap(payload);
      })
      .catch((error) => {
        if (!cancelled) setLoadError(error instanceof Error ? error.message : "Failed to load route map.");
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [caseId, refreshKey]);

  return (
    <>
      <section className="route-risk-section" aria-label="Route risk and CIF liability allocation">
        <div className="map-pane">
          <div className="map-heading">
            <div>
              <h2>Route Risk Map</h2>
              <p>
                {sellerView
                  ? "Seller view · cargo risk sits with buyer; you carry loading and document risk"
                  : "Buyer view · main-voyage cargo loss is yours from loading"}
              </p>
              {routeMap?.meta.confidence === "estimated" && (
                <p className="map-source-note">Route source: estimated shipping lane heuristic</p>
              )}
              {routeMap?.meta.source === "lane_network" && (
                <p className="map-source-note">Route source: global shipping lane network</p>
              )}
            </div>
            <div className="seat-toggle" aria-label="View allocation by party">
              <button type="button" className={sellerView ? "active" : ""} onClick={() => setSeat("seller")}>Seller</button>
              <button type="button" className={!sellerView ? "active" : ""} onClick={() => setSeat("buyer")}>Buyer</button>
            </div>
          </div>
          {loadError && <div className="warning-banner">{loadError}</div>}
          {routeMap?.meta.warnings.map((warning) => (
            <div key={warning} className="warning-banner">{warning}</div>
          ))}
          {isLoading ? (
            <div className="route-map route-map-loading">Loading route geometry...</div>
          ) : (
            <LiveRouteMap routeMap={routeMap} sellerView={sellerView} deadline={deadline} loadingPort={loadingPort} dischargePort={dischargePort} />
          )}
          <div className="map-legend">
            <span><i className="solid-line" />Your risk leg</span>
            <span><i className="dashed-line" />Counterparty leg</span>
            <span><i className="transfer-symbol" />Incoterm transfer</span>
            <span><i className="event-symbol" />External event</span>
          </div>
        </div>
        <div className="liability-pane">
          <div><span className="eyebrow">INCOTERMS® 2020</span><h2>Liability Allocation · {incoterm}</h2></div>
          <AllocationLane label="Risk"><b style={{ flex: 0.13 }}>Seller</b><span style={{ flex: 0.87 }}>Buyer, from loading</span></AllocationLane>
          <AllocationLane label="Cost"><b style={{ flex: 1 }}>Seller pays freight + insurance to destination</b></AllocationLane>
          <p className="lane-label">Obligations</p>
          <div className="obligation-list">
            <span>✓ Seller books carriage</span>
            <span>✓ Seller arranges insurance</span>
            <span>✓ Seller presents documents</span>
            <span className="muted-obligation">Buyer clears and collects</span>
          </div>
          <div className="threat-note">
            <strong>Active threat</strong>
            {primaryThreat ? (
              <>
                <p>{primaryThreat.title} ({primaryThreat.classification}).</p>
                <b>{sellerView ? "Your payment risk as Seller" : "Your cargo risk as Buyer"}</b>
              </>
            ) : (
              <>
                <p>{neutralMessage ?? "No route-level threats detected for the current monitoring cycle."}</p>
                <b>{sellerView ? "Continue monitoring loading obligations" : "Continue monitoring cargo receipt risk"}</b>
              </>
            )}
          </div>
        </div>
      </section>
      <section className="interpretation-panel">
        <Insight title="Interpretation" tone="blue">
          {sellerView
            ? `${incoterm}: risk passes to the buyer at loading. Your seller exposure is on-time shipment and clean documents.`
            : `Under ${incoterm}, main-voyage cargo risk reaches you at loading. Confirm that contract insurance is sufficient.`}
        </Insight>
        <Insight title="Primary Threat" tone="amber">
          {primaryThreat ? primaryThreat.title : neutralMessage ?? "No primary route threat identified."}
        </Insight>
        <Insight title="Business Impact" tone="red">
          {primaryThreat
            ? `Active ${primaryThreat.classification.toLowerCase()} event may affect shipment timing before ${shortDate(deadline)}.`
            : `No material route threat currently mapped. Next deadline remains ${shortDate(deadline)}.`}
        </Insight>
      </section>
    </>
  );
}

function LiveRouteMap({
  routeMap,
  loadingPort,
  dischargePort,
  deadline,
  sellerView,
}: {
  routeMap: RouteMapPayload | null;
  loadingPort: string;
  dischargePort: string;
  deadline: string;
  sellerView: boolean;
}) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current || !routeMap) return;

    const origin = routeMap.geometry.origin;
    const destination = routeMap.geometry.destination;
    const start: LatLngExpression = origin.lat != null && origin.lng != null ? [origin.lat, origin.lng] : [31.2304, 121.4737];
    const end: LatLngExpression = destination.lat != null && destination.lng != null ? [destination.lat, destination.lng] : [22.3569, 91.7832];
    const seaLeg = routeMap.geometry.legs.find((leg) => leg.type === "sea");
    const inlandLeg = routeMap.geometry.legs.find((leg) => leg.type === "inland");
    const route: LatLngExpression[] = seaLeg?.coordinates?.length ? seaLeg.coordinates : routeMap.geometry.coordinates.length ? routeMap.geometry.coordinates : [start, end];

    const map = L.map(containerRef.current, { attributionControl: true, scrollWheelZoom: false, zoomControl: true, minZoom: 2 });
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      maxZoom: 19,
    }).addTo(map);

    L.polyline(route, {
      color: sellerView ? "#91a5ca" : "#5b8cff",
      weight: 3,
      opacity: 0.92,
      dashArray: sellerView ? "3 9" : undefined,
      lineCap: "round",
    }).addTo(map);

    if (inlandLeg?.coordinates?.length) {
      L.polyline(inlandLeg.coordinates, {
        color: "#dbe7ff",
        weight: 2,
        opacity: 0.85,
        dashArray: "4 6",
        lineCap: "round",
      }).addTo(map);
    }

    const portStyle = { radius: 4, color: "#dbe7ff", weight: 1.5, fillColor: "#ffffff", fillOpacity: 1 };
    L.circleMarker(end, portStyle).addTo(map).bindTooltip(dischargePort, { permanent: true, direction: "bottom", className: "route-map-label", offset: [0, 9] });
    L.marker(start, { icon: L.divIcon({ className: "transfer-marker", html: "", iconSize: [10, 10], iconAnchor: [5, 5] }) })
      .addTo(map)
      .bindTooltip(loadingPort, { permanent: true, direction: "bottom", className: "route-map-label", offset: [0, 10] });

    const riskText = sellerView ? `Load by ${shortDate(deadline)} · payment risk` : "Risk transfers at loading";
    L.tooltip({ permanent: true, direction: "left", className: "route-risk-label", offset: [-12, 0] }).setLatLng(start).setContent(riskText).addTo(map);

    const boundsPoints: LatLngExpression[] = [...route];
    routeMap.map_events.forEach((event) => {
      const coordinates: LatLngExpression = [event.lat, event.lng];
      boundsPoints.push(coordinates);
      addEventMarker(map, coordinates, event.title, event.classification === "Relevant" ? "right" : "left", event.classification === "Relevant" ? [10, 0] : [-10, 0], event.classification);
    });

    map.fitBounds(L.latLngBounds(boundsPoints), { padding: [40, 40] });
    L.control.scale({ imperial: false, position: "bottomleft" }).addTo(map);
    window.setTimeout(() => map.invalidateSize(), 0);

    return () => {
      map.remove();
    };
  }, [deadline, dischargePort, loadingPort, routeMap, sellerView]);

  return <div ref={containerRef} className="route-map" role="img" aria-label={`Interactive trade route map from ${loadingPort} to ${dischargePort}`} />;
}

function addEventMarker(
  map: L.Map,
  coordinates: LatLngExpression,
  label: string,
  direction: "left" | "right",
  offset: [number, number],
  classification: string,
) {
  const color = classification === "Relevant" ? "#ef4444" : "#f59e0b";
  L.circleMarker(coordinates, { radius: 6, color, weight: 1.5, fillColor: color, fillOpacity: 0.16, className: "map-event-marker" })
    .addTo(map)
    .bindTooltip(label, { permanent: true, direction, className: "route-event-label", offset });
}

function AllocationLane({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <p className="lane-label">{label}</p>
      <div className="allocation-lane">{children}</div>
    </div>
  );
}

function Insight({ title, tone, children }: { title: string; tone: string; children: ReactNode }) {
  return (
    <div className="insight">
      <span className={`insight-icon ${tone}`}>{title.slice(0, 1)}</span>
      <div><h3>{title}</h3><p>{children}</p></div>
    </div>
  );
}

function shortDate(value: string) {
  const parts = value.split("-");
  return parts.length === 3 ? `${parts[1]}-${parts[2]}` : value;
}
