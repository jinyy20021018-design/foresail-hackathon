import type { Language } from "../i18n";
import type { ReactNode } from "react";
import foresailLogo from "../assets/foresail-logo.png";

type Props = {
  activePath: string;
  children: ReactNode;
  language: Language;
  onNavigate: (path: string) => void;
  onToggleLanguage: () => void;
};

export function AppShell({ activePath, children, language, onNavigate, onToggleLanguage }: Props) {
  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar-inner">
          <button className="brand" type="button" onClick={() => onNavigate("/cases")}>
            <span className="brand-logo-crop"><img src={foresailLogo} alt="ForeSail" draggable="false" /></span>
          </button>
          <nav className="top-nav" aria-label="Primary navigation">
            <button className={activePath.startsWith("/cases") ? "active" : ""} type="button" onClick={() => onNavigate("/cases")}>Trade Risk</button>
            <button type="button" onClick={() => onNavigate("/cases")}>Trade Ops</button>
          </nav>
          <span className="topbar-spacer" />
          <button className="icon-button notification-button" type="button" aria-label="Notifications"><span /></button>
          <button className="icon-button" type="button" aria-label="Help">?</button>
          <button className="user-chip" type="button" onClick={onToggleLanguage} aria-label="Switch language">
            <span>JL</span>
            <small>{language === "en" ? "EN" : "中文"} ▾</small>
          </button>
        </div>
      </header>
      <main className="shell-main">{children}</main>
    </div>
  );
}
