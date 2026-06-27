import type { RecommendedAction } from "../api/client";
import { t, translate, type Language } from "../i18n";

type Props = { actions: RecommendedAction[]; language: Language };

export function ActionBoard({ actions, language }: Props) {
  const highPriority = actions.filter((action) => action.priority.toLowerCase() === "high").length;
  const dueToday = actions.filter((action) => action.deadline.toLowerCase() === "today").length;
  const owners = new Set(actions.map((action) => action.owner_role)).size;

  return (
    <section className="panel full-width action-board">
      <div className="decision-panel-heading">
        <div><span className="section-kicker">Execution queue</span><h2>{t(language, "actionBoard")}</h2><p>Prioritized work generated from the active risk exposures.</p></div>
        <span className="tag">{actions.length} {t(language, "actions")}</span>
      </div>
      {actions.length === 0 ? <p className="empty-state">{t(language, "noActions")}</p> : <>
        <div className="queue-summary"><span><b>{dueToday}</b> due today</span><span><b>{highPriority}</b> high priority</span><span><b>{owners}</b> responsible teams</span></div>
        <div className="action-list" role="list">
          {actions.map((action) => (
            <article className="action-list-row" key={action.action_id} role="listitem">
              <span className="action-status-dot" aria-hidden="true" />
              <div className="action-main"><span className="action-id">{action.action_id}</span><h3>{translate.action(language, action.title)}</h3><small>{translate.exposure(language, action.related_exposure)}</small></div>
              <div><span className="row-label">Owner</span><strong>{translate.owner(language, action.owner_role)}</strong></div>
              <div><span className="row-label">Due</span><strong>{translate.deadline(language, action.deadline)}</strong></div>
              <span className={`priority-pill ${action.priority.toLowerCase()}`}>{translate.severity(language, action.priority)}</span>
            </article>
          ))}
        </div>
      </>}
    </section>
  );
}
