"use client";

import { useCallback, useEffect, useState } from "react";
import { jsonFetcher } from "@/lib/utils";
import type { MemeScanResult } from "@/types";

type Category = "PROVEN" | "SERIAL" | "ONE-HIT" | "RUG-PRONE" | "COOKING" | "NEW";

interface CreatorStats {
  creator: string;
  tokenCount: number;
  hits: number;
  bestMultiple: number;
  avgPeakMultiple: number;
  hitRate: number;
  category: Category;
  recentTokens: { symbol: string; mint: string; peakMultiple: number; ageHours: number }[];
}

const CAT_COLOR: Record<Category, string> = {
  PROVEN: "var(--signal-long)",
  SERIAL: "var(--signal-edge)",
  "ONE-HIT": "var(--signal-neutral)",
  COOKING: "var(--signal-edge)",
  "RUG-PRONE": "var(--signal-short)",
  NEW: "var(--text-tertiary)",
};

const CAT_DESC: Record<Category, string> = {
  PROVEN: "2+ tokens that did 2x+, hit rate ≥40% — a deployer worth watching",
  SERIAL: "Launches often; mixed results — size small, they spray",
  "ONE-HIT": "One winner so far — could be skill or luck, small sample",
  COOKING: "Has a token launched in the last few hours right now",
  "RUG-PRONE": "Most launches died fast — treat new drops as exit liquidity",
  NEW: "Not enough history yet to judge",
};

function short(a: string) {
  return `${a.slice(0, 4)}…${a.slice(-4)}`;
}

