import type { RecommendedAction } from "../api/client";
import { t, translate, type Language } from "../i18n";

type Props = {
  actions: RecommendedAction[];
  language: Language;
};

export function ActionBoard({ actions, language }: Props) {
  return (
    <section className="panel full-width">
      <div className="panel-heading">
        <h2>{t(language, "actionBoard")}</h2>
        <span className="tag">
          {actions.length} {t(language, "actions")}
        </span>
      </div>
      {actions.length === 0 ? (
        <p className="empty-state">{t(language, "noActions")}</p>
      ) : (
        <div className="action-grid">
          {actions.map((action) => (
            <article className="action-item" key={action.action_id}>
              <div>
                <span className="action-id">{action.action_id}</span>
                <h3>{translate.action(language, action.title)}</h3>
              </div>
              <dl>
                <div>
                  <dt>{t(language, "owner")}</dt>
                  <dd>{translate.owner(language, action.owner_role)}</dd>
                </div>
                <div>
                  <dt>{t(language, "priority")}</dt>
                  <dd>{translate.severity(language, action.priority)}</dd>
                </div>
                <div>
                  <dt>{t(language, "deadline")}</dt>
                  <dd>{translate.deadline(language, action.deadline)}</dd>
                </div>
                <div>
                  <dt>{t(language, "exposure")}</dt>
                  <dd>{translate.exposure(language, action.related_exposure)}</dd>
                </div>
                <div>
                  <dt>Perspective</dt>
                  <dd>{action.party_perspective ?? "SELLER"}</dd>
                </div>
                <div>
                  <dt>Responsible</dt>
                  <dd>{action.responsible_party ?? "UNKNOWN"}</dd>
                </div>
                <div>
                  <dt>Incoterm</dt>
                  <dd>{action.incoterm_basis || "N/A"}</dd>
                </div>
              </dl>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
