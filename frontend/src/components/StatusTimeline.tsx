import type { StatusTimelineEntry } from "../api/client";
import { t, translate, type Language } from "../i18n";

type Props = {
  entries: StatusTimelineEntry[];
  language: Language;
};

export function StatusTimeline({ entries, language }: Props) {
  return (
    <section className="panel status-timeline-panel">
      <div className="panel-heading">
        <h2>{t(language, "statusTimeline")}</h2>
      </div>
      <ol className="timeline">
        {entries.map((entry, index) => (
          <li key={`${entry.status}-${index}`}>
            <strong>{translate.status(language, entry.status)}</strong>
            <span>{translate.timelineReason(language, entry.reason)}</span>
          </li>
        ))}
      </ol>
    </section>
  );
}