export default function CreatorsView() {
  const [creators, setCreators] = useState<CreatorStats[]>([]);
  const [loading, setLoading] = useState(true);
  const [kvOff, setKvOff] = useState(false);
  const [ingested, setIngested] = useState<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      // 1) Feed the ledger from the current scan (launches + pumpfun)
      try {
        const scan = await jsonFetcher<MemeScanResult>("/api/scan");
        const tokens = [...(scan.launches ?? []), ...(scan.pumpfun ?? [])].map((s) => ({
          mint: s.address, symbol: s.symbol, mcap: s.fdv,
        }));
        if (tokens.length) {
          const res = await fetch("/api/creators", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ tokens }),
          });
          if (res.status === 503) setKvOff(true);
          else {
            const d = await res.json();
            setIngested(d?.ingested ?? 0);
          }
        }
      } catch {
        /* ingest best-effort */
      }
      // 2) Read the leaderboard
      const data = await jsonFetcher<{ creators: CreatorStats[]; error?: string }>("/api/creators");
      setCreators(data.creators ?? []);
      if (data.error === "kv not configured") setKvOff(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const proven = creators.filter((c) => c.category === "PROVEN" || c.category === "SERIAL");
  const freshFromProven = proven
    .flatMap((c) =>
      c.recentTokens
        .filter((t) => t.ageHours < 24)
        .map((t) => ({ ...t, creator: c.creator, category: c.category, best: c.bestMultiple }))
    )
    .sort((a, b) => a.ageHours - b.ageHours);

  return (
    <div className="space-y-3">
      <div className="text-xs text-[var(--text-tertiary)] border border-[var(--border-subtle)] rounded-card px-3 py-2">
        Track record of pump.fun deployer wallets, built up over time from
        tokens the scanner surfaces. Categorized by how their launches actually
        performed — not hype. A creator&apos;s history is information, not a buy
        signal: proven deployers also rug. Not financial advice.
      </div>

      <div className="card flex items-center justify-between flex-wrap gap-2">
        <span className="font-mono-display text-sm text-[var(--text-secondary)]">
          {creators.length} tracked creators
          {ingested !== null && ingested > 0 && ` · +${ingested} new this visit`}
        </span>
        <button
          onClick={load}
          disabled={loading}
          className="text-xs font-mono-display px-3 py-1.5 rounded-btn border border-[var(--border-active)] text-[var(--signal-edge)] disabled:opacity-50"
        >
          {loading ? "SCANNING…" : "REFRESH"}
        </button>
      </div>

      {kvOff && (
        <div className="card text-sm" style={{ color: "var(--signal-neutral)" }}>
          The creator ledger needs the KV store to persist. It looks
          unconfigured for this deployment — connect Vercel KV and redeploy.
        </div>
      )}

      {/* Fresh launches from proven creators — the watch signal */}
      {freshFromProven.length > 0 && (
        <div className="card" style={{ borderColor: "var(--signal-long)" }}>
          <h2 className="font-mono-display text-lg" style={{ color: "var(--signal-long)" }}>
            FRESH FROM PROVEN CREATORS ({freshFromProven.length})
          </h2>
          <p className="text-xs text-[var(--text-tertiary)] mb-2">
            Tokens launched in the last 24h by wallets with a real track record.
            Still do your own safety check — history rhymes, it doesn&apos;t repeat.
          </p>
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead><tr><th>Token</th><th>Age</th><th>Creator</th><th>Their best</th><th>Peak so far</th><th></th></tr></thead>
              <tbody>
                {freshFromProven.map((t) => (
                  <tr key={t.mint}>
                    <td className="font-mono-display">${t.symbol}</td>
                    <td>{t.ageHours.toFixed(1)}h</td>
                    <td className="font-mono-display" style={{ color: CAT_COLOR[t.category] }}>
                      {short(t.creator)} [{t.category}]
                    </td>
                    <td className="font-mono-display">{t.best}x</td>
                    <td className="font-mono-display">{t.peakMultiple}x</td>
                    <td>
                      <button
                        onClick={() => window.dispatchEvent(new CustomEvent("mi:goto-safety", { detail: t.mint }))}
                        className="text-xs text-[var(--signal-edge)] hover:underline"
                      >
                        safety
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Leaderboard by category */}
      {creators.length === 0 && !loading && !kvOff ? (
        <div className="card text-sm text-[var(--text-secondary)]">
          The ledger is empty — it fills as the scanner surfaces launches (and
          the alerts cron ingests them every run). Check back after a few scan
          cycles; track records need time and sample size to mean anything.
        </div>
      ) : (
        <div className="card overflow-x-auto">
          <h2 className="font-mono-display text-lg mb-1">CREATOR LEADERBOARD</h2>
          <table className="data-table">
            <thead>
              <tr>
                <th>Creator</th><th>Category</th><th>Tokens</th><th>Hits (2x+)</th>
                <th>Hit rate</th><th>Best</th><th>Avg peak</th><th>Recent</th>
              </tr>
            </thead>
            <tbody>
              {creators.map((c) => (
                <tr key={c.creator}>
                  <td>
                    <a href={`https://solscan.io/account/${c.creator}`} target="_blank" rel="noopener noreferrer"
                      className="font-mono-display text-[var(--signal-edge)] hover:underline">
                      {short(c.creator)}
                    </a>
                  </td>
                  <td className="font-mono-display text-xs" style={{ color: CAT_COLOR[c.category] }} title={CAT_DESC[c.category]}>
                    {c.category}
                  </td>
                  <td className="font-mono-display">{c.tokenCount}</td>
                  <td className="font-mono-display">{c.hits}</td>
                  <td className="font-mono-display">{Math.round(c.hitRate * 100)}%</td>
                  <td className="font-mono-display" style={{ color: c.bestMultiple >= 2 ? "var(--signal-long)" : undefined }}>
                    {c.bestMultiple}x
                  </td>
                  <td className="font-mono-display">{c.avgPeakMultiple}x</td>
                  <td className="text-xs text-[var(--text-secondary)]">
                    {c.recentTokens.slice(0, 3).map((t) => `$${t.symbol}`).join(" ")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="text-xs text-[var(--text-tertiary)] mt-2">
            Categories: PROVEN = 2+ winners, ≥40% hit rate · SERIAL = frequent, mixed · ONE-HIT · COOKING = live launch now · RUG-PRONE = most died · NEW = small sample.
            Hover a category for detail.
          </div>
        </div>
      )}
    </div>
  );
}
