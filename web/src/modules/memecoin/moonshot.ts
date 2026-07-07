// Moonshot (degen) scoring — port of the Python compute_moonshot.
// Inverted logic: deeper dips, lower mcap, accelerating volume = higher score.

import type { DexPair, ScoreComponent } from "@/types";
import { clamp } from "@/lib/utils";

export interface MoonshotResult {
  total: number;
  tier: "100x MOONSHOT" | "10x RUNNER" | "5x POTENTIAL" | "3x POSSIBLE" | "LOW POTENTIAL";
  riskLevel: "EXTREME" | "VERY HIGH" | "HIGH" | "MODERATE-HIGH";
  components: ScoreComponent[];
  reasons: string[];
  warnings: string[];
}

function num(v: unknown): number {
  const n = Number(v);
  return isFinite(n) ? n : 0;
}

export function computeMoonshot(pair: DexPair): MoonshotResult {
  const m5 = num(pair.priceChange?.m5);
  const h1 = num(pair.priceChange?.h1);
  const h6 = num(pair.priceChange?.h6);
  const h24 = num(pair.priceChange?.h24);
  const vol5m = num(pair.volume?.m5);
  const volH1 = num(pair.volume?.h1);
  const vol24 = num(pair.volume?.h24);
  const liq = num(pair.liquidity?.usd);
  const fdv = num(pair.fdv);

  const reasons: string[] = [];
  const warnings: string[] = [];
  const components: ScoreComponent[] = [];

  // 1. Dip depth (30%)
  let dip: number;
  if (h24 < -70) { dip = 100; reasons.push(`24h crash ${h24.toFixed(0)}% — max dip opportunity`); }
  else if (h24 < -50) { dip = 85; reasons.push(`24h dump ${h24.toFixed(0)}% — deep dip`); }
  else if (h24 < -35) { dip = 65; reasons.push(`24h decline ${h24.toFixed(0)}%`); }
  else if (h6 < -30) { dip = 60; reasons.push(`6h drop ${h6.toFixed(0)}%`); }
  else if (h6 < -20) dip = 45;
  else if (h1 < -15) dip = 40;
  else if (h24 < -20) dip = 35;
  else dip = 10;
  components.push({ name: "Dip depth", weightPct: 30, score: dip, detail: `1h ${h1.toFixed(0)}% / 6h ${h6.toFixed(0)}% / 24h ${h24.toFixed(0)}%` });

  // 2. Market cap (25%)
  let mcap: number;
  if (fdv <= 0) mcap = 50;
  else if (fdv < 100_000) { mcap = 100; reasons.push(`Nano-cap $${(fdv / 1000).toFixed(0)}K FDV — max moon potential`); }
  else if (fdv < 500_000) { mcap = 90; reasons.push(`Micro-cap $${(fdv / 1000).toFixed(0)}K FDV`); }
  else if (fdv < 2_000_000) mcap = 70;
  else if (fdv < 10_000_000) mcap = 45;
  else if (fdv < 50_000_000) mcap = 25;
  else mcap = 10;
  components.push({ name: "Micro-cap", weightPct: 25, score: mcap, detail: fdv > 0 ? `$${(fdv / 1000).toFixed(0)}K FDV` : "unknown" });

  // 3. Volume acceleration (20%): 5m pace vs hourly, hourly vs 24h
  const hourlyRatio = vol24 > 0 && volH1 > 0 ? (volH1 * 24) / vol24 : 0;
  const instantRatio = volH1 > 0 && vol5m > 0 ? (vol5m * 12) / volH1 : 0;
  let volScore: number;
  if (instantRatio >= 3 && vol5m > 1000) { volScore = 100; reasons.push(`Volume accelerating NOW (${instantRatio.toFixed(1)}x 5m pace)`); }
  else if (hourlyRatio >= 5) { volScore = 95; reasons.push(`Volume spike ${hourlyRatio.toFixed(1)}x vs 24h avg`); }
  else if (instantRatio >= 2 && vol5m > 500) volScore = 85;
  else if (hourlyRatio >= 3) volScore = 80;
  else if (hourlyRatio >= 2) volScore = 60;
  else if (hourlyRatio >= 1.5) volScore = 40;
  else volScore = 20;
  components.push({ name: "Volume acceleration", weightPct: 20, score: volScore, detail: `${instantRatio.toFixed(1)}x instant / ${hourlyRatio.toFixed(1)}x hourly` });

  // 4. Volatility (10%)
  const swing = Math.abs(h1) + Math.abs(h6);
  const volat = swing >= 80 ? 100 : swing >= 50 ? 80 : swing >= 30 ? 60 : swing >= 15 ? 40 : 15;
  components.push({ name: "Volatility", weightPct: 10, score: volat, detail: `${swing.toFixed(0)}% combined swing` });

  // 5. Momentum shift (10%): short frames green against a red bigger frame
  let momentum: number;
  if (m5 > 2 && (h6 < -15 || h24 < -25)) { momentum = 85; reasons.push(`Recovery igniting: 5m +${m5.toFixed(1)}% against ${h6.toFixed(0)}% 6h`); }
  else if (h1 > 5 && (h6 < -20 || h24 < -30)) { momentum = 75; reasons.push(`Momentum shift: 1h +${h1.toFixed(1)}%`); }
  else if (h1 > 0 && h6 < -10) momentum = 50;
  else momentum = 20;
  components.push({ name: "Momentum shift", weightPct: 10, score: momentum, detail: `5m ${m5.toFixed(1)}% / 1h ${h1.toFixed(1)}%` });

  // 6. Buy pressure (5%)
  let ratio = 0;
  for (const tf of ["m5", "h1"] as const) {
    const t = pair.txns?.[tf];
    const buys = num(t?.buys);
    const sells = num(t?.sells);
    if (sells > 0) ratio = Math.max(ratio, buys / sells);
  }
  const bp = ratio >= 3 ? 100 : ratio >= 2 ? 80 : ratio >= 1.5 ? 60 : ratio >= 1 ? 40 : 15;
  if (ratio >= 2) reasons.push(`Strong buy pressure (${ratio.toFixed(1)}x buys/sells)`);
  components.push({ name: "Buy pressure", weightPct: 5, score: bp, detail: ratio > 0 ? `${ratio.toFixed(1)}x` : "—" });

  let total =
    dip * 0.3 + mcap * 0.25 + volScore * 0.2 + volat * 0.1 + momentum * 0.1 + bp * 0.05;

  // Liquidity/FDV exit-trap adjustment
  if (fdv > 0 && liq > 0) {
    const liqRatio = liq / fdv;
    if (liqRatio < 0.02) {
      total -= 15;
      warnings.push(`Exit trap: liquidity only ${(liqRatio * 100).toFixed(1)}% of FDV`);
    } else if (liqRatio >= 0.08) {
      total += 5;
      reasons.push(`Healthy liquidity (${(liqRatio * 100).toFixed(0)}% of FDV)`);
    }
  }
  total = clamp(total);

  // Tier
  let tier: MoonshotResult["tier"];
  let riskLevel: MoonshotResult["riskLevel"];
  if (total >= 80 && fdv < 500_000) [tier, riskLevel] = ["100x MOONSHOT", "EXTREME"];
  else if (total >= 70 && fdv < 2_000_000) [tier, riskLevel] = ["10x RUNNER", "VERY HIGH"];
  else if (total >= 55) [tier, riskLevel] = ["5x POTENTIAL", "HIGH"];
  else if (total >= 45) [tier, riskLevel] = ["3x POSSIBLE", "MODERATE-HIGH"];
  else [tier, riskLevel] = ["LOW POTENTIAL", "HIGH"];

  if (liq < 10_000) warnings.push(`Very low liquidity $${(liq / 1000).toFixed(1)}K — slippage risk`);
  if (vol24 < 10_000) warnings.push(`Very low 24h volume — difficult to exit`);

  return { total: Math.round(total), tier, riskLevel, components, reasons, warnings };
}
