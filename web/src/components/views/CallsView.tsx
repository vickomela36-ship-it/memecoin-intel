"use client";

import { useEffect, useState } from "react";
import useSWR from "swr";
import { jsonFetcher } from "@/lib/utils";
import FollowStream from "@/components/FollowStream";

interface CallStat {
  ca: string;
  symbol: string;
  firstCaller: string;
  source: string;
  callMcap: number;
  callAt: number;
  peakMultiple: number;
  currentMultiple: number;
  ageHours: number;
}
interface CallsResp { calls: CallStat[]; error?: string }

function multColor(m: number): string {
  if (m >= 2) return "var(--signal-long)";
  if (m >= 1) return "var(--signal-neutral)";
  return "var(--signal-short)";
}

/**
 * Call ledger — first-caller attribution inside your own circle. If a CA was
 * surfaced at 100k and it's now at 1M, this records who called it and when,
 * and shows the multiple since. Ingest is a webhook (point a Telegram group at
 * it) or the manual add below. This is an information stream, not a buy signal.
 */
export default function CallsView() {
  const { data, mutate } = useSWR<CallsResp>("/api/calls", (u: string) => jsonFetcher<CallsResp>(u), {
    refreshInterval: 60_000,
  });
  const [ca, setCa] = useState("");
  const [caller, setCaller] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const saved = localStorage.getItem("mi_caller_handle");
    if (saved) setCaller(saved);
  }, []);

  async function add() {
    const m = ca.trim().match(/[A-Za-z0-9]{32,44}/);
    if (!m) { setStatus("Paste a valid contract address."); return; }
    setBusy(true);
    setStatus(null);
    if (caller.trim()) localStorage.setItem("mi_caller_handle", caller.trim());
    try {
      const r = await fetch("/api/calls", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ca: m[0], caller: caller.trim() || "me", source: "manual" }),
      });
      const j = await r.json();
      if (!r.ok) setStatus(j.error ?? "Failed to log call.");
      else {
        setStatus(j.alreadyCalled ? `Already called first by @${j.firstCaller} — updated the market cap.` : `Logged. You're the first caller for $${j.stat?.symbol}.`);
        setCa("");
        mutate();
      }
    } catch {
      setStatus("Ingest unreachable.");
    } finally {
      setBusy(false);
    }
  }

  const calls = data?.calls ?? [];

  return (
    <div className="space-y-3">
      <div className="text-xs text-[var(--text-tertiary)] border border-[var(--border-subtle)] rounded-card px-3 py-2">
        Who called it first, at what market cap, and how it did since — a real track
        record inside your circle. Point a Telegram group or webhook at{" "}
        <code>POST /api/calls</code> to auto-log calls, or add one below. This is an
        information stream; it is not a buy signal.
      </div>

      <div className="card space-y-2">
        <div className="flex gap-2 flex-wrap">
          <input
            value={caller}
            onChange={(e) => setCaller(e.target.value)}
            placeholder="your handle"
            className="w-32 bg-[var(--bg-elevated)] rounded-input px-3 py-2 text-sm border border-[var(--border-subtle)] focus:border-[var(--border-active)] outline-none font-mono-display"
          />
          <input
            value={ca}
            onChange={(e) => setCa(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && add()}
            placeholder="contract address you're calling…"
            className="flex-1 min-w-[180px] bg-[var(--bg-elevated)] rounded-input px-3 py-2 text-sm border border-[var(--border-subtle)] focus:border-[var(--border-active)] outline-none font-mono-display"
          />
          <button
            onClick={add}
            disabled={busy}
            className="font-mono-display text-sm px-4 py-2 rounded-btn disabled:opacity-50"
            style={{ background: "var(--signal-edge)", color: "var(--bg-primary)" }}
          >
            {busy ? "LOGGING…" : "LOG CALL"}
          </button>
        </div>
        {status && <div className="text-xs text-[var(--text-secondary)]">{status}</div>}
      </div>

      {calls.length === 0 ? (
        <div className="card text-sm text-[var(--text-secondary)]">
          No calls logged yet. Log one above, or wire a group webhook to{" "}
          <code>/api/calls</code>.
        </div>
      ) : (
        <div className="card overflow-x-auto">
          <table className="data-table">
            <thead>
              <tr><th>Token</th><th>First caller</th><th>Called @</th><th>Now</th><th>Peak</th><th>When</th><th></th></tr>
            </thead>
            <tbody>
              {calls.map((c) => (
                <tr key={c.ca}>
                  <td className="font-mono-display">${c.symbol}</td>
                  <td className="font-mono-display text-[var(--signal-edge)]">@{c.firstCaller}</td>
                  <td className="font-mono-display">${(c.callMcap / 1000).toFixed(0)}K</td>
                  <td className="font-mono-display" style={{ color: multColor(c.currentMultiple) }}>{c.currentMultiple}x</td>
                  <td className="font-mono-display" style={{ color: multColor(c.peakMultiple) }}>{c.peakMultiple}x</td>
                  <td className="text-[var(--text-tertiary)]">
                    {c.ageHours < 24 ? `${c.ageHours.toFixed(0)}h` : `${(c.ageHours / 24).toFixed(0)}d`} ago
                  </td>
                  <td>
                    <button
                      onClick={() => window.dispatchEvent(new CustomEvent("mi:goto-safety", { detail: c.ca }))}
                      className="text-xs text-[var(--signal-edge)] hover:underline"
                    >
                      check
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="text-xs text-[var(--text-tertiary)] mt-1">
            Peak/now are market-cap multiples vs the call. First-caller is attributed once and never overwritten.
          </div>
        </div>
      )}

      <FollowStream />
    </div>
  );
}
