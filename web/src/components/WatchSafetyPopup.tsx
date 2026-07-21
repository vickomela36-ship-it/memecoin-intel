"use client";

import { useEffect, useState } from "react";
import SafetyCard from "@/components/SafetyCard";
import { jsonFetcher } from "@/lib/utils";
import type { SafetyReport } from "@/types";

/**
 * App-wide listener: whenever a token is added to the watchlist, the safety
 * card comes up automatically. Watching a rug is how bags happen.
 */
export default function WatchSafetyPopup() {
  const [symbol, setSymbol] = useState<string | null>(null);
  const [report, setReport] = useState<SafetyReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(false);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const onAdd = async (e: Event) => {
      const { address, symbol } = (e as CustomEvent<{ address: string; symbol: string }>).detail ?? {};
      if (!address) return;
      setSymbol(symbol ?? null);
      setReport(null);
      setFailed(false);
      setOpen(true);
      setLoading(true);
      try {
        const r = await jsonFetcher<SafetyReport>(`/api/safety?mint=${address}`);
        setReport(r);
      } catch {
        setFailed(true);
      } finally {
        setLoading(false);
      }
    };
    window.addEventListener("mi:watch-added", onAdd);
    return () => window.removeEventListener("mi:watch-added", onAdd);
  }, []);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center p-4 overflow-y-auto"
      style={{ background: "var(--bg-overlay)" }}
      onClick={() => setOpen(false)}
    >
      <div className="max-w-2xl w-full my-8" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-2">
          <span className="font-mono-display text-sm text-[var(--text-secondary)]">
            Added {symbol ? `$${symbol}` : "token"} to watchlist — auto safety check
          </span>
          <button
            onClick={() => setOpen(false)}
            className="font-mono-display text-sm text-[var(--text-secondary)] px-2 hover:text-[var(--text-primary)]"
          >
            ✕ close
          </button>
        </div>

        {loading && (
          <div className="card text-sm text-[var(--text-secondary)]">
            Running safety checks — LP lock, authorities, holders, honeypot triad…
          </div>
        )}
        {failed && (
          <div className="card text-sm" style={{ color: "var(--signal-neutral)" }}>
            Safety sources are rate-limited right now. The token is on your
            watchlist — run the check manually from the Safety tab in ~30s.
          </div>
        )}
        {report && <SafetyCard report={report} />}
      </div>
    </div>
  );
}
