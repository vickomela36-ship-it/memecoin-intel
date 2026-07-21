"use client";

import { useEffect, useRef, useState } from "react";
import SafetyCard from "@/components/SafetyCard";
import { addWatch } from "@/lib/storage";
import { jsonFetcher } from "@/lib/utils";
import type { SafetyReport } from "@/types";

interface SocialResp {
  configured: boolean;
  hint?: string;
  timing?: { label: string; detail: string };
  humanCount?: number;
  botCount?: number;
  human?: { author: string; followers: number; text: string; createdAt: number; url?: string; earlyScore: number; hasThesis: boolean }[];
}

function SocialSection({ mint, symbol }: { mint: string; symbol: string }) {
  const [data, setData] = useState<SocialResp | null>(null);
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const r = await jsonFetcher<SocialResp>(`/api/social?q=${encodeURIComponent(mint)}`);
      setData(r);
    } catch {
      setData({ configured: true, hint: "Social worker unreachable." });
    } finally {
      setLoading(false);
    }
  }

  if (!data) {
    return (
      <div className="card">
        <button
          onClick={load}
          disabled={loading}
          className="text-xs font-mono-display px-3 py-1.5 rounded-btn border border-[var(--border-active)] text-[var(--signal-edge)] disabled:opacity-50"
        >
          {loading ? "READING X…" : `🐦 Social signal for $${symbol}`}
        </button>
      </div>
    );
  }

  if (!data.configured) {
    return (
      <div className="card text-xs text-[var(--text-tertiary)]">
        <b className="text-[var(--text-secondary)]">Social analysis not connected.</b>{" "}
        X data can&apos;t run on Vercel (X blocks scrapers; Agent-Reach needs login
        cookies + a long-running host). Self-host an Agent-Reach worker and set
        the <code>XREACH_URL</code> env var — then this section filters bots and
        surfaces early, credible posters. The analysis logic is already built and
        waiting for a data source; nothing here is faked.
      </div>
    );
  }

  return (
    <div className="card space-y-2">
      <div className="flex items-center justify-between">
        <h3 className="font-mono-display text-base">SOCIAL SIGNAL</h3>
        {data.timing && (
          <span
            className="font-mono-display text-xs px-2 py-0.5 rounded-input"
            style={{
              color: data.timing.label === "EARLY" ? "var(--signal-long)" : data.timing.label === "LATE" ? "var(--signal-short)" : "var(--signal-neutral)",
              border: "1px solid var(--border-subtle)",
            }}
          >
            {data.timing.label}
          </span>
        )}
      </div>
      {data.timing && <div className="text-xs text-[var(--text-tertiary)]">{data.timing.detail}</div>}
      <div className="text-xs text-[var(--text-secondary)]">
        {data.humanCount ?? 0} credible human posts · {data.botCount ?? 0} bots filtered out.
        Ranked by early + small-account + real thesis, not engagement.
      </div>
      {(data.human ?? []).map((p, i) => (
        <div key={i} className="rounded-input px-3 py-1.5 text-xs" style={{ background: "var(--bg-elevated)" }}>
          <div className="flex justify-between">
            <a href={p.url ?? `https://x.com/${p.author}`} target="_blank" rel="noopener noreferrer"
              className="font-mono-display text-[var(--signal-edge)] hover:underline">
              @{p.author}
            </a>
            <span className="text-[var(--text-tertiary)]">
              {p.followers.toLocaleString()} followers · score {p.earlyScore}{p.hasThesis && " · thesis"}
            </span>
          </div>
          <div className="text-[var(--text-secondary)] mt-0.5">{p.text.slice(0, 200)}</div>
        </div>
      ))}
    </div>
  );
}

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
    // A redirect from another tab stashes the CA before this view mounts —
    // consume it, paste it into the bar, and run the check automatically.
    const pending = sessionStorage.getItem("mi_pending_safety");
    if (pending) {
      sessionStorage.removeItem("mi_pending_safety");
      setInput(pending);
      void run(false, pending);
    }
    // Live listener covers redirects fired while this view is already open
    const onGoto = (e: Event) => {
      const addr = (e as CustomEvent<string>).detail;
      if (!addr) return;
      sessionStorage.removeItem("mi_pending_safety");
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
      setError(
        "The free safety sources (Rugcheck/DexScreener) are rate-limited right now. Results cache for 5 minutes once they answer — wait ~30s and check again."
      );
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
          <SocialSection mint={report.mint} symbol={report.symbol} />
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
