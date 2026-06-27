import L, { type LatLngExpression } from "leaflet";
import "leaflet/dist/leaflet.css";
import { useEffect, useRef, useState, type ReactNode } from "react";
import type { TradeCase } from "../api/client";
import { getMaritimeRoute } from "../data/maritimeRoutes";

export function RouteRiskMap({ tradeCase }: { tradeCase: TradeCase }) {
  const [seat, setSeat] = useState<"seller" | "buyer">("seller");
  const sellerView = seat === "seller";
  const loadingPort = tradeCase.port_of_loading || "Port of loading";
  const dischargePort = tradeCase.port_of_discharge || tradeCase.final_destination || "Port of discharge";
  const deadline = tradeCase.latest_shipment_date || "contract deadline";
  const incoterm = (tradeCase.incoterm || "CIF").toUpperCase();

  return (
    <>
      <section className="route-risk-section" aria-label="Route risk and CIF liability allocation">
        <div className="map-pane">
          <div className="map-heading">
            <div><h2>Route Risk Map</h2><p>{sellerView ? "Seller view · cargo risk sits with buyer; you carry loading and document risk" : "Buyer view · main-voyage cargo loss is yours from loading"}</p></div>
            <div className="seat-toggle" aria-label="View allocation by party">
              <button type="button" className={sellerView ? "active" : ""} onClick={() => setSeat("seller")}>Seller</button>
              <button type="button" className={!sellerView ? "active" : ""} onClick={() => setSeat("buyer")}>Buyer</button>
            </div>
          </div>
          <LiveRouteMap loadingPort={loadingPort} dischargePort={dischargePort} deadline={deadline} sellerView={sellerView} />
          <div className="map-legend"><span><i className="solid-line"/>Your risk leg</span><span><i className="dashed-line"/>Counterparty leg</span><span><i className="transfer-symbol"/>Incoterm transfer</span><span><i className="event-symbol"/>External event</span></div>
        </div>
        <div className="liability-pane">
          <div><span className="eyebrow">INCOTERMS® 2020</span><h2>Liability Allocation · {incoterm}</h2></div>
          <AllocationLane label="Risk"><b style={{ flex: .13 }}>Seller</b><span style={{ flex: .87 }}>Buyer, from loading</span></AllocationLane>
          <AllocationLane label="Cost"><b style={{ flex: 1 }}>Seller pays freight + insurance to destination</b></AllocationLane>
          <p className="lane-label">Obligations</p>
          <div className="obligation-list"><span>✓ Seller books carriage</span><span>✓ Seller arranges insurance</span><span>✓ Seller presents documents</span><span className="muted-obligation">Buyer clears and collects</span></div>
          <div className="threat-note"><strong>Active threat</strong><p>Typhoon at {loadingPort} threatens loading by {shortDate(deadline)}.</p><b>{sellerView ? "Your payment risk as Seller" : "Your cargo risk as Buyer"}</b></div>
        </div>
      </section>
      <section className="interpretation-panel">
        <Insight title="Interpretation" tone="blue">{sellerView ? `${incoterm}: risk passes to the buyer at loading. Your seller exposure is on-time shipment and clean documents.` : `Under ${incoterm}, main-voyage cargo risk reaches you at loading. Confirm that contract insurance is sufficient.`}</Insight>
        <Insight title="Primary Threat" tone="amber">Typhoon delay at the port of loading.</Insight>
        <Insight title="Business Impact" tone="red">May miss {shortDate(deadline)}, creating LC extension or payment refusal risk.</Insight>
      </section>
    </>
  );
}

const PORT_COORDINATES: Record<string, LatLngExpression> = {
  shanghai: [31.2304, 121.4737],
  chittagong: [22.3569, 91.7832],
  chattogram: [22.3569, 91.7832],
  dhaka: [23.8103, 90.4125],
  ningbo: [29.8683, 121.544],
  qingdao: [36.0671, 120.3826],
  shenzhen: [22.5431, 114.0579],
  surabaya: [-7.2575, 112.7521],
  rotterdam: [51.9244, 4.4777],
  "long beach": [33.7701, -118.1937],
};

