import type { Language } from "../i18n";
import type { ReactNode } from "react";
import { useEffect, useRef, useState } from "react";
import { api, type CompanyProfile } from "../api/client";
import foresailLogo from "../assets/foresail-logo.png";

type Props = {
  activePath: string;
  children: ReactNode;
  language: Language;
  onNavigate: (path: string) => void;
  onToggleLanguage: () => void;
};

export function AppShell({ activePath, children, onNavigate }: Props) {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [company, setCompany] = useState<CompanyProfile | null>(null);
  const settingsRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!settingsOpen || company) return;
    api.getCompanyProfile().then(setCompany).catch(() => setCompany({ name: "Unavailable", aliases: [] }));
  }, [settingsOpen, company]);

  useEffect(() => {
    if (!settingsOpen) return;
    function onClickAway(event: MouseEvent) {
      if (settingsRef.current && !settingsRef.current.contains(event.target as Node)) {
        setSettingsOpen(false);
      }
    }
    document.addEventListener("mousedown", onClickAway);
    return () => document.removeEventListener("mousedown", onClickAway);
  }, [settingsOpen]);

  return (
    <div className="app-shell">
      <div className="app-frame">
        <nav className="fsnav" aria-label="Primary navigation">
          <button className="fsnav-brand" type="button" onClick={() => onNavigate("/cases")} aria-label="ForeSail home">
            <img src={foresailLogo} alt="ForeSail" draggable="false" />
          </button>
          <div className="fsnav-tabs">
            <button className={activePath.startsWith("/cases") ? "active" : ""} type="button" onClick={() => onNavigate("/cases")}>Trade Risk</button>
            <button type="button" onClick={() => onNavigate("/cases")}>Trade Ops</button>
          </div>
          <div className="fsnav-util">
            <button className="fsnav-icon notif" type="button" aria-label="Notifications"><span /></button>
            <button
              className="fsnav-icon"
              type="button"
              aria-label="Replay guided tour"
              title="Replay guided tour"
              onClick={() => window.dispatchEvent(new CustomEvent("foresail:guide-restart"))}
            >
              <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9" /><path d="M9.5 9a2.5 2.5 0 0 1 4.5 1.5c0 1.5-2 2-2 3.5M12 17h.01" /></svg>
            </button>
            <div className="fsnav-settings" ref={settingsRef}>
              <button className="fsnav-icon" type="button" aria-label="Settings" aria-expanded={settingsOpen} onClick={() => setSettingsOpen((open) => !open)}>
                <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09a1.65 1.65 0 0 0 1.51-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33h.01a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51h.01a1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82v.01a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" /></svg>
              </button>
              {settingsOpen && (
                <div className="fsnav-settings-panel" role="dialog" aria-label="Workspace settings">
                  <span className="panel-kicker">Our Company</span>
                  <strong>{company ? company.name : "Loading…"}</strong>
                  {company && company.aliases.length > 0 && (
                    <p className="panel-aliases">Also known as: {company.aliases.join(" · ")}</p>
                  )}
                  <p className="panel-note">{company?.role_note ?? "Seat (buyer/seller) is auto-detected per case from LC, contract, and B/L parties."}</p>
                </div>
              )}
            </div>
            <div className="fsnav-lang" aria-label="Language: English">
              <span aria-hidden="true" />
              <small>EN</small>
            </div>
          </div>
        </nav>
        <main className="shell-main">{children}</main>
      </div>
    </div>
  );
}
