"use client";

import { useEffect, useState } from "react";
import {
  HIT_DEFINITIONS,
  exportLogsJson,
  moduleAccuracy,
} from "@/lib/accuracy-tracker";
import type { ModuleAccuracy, ModuleId } from "@/types";

const MODULES: { id: ModuleId; label: string }[] = [
  { id: "memecoin", label: "Memecoin Scanner" },
  { id: "football", label: "Football Predictor" },
  { id: "crypto", label: "Crypto Score" },
];

export default function TrackRecord({ refreshKey }: { refreshKey: number }) {
  const [expanded, setExpanded] = useState(false);
  const [stats, setStats] = useState<ModuleAccuracy[]>([]);

  useEffect(() => {
    setStats(MODULES.map((m) => moduleAccuracy(m.id)));
  }, [refreshKey, expanded]);

  const summary = stats
    .map((s) => {
      const label = MODULES.find((m) => m.id === s.module)?.label.split(" ")[0];
      return s.hitRate !== null
        ? `${label}: ${(s.hitRate * 100).toFixed(0)}%`
        : `${label}: tracking (${s.resolved})`;
    })
    .join("  ·  ");

  function handleExport() {
    const blob = new Blob([exportLogsJson()], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `memecoin-intel-signals-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <footer className="border-t border-[var(--border-subtle)] mt-6 px-4 py-3">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="font-mono-display text-xs text-[var(--text-secondary)]">
          TRACK RECORD — {summary}
        </div>
        <div className="flex gap-3">
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-xs font-mono-display text-[var(--signal-edge)] hover:underline"
          >
            {expanded ? "collapse" : "▸ view full history"}
          </button>
          <button
            onClick={handleExport}
            className="text-xs font-mono-display text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
          >
            export JSON
          </button>
        </div>
      </div>

      {expanded && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mt-3">
          {stats.map((s) => {
            const meta = MODULES.find((m) => m.id === s.module)!;
            return (
              <div key={s.module} className="card">
                <div className="font-mono-display text-sm mb-1">
                  {meta.label}
                </div>
                <div className="text-xs space-y-0.5 text-[var(--text-secondary)]">
                  <div>Signals fired: {s.fired}</div>
                  <div>Resolved: {s.resolved}</div>
                  <div>
                    Hit rate:{" "}
                    {s.hitRate !== null
                      ? `${(s.hitRate * 100).toFixed(0)}% (${s.hits}/${s.resolved})`
                      : `needs ${Math.max(0, 5 - s.resolved)} more resolutions`}
                  </div>
                  <div className="text-[var(--text-tertiary)] pt-1">
                    Hit = {HIT_DEFINITIONS[s.module]}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      <div className="text-xs text-[var(--text-tertiary)] mt-2">
        All accuracy numbers are computed from locally-logged signals and real
        outcomes — nothing is simulated. This tool surfaces intelligence; it is
        not financial advice and profits are not guaranteed.
      </div>
    </footer>
  );
}