function LiveRouteMap({ loadingPort, dischargePort, deadline, sellerView }: { loadingPort: string; dischargePort: string; deadline: string; sellerView: boolean }) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const start = findCoordinates(loadingPort) || PORT_COORDINATES.shanghai;
    const end = findCoordinates(dischargePort) || PORT_COORDINATES.chittagong;
    const startLatLng = L.latLng(start);
    const endLatLng = L.latLng(end);
    const plannedRoute = getMaritimeRoute(loadingPort, dischargePort);
    const route: LatLngExpression[] = plannedRoute?.coordinates || [start, end];

    const map = L.map(containerRef.current, { attributionControl: true, scrollWheelZoom: false, zoomControl: true, minZoom: 2 });
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      maxZoom: 19,
    }).addTo(map);

    L.polyline(route, {
      color: sellerView ? "#91a5ca" : "#5b8cff",
      weight: 3,
      opacity: .92,
      dashArray: sellerView ? "3 9" : undefined,
      lineCap: "round",
    }).addTo(map);

    const portStyle = { radius: 4, color: "#dbe7ff", weight: 1.5, fillColor: "#ffffff", fillOpacity: 1 };
    L.circleMarker(end, portStyle).addTo(map).bindTooltip(dischargePort, { permanent: true, direction: "bottom", className: "route-map-label", offset: [0, 9] });
    L.marker(start, { icon: L.divIcon({ className: "transfer-marker", html: "", iconSize: [10, 10], iconAnchor: [5, 5] }) })
      .addTo(map)
      .bindTooltip(loadingPort, { permanent: true, direction: "bottom", className: "route-map-label", offset: [0, 10] });

    const riskText = sellerView ? `Load by ${shortDate(deadline)} · payment risk` : "Risk transfers at loading";
    L.tooltip({ permanent: true, direction: "left", className: "route-risk-label", offset: [-12, 0] }).setLatLng(start).setContent(riskText).addTo(map);

    const typhoon: LatLngExpression = [26.8, startLatLng.lng + 4.7];
    const strike: LatLngExpression = [endLatLng.lat + 1.4, endLatLng.lng - 1.1];
    addEventMarker(map, typhoon, "Typhoon", "right", [10, 0]);
    addEventMarker(map, strike, "Port strike", "left", [-10, 0]);
    map.fitBounds(L.latLngBounds([...route, typhoon, strike]), { padding: [40, 40] });
    L.control.scale({ imperial: false, position: "bottomleft" }).addTo(map);
    window.setTimeout(() => map.invalidateSize(), 0);

    return () => { map.remove(); };
  }, [deadline, dischargePort, loadingPort, sellerView]);

  return <div ref={containerRef} className="route-map" role="img" aria-label={`Interactive trade route map from ${loadingPort} to ${dischargePort}`} />;
}

function addEventMarker(map: L.Map, coordinates: LatLngExpression, label: string, direction: "left" | "right", offset: [number, number]) {
  L.circleMarker(coordinates, { radius: 6, color: "#f59e0b", weight: 1.5, fillColor: "#f59e0b", fillOpacity: .16, className: "map-event-marker" })
    .addTo(map)
    .bindTooltip(label, { permanent: true, direction, className: "route-event-label", offset });
}

function findCoordinates(port: string) {
  const normalized = port.trim().toLowerCase();
  const match = Object.entries(PORT_COORDINATES).find(([name]) => normalized.includes(name));
  return match?.[1];
}

function AllocationLane({ label, children }: { label: string; children: ReactNode }) { return <div><p className="lane-label">{label}</p><div className="allocation-lane">{children}</div></div>; }
function Insight({ title, tone, children }: { title: string; tone: string; children: ReactNode }) { return <div className="insight"><span className={`insight-icon ${tone}`}>{title.slice(0, 1)}</span><div><h3>{title}</h3><p>{children}</p></div></div>; }
function shortDate(value: string) { const parts = value.split("-"); return parts.length === 3 ? `${parts[1]}-${parts[2]}` : value; }
