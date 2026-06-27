import type { Language } from "../i18n";
import type { ReactNode } from "react";

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
            <span className="brand-mark" aria-hidden="true">
              <svg viewBox="0 0 32 32"><path d="M17 3.5c-4.1 5.3-6.6 11.4-7.2 18.1 3.3-1.7 6.3-4 8.9-6.8L17 3.5Z"/><path d="M19.3 4.8l1.4 10.1c2 2.8 4.5 5.1 7.3 7-1.1-6.7-4-12.4-8.7-17.1Z" opacity=".72"/><path d="M4 23.5c7.1 1.8 14.7 1.8 23.7-.1-5 4.6-12.3 6.4-19 3.8L4 23.5Z" opacity=".9"/></svg>
            </span>
            <strong>ForeSail</strong>
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
