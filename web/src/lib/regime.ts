// Regime dial. Pure functions.
// (Market-structure / swing engine lives in lib/ta.ts and is consumed by the
//  per-token chart card; this file is only the market-wide regime composite.)

// ── Regime composite ──────────────────────────────────────────────────────

export type RegimeState = "HOT" | "NEUTRAL" | "COLD";

export interface RegimeInputs {
  breadthPct: number; // % of scanned tokens green
  medianH24: number; // median 24h move across scanned tokens
  majorsUp: number; // how many of BTC/ETH/SOL are trending up (0-3)
}

export interface RegimeResult {
  state: RegimeState;
  score: number; // 0-100
  inputs: RegimeInputs;
  guidance: string;
  rotation: string;
}

export function computeRegime(inp: RegimeInputs): RegimeResult {
  // Breadth 0-40, median move 0-30, majors 0-30
  const breadthScore = Math.min(40, (inp.breadthPct / 60) * 40);
  const moveScore = Math.min(30, Math.max(0, (inp.medianH24 + 10) / 30 * 30));
  const majorsScore = (inp.majorsUp / 3) * 30;
  const score = Math.round(breadthScore + moveScore + majorsScore);

  let state: RegimeState;
  if (score >= 62) state = "HOT";
  else if (score >= 38) state = "NEUTRAL";
  else state = "COLD";

  const guidance =
    state === "HOT"
      ? "Conditions favor risk: larger size, more trades, earlier entries, weighted toward memecoins."
      : state === "COLD"
        ? "Preserve capital: reduce deployment, fewer trades, only your highest-conviction setups. In bad conditions, not losing IS winning."
        : "Mixed: standard size, be selective, let A-setups come to you.";

  const rotation =
    state === "COLD"
      ? "Rotate down the risk curve: memecoins → utility → ownership → stables."
      : state === "HOT"
        ? "Risk-on: memecoins and fresh launches carry the returns here."
        : "Balanced: keep dry powder, rotate into strength.";

  return { state, score, inputs: inp, guidance, rotation };
}
