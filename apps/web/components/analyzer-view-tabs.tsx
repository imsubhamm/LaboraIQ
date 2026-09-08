"use client";

import type { MouseEvent } from "react";

export function AnalyzerViewTabs({
  view,
  onViewChange,
}: {
  view: "config" | "health";
  onViewChange?: (view: "config" | "health") => void;
}) {
  function select(next: "config" | "health") {
    return (event: MouseEvent<HTMLAnchorElement>) => {
      if (!onViewChange) return;
      event.preventDefault();
      const href = next === "health" ? "/analyzers?view=health" : "/analyzers";
      window.history.replaceState(null, "", href);
      onViewChange(next);
    };
  }

  return (
    <nav className="view-tabs" aria-label="Analyzer views">
      <a href="/analyzers" className={view === "config" ? "active" : ""} onClick={select("config")}>
        Configuration
      </a>
      <a href="/analyzers?view=health" className={view === "health" ? "active" : ""} onClick={select("health")}>
        Machine health
      </a>
    </nav>
  );
}
