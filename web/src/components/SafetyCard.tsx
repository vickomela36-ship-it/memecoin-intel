"use client";

import { useState } from "react";
import type { SafetyReport, SafetyVerdict } from "@/types";
import { timeAgo } from "@/lib/utils";

const V_COLOR: Record<SafetyVerdict, string> = {
  pass: "var(--signal-long)",
  warn: "var(--signal-neutral)",
  fail: "var(--signal-short)",
  unknown: "var(--text-tertiary)",
};
const V_ICON: Record<SafetyVerdict, string> = {
  pass: "✓",
  warn: "!",
  fail: "✕",
  unknown: "?",
};
const V_LABEL: Record<SafetyVerdict, string> = {
  pass: "LOOKS CLEAN",
  warn: "PROCEED WITH CAUTION",
  fail: "RED FLAGS PRESENT",
  unknown: "INSUFFICIENT DATA",
};

export default function SafetyCard({
  report,
  onDeepScan,
  deepLoading,
}: {
  report: SafetyReport;
  onDeepScan?: () => void;
  deepLoading?: boolean;
}) {
  const [open, setOpen] = useState(true);
  const clr = V_COLOR[report.verdict];
  const fails = report.checks.filter((c) => c.verdict === "fail").length;
  const warns = report.checks.filter((c) => c.verdict === "warn").length;

  return (
    <div className="card" style={{ borderColor: clr }}>
      {/* Verdict header */}
      <button onClick={() => setOpen(!open)} className="w-full text-left">
        <div className="flex items-center justify-between gap-2 flex-wrap">
          <div className="flex items-center gap-2">
            <span
              className="font-mono-display text-sm px-2 py-0.5 rounded-input"
              style={{ color: clr, border: `1px solid ${clr}`, background: `${clr}15` }}
            >
              {V_ICON[report.verdict]} {V_LABEL[report.verdict]}
            </span>
            <span className="font-mono-display text-lg">${report.symbol}</span>
          </div>
          <span className="text-xs text-[var(--text-tertiary)] font-mono-display">
            {fails} fail · {warns} warn · {report.sources.join(", ") || "no sources"} · {open ? "▾" : "▸"}
          </span>
        </div>
      </button>

      {open && (
        <div className="mt-3 space-y-1.5">
          {report.checks.map((c) => (
            <details key={c.id} className="rounded-input" style={{ background: "var(--bg-elevated)" }}>
              <summary className="flex items-center justify-between gap-2 px-3 py-1.5 cursor-pointer text-sm">
                <span className="flex items-center gap-2">
                  <span
                    className="font-mono-display w-4 text-center"
                    style={{ color: V_COLOR[c.verdict] }}
                  >
                    {V_ICON[c.verdict]}
                  </span>
                  <span>{c.label}</span>
                </span>
                <span className="font-mono-display text-xs" style={{ color: V_COLOR[c.verdict] }}>
                  {c.value}
                </span>
              </summary>
              <div className="px-9 pb-2 text-xs text-[var(--text-secondary)]">{c.explain}</div>
            </details>
          ))}

          {/* Creator */}
          <div className="rounded-input px-3 py-2 text-sm" style={{ background: "var(--bg-elevated)" }}>
            <span className="text-[var(--text-secondary)]">Creator wallet:</span>{" "}
            {report.creator.address ? (
              <a
                href={`https://solscan.io/account/${report.creator.address}`}
                target="_blank"
                rel="noopener noreferrer"
                className="font-mono-display text-[var(--signal-edge)] hover:underline"
              >
                {report.creator.address.slice(0, 4)}…{report.creator.address.slice(-4)}
              </a>
            ) : (
              <span className="text-[var(--text-tertiary)]">unknown</span>
            )}{" "}
            <span
              className="font-mono-display text-xs"
              style={{
                color:
                  report.creator.status === "distributing"
                    ? "var(--signal-short)"
                    : report.creator.status === "holding"
                      ? "var(--signal-long)"
                      : "var(--text-tertiary)",
              }}
            >
              [{report.creator.status}]
            </span>
            <div className="text-xs text-[var(--text-tertiary)] mt-0.5">{report.creator.note}</div>
          </div>

          {/* Deep scan */}
          {report.deep?.ran ? (
            <div className="rounded-input px-3 py-2 text-xs" style={{ background: "var(--bg-elevated)" }}>
              <b className="text-[var(--text-secondary)]">Deep scan:</b> {report.deep.note}
              {report.deep.fundingClusters.length > 0 && (
                <ul className="mt-1 space-y-0.5">
                  {report.deep.fundingClusters.map((c, i) => (
                    <li key={i} style={{ color: "var(--signal-short)" }}>
                      ⚠ {c.holders} holders funded from {c.origin}
                      {c.withinHours !== null && ` within ${c.withinHours}h`} (~{c.pctOfSupply}% supply)
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ) : onDeepScan ? (
            <button
              onClick={onDeepScan}
              disabled={deepLoading}
              className="text-xs font-mono-display px-3 py-1.5 rounded-btn border border-[var(--border-active)] text-[var(--signal-edge)] disabled:opacity-50"
            >
              {deepLoading ? "TRACING WALLETS…" : "🔬 DEEP SCAN — fresh wallets + funding origins"}
            </button>
          ) : null}

          <div className="text-xs text-[var(--text-tertiary)] pt-1">
            Checked {timeAgo(report.fetchedAt)}. Every flag is explainable — expand any row.
            This surfaces information; it does not predict outcomes. Not financial advice.
          </div>
        </div>
      )}
    </div>
  );
}
