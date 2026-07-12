import { useEffect, useMemo, useState } from "react";
import type { TradeCase } from "./api/client";
import { AppShell } from "./components/AppShell";
import { CaseLibrary } from "./pages/CaseLibrary";
import { CaseWorkspace } from "./pages/CaseWorkspace";
import { CreateCase } from "./pages/CreateCase";
import type { Language } from "./i18n";

const ACTIVE_CASE_STORAGE_KEY = "foresail.activeCaseId";
const CASE_IDS_STORAGE_KEY = "foresail.caseIds";

export default function App() {
  const [path, setPath] = useState(normalizePath(window.location.pathname));
  const [caseIds, setCaseIds] = useState<string[]>(readCaseIds);
  const [language, setLanguage] = useState<Language>("en");

  useEffect(() => {
    if (window.location.pathname === "/") {
      navigate("/cases", true);
    }

    function handlePopState() {
      setPath(normalizePath(window.location.pathname));
    }

    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  useEffect(() => {
    const storedCaseId = window.localStorage.getItem(ACTIVE_CASE_STORAGE_KEY);
    if (storedCaseId && !caseIds.includes(storedCaseId)) {
      updateCaseIds([storedCaseId, ...caseIds]);
    }
  }, [caseIds]);

  const route = useMemo(() => parseRoute(path), [path]);

  function navigate(nextPath: string, replace = false) {
    const normalized = normalizePath(nextPath);
    if (replace) {
      window.history.replaceState({}, "", normalized);
    } else {
      window.history.pushState({}, "", normalized);
    }
    setPath(normalized);
  }

  function updateCaseIds(nextIds: string[]) {
    const deduped = Array.from(new Set(nextIds.filter(Boolean)));
    setCaseIds(deduped);
    window.localStorage.setItem(CASE_IDS_STORAGE_KEY, JSON.stringify(deduped));
  }

  function registerCase(tradeCase: TradeCase | null) {
    if (!tradeCase) {
      window.localStorage.removeItem(ACTIVE_CASE_STORAGE_KEY);
      return;
    }
    window.localStorage.setItem(ACTIVE_CASE_STORAGE_KEY, tradeCase.case_id);
    updateCaseIds([tradeCase.case_id, ...caseIds]);
  }

  function forgetCase(caseId: string) {
    if (window.localStorage.getItem(ACTIVE_CASE_STORAGE_KEY) === caseId) {
      window.localStorage.removeItem(ACTIVE_CASE_STORAGE_KEY);
    }
    updateCaseIds(caseIds.filter((existingCaseId) => existingCaseId !== caseId));
  }

  return (
    <AppShell
      activePath={path}
      language={language}
      onNavigate={navigate}
      onToggleLanguage={() => setLanguage(language === "en" ? "zh" : "en")}
    >
      {route.name === "new" && (
        <CreateCase
          language={language}
          onCancel={() => navigate("/cases")}
          onCaseCreated={(tradeCase, targetPath) => {
            registerCase(tradeCase);
            navigate(targetPath ?? `/cases/${tradeCase.case_id}`);
          }}
        />
      )}
      {route.name === "detail" && (
        <CaseWorkspace
          caseId={route.caseId}
          language={language}
          onNavigate={navigate}
          onCaseChange={(tradeCase) => {
            registerCase(tradeCase);
          }}
        />
      )}
      {route.name === "library" && (
        <CaseLibrary caseIds={caseIds} onNavigate={navigate} onRegisterCase={registerCase} onForgetCase={forgetCase} />
      )}
    </AppShell>
  );
}

function normalizePath(value: string) {
  if (!value || value === "/") return "/cases";
  return value.replace(/\/+$/, "") || "/cases";
}

function parseRoute(path: string): { name: "library" } | { name: "new" } | { name: "detail"; caseId: string } {
  if (path === "/cases/new") return { name: "new" };
  const detailMatch = path.match(/^\/cases\/([^/?]+)/);
  if (detailMatch) return { name: "detail", caseId: decodeURIComponent(detailMatch[1]) };
  return { name: "library" };
}

function readCaseIds() {
  try {
    const parsed = JSON.parse(window.localStorage.getItem(CASE_IDS_STORAGE_KEY) || "[]");
    return Array.isArray(parsed) ? parsed.filter((value): value is string => typeof value === "string") : [];
  } catch {
    return [];
  }
}
