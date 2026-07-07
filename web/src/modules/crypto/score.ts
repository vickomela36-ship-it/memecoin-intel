import type { CryptoScoreRow, GeckoCoin, ScoreComponent } from "@/types";
import { clamp } from "@/lib/utils";

/**
 * Composite 0-100 score from fields CoinGecko's free tier actually returns.
 *
 * Honest weighting (funding rates / on-chain data are NOT free — we do not
 * fake them; the breakdown below is exactly what drives the number):
 *   24h momentum vs 7d volatility  30%
 *   1h velocity                    20%
 *   volume / market cap            25%
 *   7d trend                       25%
 */
export function computeCryptoScore(coin: GeckoCoin): CryptoScoreRow {
  const spark = coin.sparkline_in_7d?.price ?? [];
  const p1h = coin.price_change_percentage_1h_in_currency ?? 0;
  const p24 = coin.price_change_percentage_24h_in_currency ?? 0;
  const p7d = coin.price_change_percentage_7d_in_currency ?? 0;

  // 7d realized volatility from sparkline (hourly points)
  let vol7d = 2; // default daily-ish % when sparkline missing
  if (spark.length > 24) {
    const rets: number[] = [];
    for (let i = 1; i < spark.length; i++) {
      if (spark[i - 1] > 0) rets.push(spark[i] / spark[i - 1] - 1);
    }
    const mean = rets.reduce((a, b) => a + b, 0) / rets.length;
    const varr = rets.reduce((a, b) => a + (b - mean) ** 2, 0) / rets.length;
    vol7d = Math.sqrt(varr) * Math.sqrt(24) * 100; // daily vol in %
    if (!isFinite(vol7d) || vol7d <= 0) vol7d = 2;
  }

  const components: ScoreComponent[] = [];

  // 1. 24h momentum normalized by volatility: ±2 daily-vols maps to 0..100
  const momoNorm = clamp(50 + (p24 / (vol7d * 2)) * 50);
  components.push({
    name: "24h momentum (vol-adjusted)",
    weightPct: 30,
    score: momoNorm,
    detail: `${p24.toFixed(1)}% vs ${vol7d.toFixed(1)}% daily vol`,
  });

  // 2. 1h velocity: ±1.5% maps to 0..100
  const velocity = clamp(50 + (p1h / 1.5) * 50);
  components.push({
    name: "1h velocity",
    weightPct: 20,
    score: velocity,
    detail: `${p1h.toFixed(2)}% last hour`,
  });

  // 3. Volume / market cap: 0.25 turnover = max conviction
  const turnover = coin.market_cap > 0 ? coin.total_volume / coin.market_cap : 0;
  const volScore = clamp((turnover / 0.25) * 100);
  components.push({
    name: "Volume / market cap",
    weightPct: 25,
    score: volScore,
    detail: `${(turnover * 100).toFixed(1)}% daily turnover`,
  });

  // 4. 7d trend: ±15% maps to 0..100
  const trend = clamp(50 + (p7d / 15) * 50);
  components.push({
    name: "7d trend",
    weightPct: 25,
    score: trend,
    detail: `${p7d.toFixed(1)}% over 7 days`,
  });

  const score = clamp(
    components.reduce((acc, c) => acc + c.score * (c.weightPct / 100), 0)
  );

  let label: string;
  let direction: CryptoScoreRow["direction"];
  if (score >= 80) [label, direction] = ["STRONG BULLISH", "bullish"];
  else if (score >= 60) [label, direction] = ["BULLISH", "bullish"];
  else if (score >= 40) [label, direction] = ["NEUTRAL", "neutral"];
  else if (score >= 20) [label, direction] = ["BEARISH", "bearish"];
  else [label, direction] = ["STRONG BEARISH", "bearish"];

  // Downsample sparkline to ~40 points for cheap rendering
  const step = Math.max(1, Math.floor(spark.length / 40));
  const sparkline = spark.filter((_, i) => i % step === 0);

  return {
    id: coin.id,
    symbol: coin.symbol.toUpperCase(),
    name: coin.name,
    price: coin.current_price,
    score: Math.round(score),
    direction,
    label,
    components,
    sparkline,
    change24h: p24,
  };
}
