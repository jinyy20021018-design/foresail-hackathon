import { useState } from "react";
import { api, type EventConfig, type ExternalEvent, type ExternalEventQuery, type ExternalEventSearchResult } from "../api/client";

type Props = { caseId: string; config: EventConfig | null; events: ExternalEvent[]; hasConfirmedFacts: boolean; highOpenConflictsCount: number; onEventsChange: (events: ExternalEvent[]) => void; onError: (message: string | null) => void };

export function ExternalEventsPanel({ caseId, config, events, hasConfirmedFacts, highOpenConflictsCount, onEventsChange, onError }: Props) {
  const [isFetching, setIsFetching] = useState(false);
  const [isBuildingQueries, setIsBuildingQueries] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const [queries, setQueries] = useState<ExternalEventQuery[]>([]);
  const [searchResult, setSearchResult] = useState<ExternalEventSearchResult | null>(null);
  const canFetch = hasConfirmedFacts && highOpenConflictsCount === 0;
  const highSeverity = events.filter((event) => event.severity.toLowerCase() === "high").length;
  const affectedPorts = new Set(events.flatMap((event) => event.affected_ports)).size;

  async function fetchEvents() {
    setIsFetching(true); onError(null);
    try { await api.fetchExternalEvents(caseId); onEventsChange(await api.getExternalEvents(caseId)); }
    catch (caught) { onError(caught instanceof Error ? caught.message : "External event fetch failed."); }
    finally { setIsFetching(false); }
  }
  async function buildQueries() {
    setIsBuildingQueries(true); onError(null);
    try { setQueries((await api.getExternalEventQueries(caseId)).queries); }
    catch (caught) { onError(caught instanceof Error ? caught.message : "External event query generation failed."); }
    finally { setIsBuildingQueries(false); }
  }
  async function searchEvents() {
    setIsSearching(true); onError(null);
    try { const result = await api.searchExternalEvents(caseId); setSearchResult(result); setQueries(result.queries_generated ?? []); onEventsChange(await api.getExternalEvents(caseId)); }
    catch (caught) { onError(caught instanceof Error ? caught.message : "External event search failed."); }
    finally { setIsSearching(false); }
  }

  return <section className="events-workspace">
    <section className="panel full-width event-command-panel">
      <div className="decision-panel-heading">
        <div><span className="section-kicker">Route monitoring</span><h2>External event scan</h2><p>Refresh disruption signals that may affect this vessel, route, or shipment window.</p></div>
        <div className="event-command-actions"><button className="secondary-action" type="button" onClick={buildQueries} disabled={!canFetch || isBuildingQueries}>{isBuildingQueries ? "Preparing…" : "Preview search"}</button><button className="primary-action" type="button" onClick={config?.real_search_enabled ? searchEvents : fetchEvents} disabled={!canFetch || isFetching || isSearching}>{isFetching || isSearching ? "Scanning…" : "Scan for events"}</button></div>
      </div>
      {!canFetch && <div className="prerequisite-inline"><span>!</span><div><strong>Case facts must be confirmed first</strong><p>{highOpenConflictsCount > 0 ? "Resolve high-severity conflicts, then confirm the case facts before scanning." : "Review and confirm the extracted case facts before scanning external sources."}</p></div></div>}
      <div className="event-scan-summary"><span><b>{events.length}</b> stored events</span><span><b>{highSeverity}</b> high severity</span><span><b>{affectedPorts}</b> affected ports</span><span><b>{new Set(events.map((event) => event.source_type)).size}</b> source types</span></div>
      <details className="technical-details"><summary>Source and search settings</summary><dl><div><dt>Mode</dt><dd>{config?.event_source_mode ?? "MOCK"}</dd></div><div><dt>Search</dt><dd>{config?.real_search_enabled ? "Enabled" : "Demo feed"}</dd></div><div><dt>Sources</dt><dd>{config?.connectors.length ?? 1}</dd></div><div><dt>Matched items</dt><dd>{searchResult?.rss_items_matched ?? 0}</dd></div></dl></details>
    </section>
    {queries.length > 0 && <SearchQueryList queries={queries} />}
    <ExternalEventsTable events={events} />
  </section>;
}

function SearchQueryList({ queries }: { queries: ExternalEventQuery[] }) {
  return <details className="panel full-width query-disclosure"><summary><span><strong>Prepared search queries</strong><small>Review the terms used to find route-relevant events.</small></span><span>{queries.length} queries</span></summary><div className="query-list">{queries.map((query) => <div key={query.query_id}><strong>{query.query_text}</strong><span>{query.query_type} · {query.priority}</span></div>)}</div></details>;
}

export function ExternalEventsTable({ events }: { events: ExternalEvent[] }) {
  return <section className="panel full-width events-list-panel">
    <div className="decision-panel-heading"><div><span className="section-kicker">Signal inbox</span><h2>Detected events</h2><p>Raw events before relevance and exposure assessment.</p></div><span className="tag">{events.length} events</span></div>
    {events.length === 0 ? <div className="review-empty"><span>0</span><div><strong>No events stored</strong><p>Run a scan after confirming the case facts.</p></div></div> : <div className="events-list">
      {events.map((event) => <article key={`${event.agent_run_id ?? "fetch"}-${event.event_id}`}>
        <span className={`event-severity ${event.severity.toLowerCase()}`}>{event.severity}</span>
        <div><h3>{event.title}</h3><p>{event.description}</p><small>{event.source} · {event.event_type.replace(/_/g, " ")}</small></div>
        <div><span className="row-label">Affected</span><strong>{[...event.affected_ports, ...event.affected_vessels].join(", ") || "Route region"}</strong></div>
        <div><span className="row-label">Confidence</span><strong>{Math.round((event.confidence ?? 0) * 100)}%</strong></div>
        {event.url ? <a href={event.url} target="_blank" rel="noreferrer">Open source ↗</a> : <span />}
      </article>)}
    </div>}
  </section>;
}
