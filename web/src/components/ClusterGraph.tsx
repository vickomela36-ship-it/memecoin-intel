"use client";

import type { FundingCluster } from "@/types";

/**
 * Bubblemaps-style linkage view of funding clusters. Each funder origin is a
 * hub; the wallets it funded orbit it, linked by lines. Hub size scales with
 * the cluster's combined % of supply — the number that actually matters, since
 * one entity funding many wallets is one entity, not a crowd.
 */
export default function ClusterGraph({ clusters }: { clusters: FundingCluster[] }) {
  if (!clusters.length) return null;

  const show = clusters.slice(0, 4);
  const CW = 150; // width per cluster cell
  const H = 150;
  const W = show.length * CW;

  return (
    <div className="overflow-x-auto">
      <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="img" aria-label="funding cluster linkage graph">
        {show.map((c, ci) => {
          const cx = ci * CW + CW / 2;
          const cy = H / 2;
          const pct = c.pctOfSupply ?? 0;
          const hubR = Math.max(10, Math.min(30, 8 + pct * 1.5));
          const sat = Math.min(c.holders, 8);
          const orbit = 52;
          const danger = c.holders >= 4;
          const hubColor = danger ? "var(--signal-short)" : "var(--signal-neutral)";
          return (
            <g key={ci}>
              {Array.from({ length: sat }).map((_, i) => {
                const ang = (i / sat) * Math.PI * 2 - Math.PI / 2;
                const sx = cx + Math.cos(ang) * orbit;
                const sy = cy + Math.sin(ang) * orbit;
                return (
                  <g key={i}>
                    <line x1={cx} y1={cy} x2={sx} y2={sy} stroke="var(--border-subtle)" strokeWidth={1} />
                    <circle cx={sx} cy={sy} r={4} fill="var(--text-tertiary)" />
                  </g>
                );
              })}
              <circle cx={cx} cy={cy} r={hubR} fill={hubColor} opacity={0.85} />
              <text x={cx} y={cy + 3} textAnchor="middle" fontSize={9} fill="var(--bg-primary)" fontFamily="var(--font-jetbrains), monospace">
                {pct.toFixed(0)}%
              </text>
              <text x={cx} y={H - 22} textAnchor="middle" fontSize={9} fill="var(--text-secondary)" fontFamily="var(--font-jetbrains), monospace">
                {c.origin}
              </text>
              <text x={cx} y={H - 10} textAnchor="middle" fontSize={9} fill="var(--text-tertiary)" fontFamily="var(--font-jetbrains), monospace">
                {c.holders} wallets{c.withinHours !== null ? ` · ${c.withinHours}h` : ""}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
