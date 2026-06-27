import { useState } from "react";
import {
  api,
  type EventConfig,
  type ExternalEvent,
  type ExternalEventQuery,
  type ExternalEventSearchResult
} from "../api/client";

type Props = {
  caseId: string;
  config: EventConfig | null;
  events: ExternalEvent[];
  hasConfirmedFacts: boolean;
  highOpenConflictsCount: number;
  onEventsChange: (events: ExternalEvent[]) => void;
  onError: (message: string | null) => void;
};

export function ExternalEventsPanel({
  caseId,
  config,
  events,
  hasConfirmedFacts,
  highOpenConflictsCount,
  onEventsChange,
  onError,
}: Props) {
  const [isFetching, setIsFetching] = useState(false);
  const [isBuildingQueries, setIsBuildingQueries] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const [lastResult, setLastResult] = useState<{ fetched: number; errors: number; mode: string } | null>(null);
  const [queries, setQueries] = useState<ExternalEventQuery[]>([]);
  const [searchResult, setSearchResult] = useState<ExternalEventSearchResult | null>(null);
  const canFetch = hasConfirmedFacts && highOpenConflictsCount === 0;

  async function fetchEvents() {
    setIsFetching(true);
    onError(null);
    try {
      const result = await api.fetchExternalEvents(caseId);
      setLastResult({ fetched: result.events_deduped_count, errors: result.connector_errors.length, mode: result.mode });
      onEventsChange(await api.getExternalEvents(caseId));
    } catch (caught) {
      onError(caught instanceof Error ? caught.message : "External event fetch failed.");
    } finally {
      setIsFetching(false);
    }
  }

  async function buildQueries() {
    setIsBuildingQueries(true);
    onError(null);
    try {
      const result = await api.getExternalEventQueries(caseId);
      setQueries(result.queries);
    } catch (caught) {
      onError(caught instanceof Error ? caught.message : "External event query generation failed.");
    } finally {
      setIsBuildingQueries(false);
    }
  }

  async function searchEvents() {
    setIsSearching(true);
    onError(null);
    try {
      const result = await api.searchExternalEvents(caseId);
      setSearchResult(result);
      setQueries(result.queries_generated ?? []);
      onEventsChange(await api.getExternalEvents(caseId));
    } catch (caught) {
      onError(caught instanceof Error ? caught.message : "External event search failed.");
    } finally {
      setIsSearching(false);
    }
  }

  return (
    <section>
      <div className="workspace-grid">
        <section className="panel">
          <div className="panel-heading">
            <div>
              <h2>Event Source Mode</h2>
              <p className="subtle">External events are normalized before relevance scoring.</p>
            </div>
            <span className="tag">Event Mode: {config?.event_source_mode ?? "Loading"}</span>
          </div>
          <dl className="field-grid">
            <div><dt>Connectors</dt><dd>{config?.connectors?.length ? config.connectors.join(", ") : "Loading"}</dd></div>
            <div><dt>Last Fetch</dt><dd>{lastResult ? `${lastResult.fetched} events / ${lastResult.errors} errors` : "Not fetched in this session"}</dd></div>
            <div><dt>GDELT</dt><dd>{config?.gdelt_enabled ? "Enabled" : "Disabled"}</dd></div>
            <div><dt>RSS News Fallback</dt><dd>{config?.real_search_enabled ? `Enabled (${config?.configured_feeds_count ?? 0} feeds)` : "Disabled"}</dd></div>
            <div><dt>Open-Meteo</dt><dd>{config?.open_meteo_enabled ? "Enabled" : "Disabled"}</dd></div>
            <div><dt>GDELT Lookback</dt><dd>{config?.gdelt_lookback_days ?? 7} days</dd></div>
            <div><dt>GDELT Max Records</dt><dd>{config?.gdelt_max_records ?? 10}</dd></div>
            <div><dt>Query Limit</dt><dd>{config?.external_event_query_limit ?? 3}</dd></div>
            <div><dt>Weather Location Limit</dt><dd>{config?.real_event_location_limit ?? config?.external_event_query_limit ?? 3}</dd></div>
            <div><dt>Weather Forecast</dt><dd>{config?.open_meteo_forecast_days ?? 3} days</dd></div>
            <div><dt>LLM Event Extraction</dt><dd>{config?.use_llm_event_extraction ? "Enabled" : "Disabled"}</dd></div>
          </dl>
          {!hasConfirmedFacts && <div className="warning-banner">Confirmed case facts are required before fetching external events.</div>}
          {highOpenConflictsCount > 0 && <div className="warning-banner">Resolve High OPEN conflicts before fetching external events.</div>}
          <button
            className="primary-action"
            type="button"
            onClick={fetchEvents}
            disabled={!canFetch || isFetching}
            title={!canFetch ? "Confirmed facts are required and high conflicts must be resolved." : undefined}
          >
            {isFetching ? "Fetching..." : "Fetch External Events"}
          </button>
        </section>
        <section className="panel">
          <div className="panel-heading"><h2>Real Search</h2></div>
          <p className="subtle">
            Search queries are generated from the confirmed watch profile, then GDELT, RSS news fallback, and Open-Meteo outputs are normalized into external events.
          </p>
          <div className="action-row">
            <button
              className="secondary-action"
              type="button"
              onClick={buildQueries}
              disabled={!canFetch || isBuildingQueries}
              title={!canFetch ? "Confirmed facts are required and high conflicts must be resolved." : undefined}
            >
              {isBuildingQueries ? "Generating..." : "Generate Search Queries"}
            </button>
            <button
              className="primary-action"
              type="button"
              onClick={searchEvents}
              disabled={!canFetch || isSearching}
              title={!canFetch ? "Confirmed facts are required and high conflicts must be resolved." : undefined}
            >
              {isSearching ? "Searching..." : "Search Real External Events"}
            </button>
          </div>
          <div className="mini-metrics">
            <div><strong>{searchResult?.queries_generated?.length ?? 0}</strong><span>Queries</span></div>
            <div><strong>{searchResult?.gdelt_articles_fetched ?? 0}</strong><span>GDELT Articles</span></div>
            <div><strong>{searchResult?.gdelt_events_extracted?.length ?? 0}</strong><span>GDELT Events</span></div>
            <div><strong>{searchResult?.rss_items_fetched ?? 0}</strong><span>RSS Items</span></div>
            <div><strong>{searchResult?.rss_items_matched ?? 0}</strong><span>RSS Matched</span></div>
            <div><strong>{searchResult?.weather_locations_checked ?? 0}</strong><span>Weather Locations</span></div>
            <div><strong>{searchResult?.weather_events_extracted?.length ?? 0}</strong><span>Weather Events</span></div>
            <div><strong>{events.length}</strong><span>Stored Events</span></div>
          </div>
          {searchResult?.warnings.map((warning) => <div className="warning-banner" key={warning}>{warning}</div>)}
          {searchResult?.connector_errors.map((error) => (
            <div className="warning-banner" key={`${error.connector ?? error.feed_url ?? error.location ?? error.title ?? "source"}-${error.error}`}>
              {error.connector ?? error.feed_url ?? error.location ?? error.title ?? "Connector"}: {error.error}
            </div>
          ))}
        </section>
      </div>
      <SearchQueryTable queries={queries} />
      <ExternalEventsTable events={events} />
    </section>
  );
}

