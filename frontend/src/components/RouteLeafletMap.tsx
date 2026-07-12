import L, { type LatLngExpression } from "leaflet";
import "leaflet/dist/leaflet.css";
import { useEffect, useRef, useState } from "react";
import type { Hazard, RouteMapPayload, TradeCase } from "../api/client";

type Props = {
  routeMap: RouteMapPayload | null;
  tradeCase: TradeCase;
  selectedHazard?: Hazard | null;
  focusRequest?: number;
};

type LayerIndexes = {
  events: Map<string, L.CircleMarker>;
  corridors: Map<string, L.CircleMarker>;
  typhoons: Map<string, L.Marker>;
};

type FocusTarget = {
  latLng: L.LatLng;
  label: string;
};

export function RouteLeafletMap({ routeMap, tradeCase, selectedHazard = null, focusRequest = 0 }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const defaultBoundsRef = useRef<L.LatLngBounds | null>(null);
  const highlightLayerRef = useRef<L.LayerGroup | null>(null);
  const indexesRef = useRef<LayerIndexes>({ events: new Map(), corridors: new Map(), typhoons: new Map() });
  const [noLocationRisk, setNoLocationRisk] = useState<string | null>(null);

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

    const map = L.map(containerRef.current, { attributionControl: true, scrollWheelZoom: false, dragging: true, doubleClickZoom: true, zoomControl: true, minZoom: 2 });
    mapRef.current = map;
    defaultBoundsRef.current = null;
    indexesRef.current = { events: new Map(), corridors: new Map(), typhoons: new Map() };
    highlightLayerRef.current = L.layerGroup().addTo(map);

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

    const riskText = sellerView ? `Load by ${shortDate(deadline)} - payment risk` : "Risk transfers at loading";
    L.tooltip({ permanent: true, direction: "left", className: "route-risk-label", offset: [-12, 0] }).setLatLng(start).setContent(riskText).addTo(map);

    const boundsPoints: LatLngExpression[] = [...route];
    const primaryThreatId = routeMap.threat_summary.primary_threat?.event_id;
    routeMap.map_events.forEach((event) => {
      const coordinates: LatLngExpression = [event.lat, event.lng];
      boundsPoints.push(coordinates);
      const isPrimary = event.event_id === primaryThreatId;
      const marker = addEventMarker(
        map,
        coordinates,
        truncateLabel(event.title),
        event.classification === "Relevant" ? "right" : "left",
        event.classification === "Relevant" ? [10, 0] : [-10, 0],
        event.classification,
        isPrimary,
        `<b>${escapeHtml(event.classification)}</b> - ${escapeHtml(event.event_type ?? "event")}<br/>${escapeHtml(event.title)}`,
      );
      indexesRef.current.events.set(event.event_id, marker);
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
        const marker = L.marker([head.lat, head.lng], { icon: L.divIcon({ className: "typhoon-marker", html: "TC", iconSize: [24, 24], iconAnchor: [12, 12] }) })
          .addTo(map)
          .bindTooltip(`${track.name} - forecast track`, { direction: "right", className: "route-event-label", offset: [12, 0] })
          .bindPopup(
            `<b>Typhoon ${escapeHtml(track.name)}</b><br/>Forecast ${track.points.length} positions, max wind ${Math.max(...track.points.map((point) => point.max_wind_kt))} kt<br/>` +
            `Track ${escapeHtml(head.time.slice(0, 10))} -> ${escapeHtml(lastPoint.time.slice(0, 10))}; uncertainty cone grows with lead time.`,
          );
        if (track.source_event_id) {
          indexesRef.current.typhoons.set(track.source_event_id, marker);
        }
      }
    });

    (routeMap.corridors_on_route ?? []).forEach((corridor) => {
      const color = corridor.state === "RED" ? "#ef4444" : corridor.state === "AMBER" ? "#f59e0b" : "#34d399";
      const trendText = corridor.trend === "UP" ? " up" : corridor.trend === "DOWN" ? " down" : "";
      const marker = L.circleMarker([corridor.lat, corridor.lng], { radius: 7, color, weight: 2, fillColor: color, fillOpacity: 0.35, className: `corridor-marker corridor-${corridor.state.toLowerCase()}` })
        .addTo(map)
        .bindTooltip(`${corridor.name}: ${corridor.state}${trendText}`, { direction: "top", className: "route-map-label", offset: [0, -8] })
        .bindPopup(
          `<b>${escapeHtml(corridor.name)}</b> - ${escapeHtml(corridor.state)}${escapeHtml(trendText)}` +
          (corridor.capacity_notes ? `<br/>${escapeHtml(corridor.capacity_notes)}` : ""),
        );
      indexesRef.current.corridors.set(corridor.corridor_id, marker);
    });

    const vessel = routeMap.vessel_position;
    if (vessel) {
      const vesselLabel =
        vessel.status === "pre_departure"
          ? `Vessel - berthed at ${loadingPort} - ETD ${shortDate(vessel.date)}`
          : vessel.status === "arrived"
          ? `Vessel - arrived ${dischargePort}`
          : `Vessel (est.) - ${shortDate(vessel.date)} - ${vessel.region}`;
      L.marker([vessel.lat, vessel.lng], { icon: L.divIcon({ className: "vessel-marker", html: "V", iconSize: [22, 22], iconAnchor: [11, 11] }) })
        .addTo(map)
        .bindTooltip(vesselLabel, { permanent: true, direction: "top", className: "route-map-label", offset: [0, -12] });
      boundsPoints.push([vessel.lat, vessel.lng]);
    }

    const defaultBounds = L.latLngBounds(boundsPoints);
    defaultBoundsRef.current = defaultBounds;
    map.fitBounds(defaultBounds, { padding: [40, 40] });
    L.control.scale({ imperial: false, position: "bottomleft" }).addTo(map);
    applyZoomDensity();
    window.setTimeout(() => map.invalidateSize(), 0);

    return () => {
      map.remove();
      mapRef.current = null;
      defaultBoundsRef.current = null;
      highlightLayerRef.current = null;
      indexesRef.current = { events: new Map(), corridors: new Map(), typhoons: new Map() };
    };
  }, [deadline, dischargePort, loadingPort, routeMap, sellerView]);

  useEffect(() => {
    const map = mapRef.current;
    const highlightLayer = highlightLayerRef.current;
    if (!map || !routeMap || !highlightLayer) return;

    highlightLayer.clearLayers();
    setNoLocationRisk(null);

    if (!selectedHazard) {
      map.closePopup();
      if (defaultBoundsRef.current) {
        map.fitBounds(defaultBoundsRef.current, { padding: [40, 40], animate: true });
      }
      return;
    }

    const targets = resolveFocusTargets(selectedHazard, routeMap, indexesRef.current);
    if (targets.length === 0) {
      map.closePopup();
      setNoLocationRisk(selectedHazard.title);
      return;
    }

    targets.forEach((target) => {
      L.circleMarker(target.latLng, {
        radius: 16,
        color: "#ffffff",
        weight: 2,
        opacity: 0.95,
        fillColor: "#ef4444",
        fillOpacity: 0.2,
        className: "risk-focus-ring",
      }).addTo(highlightLayer);
      L.circleMarker(target.latLng, {
        radius: 7,
        color: "#ffffff",
        weight: 2,
        opacity: 1,
        fillColor: "#ef4444",
        fillOpacity: 0.9,
        className: "risk-focus-dot",
      }).addTo(highlightLayer);
    });

    if (targets.length === 1) {
      map.flyTo(targets[0].latLng, Math.max(map.getZoom(), 5), { duration: 0.55 });
    } else {
      map.fitBounds(L.latLngBounds(targets.map((target) => target.latLng)), { padding: [70, 70], animate: true });
    }

    L.popup({ className: "risk-map-popup", closeButton: true, autoPan: true })
      .setLatLng(targets[0].latLng)
      .setContent(riskPopupHtml(selectedHazard, targets[0].label))
      .openOn(map);
  }, [focusRequest, routeMap, selectedHazard]);

  return (
    <div className="route-map-shell">
      <div
        ref={containerRef}
        className="route-map rc-leaflet"
        role="img"
        aria-label={`Interactive trade route map from ${loadingPort} to ${dischargePort}`}
      />
      {noLocationRisk && (
        <div className="route-map-notice" role="status">
          This risk affects the route or contract, but has no precise map location.
        </div>
      )}
    </div>
  );
}

