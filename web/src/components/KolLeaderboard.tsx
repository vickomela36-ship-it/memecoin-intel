"use client";

import useSWR from "swr";
import { jsonFetcher } from "@/lib/utils";

interface KolStat {
  handle: string;
  callCount: number;
  hitRate: number;
  avgPeakMultiple: number;
  noReasoningRatio: number;
  nearTopRatio: number;
  grade: string;
  recent: { symbol: string; ca: string; peakMultiple: number; hadThesis: boolean }[];
}
interface Resp { kols?: KolStat[] }

const GRADE_COLOR: Record<string, string> = {
  SHARP: "var(--signal-long)",
  MIXED: "var(--signal-neutral)",
  FADE: "var(--signal-short)",
  NEW: "var(--text-tertiary)",
};

/**
 * KOL track-record leaderboard — who's actually right over time, built from
 * posts the social worker surfaced. Empty until XREACH_URL is connected and
 * posts have been ingested; nothing here is fabricated.
 */
export default function KolLeaderboard() {
  const { data } = useSWR<Resp>("/api/kol", (u: string) => jsonFetcher<Resp>(u), {
    refreshInterval: 120_000,
    revalidateOnFocus: false,
  });
  const kols = data?.kols ?? [];
  if (!kols.length) {
    return (
      <div className="card text-xs text-[var(--text-tertiary)]">
        <b className="text-[var(--text-secondary)]">KOL ledger empty.</b> Each time
        the social worker (XREACH_URL) surfaces posts for a token, their authors
        are logged here with the token&apos;s market cap at post time — building a
        real track record over time. Connect the worker to populate this.
      </div>
    );
  }

  return (
    <div className="card overflow-x-auto">
      <h3 className="font-display text-base font-semibold mb-1">KOL TRACK RECORD</h3>
      <table className="data-table">
        <thead>
          <tr><th>Handle</th><th>Grade</th><th>Calls</th><th>Hit ≥2x</th><th>Avg peak</th><th>No-reason</th><th>Near-top</th></tr>
        </thead>
        <tbody>
          {kols.map((k) => (
            <tr key={k.handle}>
              <td className="font-mono-display text-[var(--signal-edge)]">@{k.handle}</td>
              <td className="font-mono-display" style={{ color: GRADE_COLOR[k.grade] }}>{k.grade}</td>
              <td className="font-mono-display">{k.callCount}</td>
              <td className="font-mono-display">{Math.round(k.hitRate * 100)}%</td>
              <td className="font-mono-display">{k.avgPeakMultiple}x</td>
              <td className="font-mono-display" style={{ color: k.noReasoningRatio > 0.6 ? "var(--signal-short)" : undefined }}>
                {Math.round(k.noReasoningRatio * 100)}%
              </td>
              <td className="font-mono-display" style={{ color: k.nearTopRatio > 0.5 ? "var(--signal-short)" : undefined }}>
                {Math.round(k.nearTopRatio * 100)}%
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="text-xs text-[var(--text-tertiary)] mt-1">
        SHARP = ≥40% hit with reasoning · FADE = mostly posts near tops or with no reasoning. &quot;No-reason&quot; = share of calls with no thesis; &quot;near-top&quot; = share that fell below the post market cap.
      </div>
    </div>
  );
}