function SearchQueryTable({ queries }: { queries: ExternalEventQuery[] }) {
  return (
    <section className="panel full-width">
      <div className="panel-heading">
        <h2>Search Query Preview</h2>
        <span className="tag">{queries.length} queries</span>
      </div>
      {queries.length === 0 ? <p className="empty-state">No search queries generated for this case yet.</p> : (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Query</th>
                <th>Type</th>
                <th>Priority</th>
                <th>Source Hint</th>
                <th>Created From</th>
              </tr>
            </thead>
            <tbody>
              {queries.map((query) => (
                <tr key={query.query_id}>
                  <td>{query.query_text}</td>
                  <td>{query.query_type}</td>
                  <td>{query.priority}</td>
                  <td>{query.source_hint}</td>
                  <td>{query.created_from.join(", ") || "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

export function ExternalEventsTable({ events }: { events: ExternalEvent[] }) {
  return (
    <section className="panel full-width">
      <div className="panel-heading">
        <h2>External Events</h2>
        <span className="tag">{events.length} events</span>
      </div>
      {events.length === 0 ? <p className="empty-state">No external events stored for this case yet.</p> : (
        <div className="table-wrap">
          <table className="data-table wide-data-table">
            <thead>
              <tr>
                <th>Event Title</th>
                <th>Source</th>
                <th>Source Type</th>
                <th>Event Type</th>
                <th>Severity</th>
                <th>Confidence</th>
                <th>Published At</th>
                <th>Event Time</th>
                <th>Affected Ports</th>
                <th>Affected Vessels</th>
                <th>Matched Terms</th>
                <th>URL</th>
              </tr>
            </thead>
            <tbody>
              {events.map((event) => (
                <tr key={`${event.agent_run_id ?? "fetch"}-${event.event_id}`}>
                  <td>{event.title}</td>
                  <td>{event.source}</td>
                  <td>{event.source_type}</td>
                  <td>{event.event_type}</td>
                  <td>{event.severity}</td>
                  <td>{Math.round((event.confidence ?? 0) * 100)}%</td>
                  <td>{event.published_at || "-"}</td>
                  <td>{event.event_time || "-"}</td>
                  <td>{event.affected_ports.join(", ") || "-"}</td>
                  <td>{event.affected_vessels.join(", ") || "-"}</td>
                  <td>{event.matched_terms?.join(", ") || event.matched_query_ids?.join(", ") || "-"}</td>
                  <td>{event.url ? <a href={event.url} target="_blank" rel="noreferrer">Open Source</a> : "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