function resolveFocusTargets(hazard: Hazard, routeMap: RouteMapPayload, indexes: LayerIndexes): FocusTarget[] {
  const targets: FocusTarget[] = [];
  const seen = new Set<string>();
  const evidenceIds = new Set(hazard.evidence_event_ids ?? []);

  routeMap.map_events.forEach((event) => {
    if (!evidenceIds.has(event.event_id)) return;
    const key = `${event.lat},${event.lng}`;
    if (seen.has(key)) return;
    seen.add(key);
    targets.push({ latLng: L.latLng(event.lat, event.lng), label: event.title });
  });

  evidenceIds.forEach((eventId) => {
    const marker = indexes.typhoons.get(eventId);
    if (!marker) return;
    const latLng = marker.getLatLng();
    const key = `${latLng.lat},${latLng.lng}`;
    if (seen.has(key)) return;
    seen.add(key);
    targets.push({ latLng, label: hazard.title });
  });

  const corridorId = hazard.corridor_state?.corridor_id;
  if (corridorId) {
    const marker = indexes.corridors.get(corridorId);
    if (marker) {
      const latLng = marker.getLatLng();
      const key = `${latLng.lat},${latLng.lng}`;
      if (!seen.has(key)) {
        targets.push({ latLng, label: hazard.title });
      }
    }
  }

  return targets;
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
  return marker;
}

function riskPopupHtml(hazard: Hazard, locationLabel: string) {
  const urgency = (hazard.urgency ?? "MONITOR").replace(/_/g, " ");
  const owner = hazard.attribution?.our_cargo_risk || hazard.attribution?.our_payment_risk ? "Affects you" : "Counterparty exposure";
  const impact = hazard.expected_impact_window ? `${shortDate(hazard.expected_impact_window.start)}-${shortDate(hazard.expected_impact_window.end)}` : "Route watch";
  const posture = hazard.recommended_posture ? `<br/><span>${escapeHtml(hazard.recommended_posture)}</span>` : "";
  return (
    `<div class="risk-popup-content">` +
    `<b>${escapeHtml(hazard.title)}</b>` +
    `<dl>` +
    `<dt>Urgency</dt><dd>${escapeHtml(titleCase(urgency))}</dd>` +
    `<dt>Impact</dt><dd>${escapeHtml(impact)}</dd>` +
    `<dt>Exposure</dt><dd>${escapeHtml(owner)}</dd>` +
    `<dt>Map point</dt><dd>${escapeHtml(locationLabel)}</dd>` +
    `</dl>${posture}</div>`
  );
}

function truncateLabel(text: string, max = 44) {
  return text.length > max ? `${text.slice(0, max - 1)}...` : text;
}

function shortDate(value?: string) {
  if (!value) return "TBD";
  const parts = value.slice(0, 10).split("-");
  return parts.length === 3 ? `${parts[1]}-${parts[2]}` : value;
}

function titleCase(text: string) {
  return text.toLowerCase().replace(/\b\w/g, (char) => char.toUpperCase());
}

function escapeHtml(value: string) {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
