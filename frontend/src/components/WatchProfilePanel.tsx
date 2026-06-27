import type { WatchProfile } from "../api/client";
import { t, translate, type Language } from "../i18n";

type Props = {
  profile: WatchProfile;
  language: Language;
};

export function WatchProfilePanel({ profile, language }: Props) {
  return (
    <section className="panel watch-profile-panel">
      <div className="panel-heading">
        <h2>{t(language, "watchProfile")}</h2>
      </div>
      <dl className="watch-profile-grid">
        <div><dt>{t(language, "watchedVessel")}</dt><dd>{profile.watched_vessel}</dd></div>
        <div><dt>{t(language, "watchedPorts")}</dt><dd>{profile.watched_ports.join(", ")}</dd></div>
        <div><dt>{t(language, "routeRegions")}</dt><dd>{profile.watched_route_regions.join(", ")}</dd></div>
        <div><dt>{t(language, "riskCategories")}</dt><dd>{profile.risk_categories.map((category) => translate.exposure(language, category)).join(", ")}</dd></div>
      </dl>
      <div className="subsection-heading">Alert rules</div>
      <ul className="watch-rule-list">
        {profile.alert_rules.map((rule) => (
          <li key={rule}>{translate.rule(language, rule)}</li>
        ))}
      </ul>
    </section>
  );
}
