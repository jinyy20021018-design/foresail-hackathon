import L, { type LatLngExpression } from "leaflet";
import "leaflet/dist/leaflet.css";
import { useEffect, useRef } from "react";
import type { RouteMapPayload, TradeCase } from "../api/client";

type Props = {
  routeMap: RouteMapPayload | null;
  tradeCase: TradeCase;
};

/**
 * Real geographic route map (CARTO dark basemap + full overlay stack:
 * route legs, ports, external events, typhoon cones, corridor states,
 * vessel position). Receives the already-fetched routeMap payload so it
 * shares RouteChart's single /route-map request. Rendered as the "Map"
 * segment of the Route Risk Deck; remounts on segment switch.
 */
export function RouteLeafletMap({ routeMap, tradeCase }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const sellerView = (tradeCase.trade_perspective ?? "SELLER").toUpperCase() !== "BUYER";
  const loadingPort = tradeCase.port_of_loading || "Port of loading";
  const dischargePort = tradeCase.port_of_discharge || tradeCase.final_destination || "Port of discharge";
  const deadline = tradeCase.latest_shipment_date || "contract deadline";

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
    L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}{r}.png", {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
      subdomains: "abcd",
      maxZoom: 19,
    }).addTo(map);
    const placeLabels = L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_only_labels/{z}/{x}/{y}{r}.png", {
      subdomains: "abcd",
      maxZoom: 19,
    });
    const applyZoomDensity = () => {
      const zoom = map.getZoom();
      const container = map.getContainer();
      container.classList.toggle("zoom-far", zoom < 5);
      if (zoom >= 5) {
        if (!map.hasLayer(placeLabels)) placeLabels.addTo(map);
      } else if (map.hasLayer(placeLabels)) {
        map.removeLayer(placeLabels);
      }
    };
    map.on("zoomend", applyZoomDensity);

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
    const primaryThreatId = routeMap.threat_summary.primary_threat?.event_id;
    routeMap.map_events.forEach((event) => {
      const coordinates: LatLngExpression = [event.lat, event.lng];
      boundsPoints.push(coordinates);
      const isPrimary = event.event_id === primaryThreatId;
      addEventMarker(
        map,
        coordinates,
        truncateLabel(event.title),
        event.classification === "Relevant" ? "right" : "left",
        event.classification === "Relevant" ? [10, 0] : [-10, 0],
        event.classification,
        isPrimary,
        `<b>${event.classification}</b> · ${event.event_type ?? "event"}<br/>${event.title}`,
      );
    });

    (routeMap.typhoon_tracks ?? []).forEach((track) => {
      const trackLine: LatLngExpression[] = track.points.map((point) => [point.lat, point.lng]);
      L.polyline(trackLine, { color: "#ef4444", weight: 2, opacity: 0.85, dashArray: "6 6" }).addTo(map);
      track.points.forEach((point, index) => {
        L.circle([point.lat, point.lng], {
          radius: point.cone_radius_km * 1000,
          color: "#ef4444",
          weight: 1,
          opacity: 0.35,
          fillColor: "#ef4444",
          fillOpacity: 0.07,
          className: `typhoon-cone${index % 2 === 1 ? " cone-skip" : ""}`,
        }).addTo(map);
      });
      const head = track.points[0];
      if (head) {
        const lastPoint = track.points[track.points.length - 1];
        L.marker([head.lat, head.lng], { icon: L.divIcon({ className: "typhoon-marker", html: "🌀", iconSize: [20, 20], iconAnchor: [10, 10] }) })
          .addTo(map)
          .bindTooltip(`${track.name} · forecast track`, { direction: "right", className: "route-event-label", offset: [12, 0] })
          .bindPopup(
            `<b>Typhoon ${track.name}</b><br/>Forecast ${track.points.length} positions, max wind ${Math.max(...track.points.map((point) => point.max_wind_kt))} kt<br/>` +
            `Track ${head.time.slice(0, 10)} → ${lastPoint.time.slice(0, 10)}; uncertainty cone grows with lead time.`,
          );
      }
    });

    (routeMap.corridors_on_route ?? []).forEach((corridor) => {
      const color = corridor.state === "RED" ? "#ef4444" : corridor.state === "AMBER" ? "#f59e0b" : "#34d399";
      const trendArrow = corridor.trend === "UP" ? " ↑" : corridor.trend === "DOWN" ? " ↓" : "";
      L.circleMarker([corridor.lat, corridor.lng], { radius: 7, color, weight: 2, fillColor: color, fillOpacity: 0.35, className: `corridor-marker corridor-${corridor.state.toLowerCase()}` })
        .addTo(map)
        .bindTooltip(`${corridor.name}: ${corridor.state}${trendArrow}`, { direction: "top", className: "route-map-label", offset: [0, -8] })
        .bindPopup(
          `<b>${corridor.name}</b> · ${corridor.state}${trendArrow}` +
          (corridor.capacity_notes ? `<br/>${corridor.capacity_notes}` : ""),
        );
    });

    const vessel = routeMap.vessel_position;
    if (vessel) {
      L.marker([vessel.lat, vessel.lng], { icon: L.divIcon({ className: "vessel-marker", html: "🚢", iconSize: [22, 22], iconAnchor: [11, 11] }) })
        .addTo(map)
        .bindTooltip(`Vessel (est.) · ${vessel.date} · ${vessel.region}`, { permanent: true, direction: "top", className: "route-map-label", offset: [0, -12] });
      boundsPoints.push([vessel.lat, vessel.lng]);
    }

    map.fitBounds(L.latLngBounds(boundsPoints), { padding: [40, 40] });
    L.control.scale({ imperial: false, position: "bottomleft" }).addTo(map);
    applyZoomDensity();
    window.setTimeout(() => map.invalidateSize(), 0);

    return () => {
      map.remove();
    };
  }, [deadline, dischargePort, loadingPort, routeMap, sellerView]);

  return (
    <div
      ref={containerRef}
      className="route-map rc-leaflet"
      role="img"
      aria-label={`Interactive trade route map from ${loadingPort} to ${dischargePort}`}
    />
  );
}

function addEventMarker(
  map: L.Map,
  coordinates: LatLngExpression,
  label: string,
  direction: "left" | "right",
  offset: [number, number],
  classification: string,
  isPrimary = false,
  popupHtml?: string,
) {
  const color = classification === "Relevant" ? "#ef4444" : "#f59e0b";
  const marker = L.circleMarker(coordinates, { radius: 6, color, weight: 1.5, fillColor: color, fillOpacity: 0.16, className: "map-event-marker" })
    .addTo(map)
    .bindTooltip(label, { permanent: isPrimary, direction, className: "route-event-label", offset });
  if (popupHtml) {
    marker.bindPopup(popupHtml);
  }
}

function truncateLabel(text: string, max = 44) {
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}

function shortDate(value: string) {
  const parts = value.split("-");
  return parts.length === 3 ? `${parts[1]}-${parts[2]}` : value;
}
