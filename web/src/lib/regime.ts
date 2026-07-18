// Market-structure engine + regime dial. Pure functions.

export type TrendState = "UPTREND" | "DOWNTREND" | "RANGING" | "REVERSAL FORMING";

export interface StructureResult {
  state: TrendState;
  detail: string;
}

/** Swing highs/lows from close series → higher-highs/higher-lows etc. */
export function marketStructure(closes: number[]): StructureResult {
  if (closes.length < 8) return { state: "RANGING", detail: "not enough data" };

  // Fractal swing points: local extrema over a 2-bar window
  const highs: number[] = [];
  const lows: number[] = [];
  for (let i = 2; i < closes.length - 2; i++) {
    const w = closes.slice(i - 2, i + 3);
    if (closes[i] === Math.max(...w)) highs.push(closes[i]);
    if (closes[i] === Math.min(...w)) lows.push(closes[i]);
  }
  const last2 = <T,>(a: T[]) => a.slice(-2);
  const [h1, h2] = last2(highs);
  const [l1, l2] = last2(lows);

  const hh = h2 > h1;
  const hl = l2 > l1;
  const lh = h2 < h1;
  const ll = l2 < l1;

  // Break of structure: latest close breaks the last swing high/low
  const lastClose = closes[closes.length - 1];
  const brokeUp = highs.length > 0 && lastClose > Math.max(...highs.slice(-2, -1), h1 ?? -Infinity);

  if (highs.length >= 2 && lows.length >= 2) {
    if (hh && hl) return { state: "UPTREND", detail: "higher highs + higher lows" };
    if (lh && ll) {
      if (brokeUp) return { state: "REVERSAL FORMING", detail: "downtrend structure just broke to the upside" };
      return { state: "DOWNTREND", detail: "lower highs + lower lows" };
    }
  }
  return { state: "RANGING", detail: "no clean higher-high/lower-low sequence" };
}

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
