"use client";

import { useEffect, useRef, useState } from "react";
import SafetyCard from "@/components/SafetyCard";
import { addWatch } from "@/lib/storage";
import { jsonFetcher } from "@/lib/utils";
import type { SafetyReport } from "@/types";

export default function IntelView() {
  const [input, setInput] = useState("");
  const [report, setReport] = useState<SafetyReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [deepLoading, setDeepLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function extractMint(raw: string): string | null {
    const m = raw.trim().match(/[A-Za-z0-9]{32,44}/);
    return m ? m[0] : null;
  }

  const lastMint = useRef<string | null>(null);

  useEffect(() => {
    const onGoto = (e: Event) => {
      const addr = (e as CustomEvent<string>).detail;
      if (!addr) return;
      setInput(addr);
      void run(false, addr);
    };
    window.addEventListener("mi:goto-safety", onGoto);
    return () => window.removeEventListener("mi:goto-safety", onGoto);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function run(deep = false, addrOverride?: string) {
    // Deep scan re-runs the token already displayed; otherwise parse the box
    const mint = deep
      ? lastMint.current
      : extractMint(addrOverride ?? input);
    if (!mint) {
      setError("Paste a valid Solana contract address (or a DexScreener/Solscan link).");
      return;
    }
    lastMint.current = mint;
    setError(null);
    if (deep) setDeepLoading(true);
    else {
      setLoading(true);
      setReport(null);
    }
    try {
      const r = await jsonFetcher<SafetyReport>(`/api/safety?mint=${mint}${deep ? "&deep=1" : ""}`);
      setReport(r);
    } catch {
      setError("Could not reach the safety sources. They may be rate-limited — try again shortly.");
    } finally {
      setLoading(false);
      setDeepLoading(false);
    }
  }

  return (
    <div className="space-y-3">
      <div className="text-xs text-[var(--text-tertiary)] border border-[var(--border-subtle)] rounded-card px-3 py-2">
        Paste any Solana contract address for a full safety breakdown — LP lock,
        mint/freeze authority, holder concentration (LP excluded), volume/mcap,
        honeypot triad, and creator wallet. Every check is expandable and
        explained. This surfaces information; it never tells you to buy or sell.
      </div>

      <div className="card">
        <div className="flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && run(false)}
            placeholder="Paste contract address or DexScreener/Solscan link…"
            className="flex-1 bg-[var(--bg-elevated)] rounded-input px-3 py-2 text-sm border border-[var(--border-subtle)] focus:border-[var(--border-active)] outline-none font-mono-display"
          />
          <button
            onClick={() => run(false)}
            disabled={loading}
            className="font-mono-display text-sm px-4 py-2 rounded-btn disabled:opacity-50"
            style={{ background: "var(--signal-edge)", color: "var(--bg-primary)" }}
          >
            {loading ? "CHECKING…" : "CHECK"}
          </button>
        </div>
        {error && <div className="mt-2 text-sm" style={{ color: "var(--signal-short)" }}>{error}</div>}
      </div>

      {report && (
        <>
          <SafetyCard
            report={report}
            deepLoading={deepLoading}
            onDeepScan={report.deep?.ran ? undefined : () => run(true)}
          />
          <div className="flex gap-3">
            <button
              onClick={() =>
                addWatch({
                  address: report.mint,
                  symbol: report.symbol,
                  name: report.name,
                  entryPrice: 0,
                  target2x: 0,
                  grade: `SAFETY-${report.verdict}`,
                  pairUrl: `https://dexscreener.com/solana/${report.mint}`,
                })
              }
              className="text-xs font-mono-display px-3 py-1.5 rounded-btn border border-[var(--border-subtle)] text-[var(--text-secondary)] hover:border-[var(--border-active)]"
            >
              + Watch
            </button>
            <a
              href={`https://dexscreener.com/solana/${report.mint}`}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs font-mono-display px-3 py-1.5 text-[var(--signal-edge)] hover:underline self-center"
            >
              DexScreener ↗
            </a>
            <a
              href={`https://rugcheck.xyz/tokens/${report.mint}`}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs font-mono-display px-3 py-1.5 text-[var(--signal-edge)] hover:underline self-center"
            >
              Rugcheck ↗
            </a>
          </div>
        </>
      )}
    </div>
  );
}
