// Challenge pace math + tier-based position sizing.
// Direct port of the Python challenge_tracker module.

import type { ChallengeState } from "./storage";

export interface SizingRule {
  label: string;
  fraction: number; // % of current bankroll
  stopPct: number;
  tp1Mult: number;
  tp2Mult: number;
  why: string;
}

export const SIZING_RULES: Record<string, SizingRule> = {
  A: {
    label: "A-grade recovery",
    fraction: 0.4,
    stopPct: 15,
    tp1Mult: 1.6,
    tp2Mult: 2.5,
    why: "Highest win-rate setup. Big size, tight stop, modest targets.",
  },
  B: {
    label: "B-grade recovery",
    fraction: 0.25,
    stopPct: 18,
    tp1Mult: 1.8,
    tp2Mult: 3.0,
    why: "Solid setup. Moderate size.",
  },
  "3x POSSIBLE": {
    label: "3x degen play",
    fraction: 0.15,
    stopPct: 22,
    tp1Mult: 1.8,
    tp2Mult: 3.0,
    why: "Moderate-risk degen. Controlled size.",
  },
  "5x POTENTIAL": {
    label: "5x degen play",
    fraction: 0.2,
    stopPct: 25,
    tp1Mult: 2.0,
    tp2Mult: 5.0,
    why: "High risk. Wider stop for volatility, bigger targets.",
  },
  "10x RUNNER": {
    label: "10x degen play",
    fraction: 0.12,
    stopPct: 30,
    tp1Mult: 3.0,
    tp2Mult: 10.0,
    why: "Very high risk. Small size, huge asymmetry.",
  },
  "100x MOONSHOT": {
    label: "100x moonshot",
    fraction: 0.07,
    stopPct: 40,
    tp1Mult: 5.0,
    tp2Mult: 20.0,
    why: "Lottery ticket. Never size beyond 7% — most go to zero.",
  },
};

const DEFAULT_RULE: SizingRule = {
  label: "Unrated play",
  fraction: 0.1,
  stopPct: 20,
  tp1Mult: 2.0,
  tp2Mult: 4.0,
  why: "No grade — default conservative sizing.",
};

export interface PositionPlan extends SizingRule {
  sizeUsd: number;
  maxLossUsd: number;
}

export function positionPlan(bankroll: number, key: string): PositionPlan {
  const rule = SIZING_RULES[key] ?? DEFAULT_RULE;
  const sizeUsd = bankroll * rule.fraction;
  return {
    ...rule,
    sizeUsd,
    maxLossUsd: sizeUsd * (rule.stopPct / 100),
  };
}

// ── Pace math ─────────────────────────────────────────────────────────────

export function daysElapsed(state: ChallengeState): number {
  if (!state.startedAt) return 0;
  return Math.max(0, (Date.now() - state.startedAt) / 86_400_000);
}

export function requiredDailyMultiple(
  current: number,
  target: number,
  daysLeft: number
): number {
  if (current <= 0 || daysLeft <= 0) return Infinity;
  if (current >= target) return 1;
  return Math.pow(target / current, 1 / daysLeft);
}

export function paceBankroll(state: ChallengeState, day: number): number {
  const totalMult = state.target / state.startBankroll;
  return (
    state.startBankroll *
    Math.pow(totalMult, Math.min(day, state.days) / state.days)
  );
}

export type PaceStatus = "TARGET HIT" | "AHEAD OF PACE" | "BEHIND PACE" | "CRITICAL";

export function paceStatus(state: ChallengeState): {
  status: PaceStatus;
  onPace: number;
  reqMult: number;
  elapsed: number;
  daysLeft: number;
} {
  const elapsed = daysElapsed(state);
  const daysLeft = Math.max(0.01, state.days - elapsed);
  const onPace = paceBankroll(state, elapsed);
  const reqMult = requiredDailyMultiple(
    state.currentBankroll,
    state.target,
    daysLeft
  );

  let status: PaceStatus;
  if (state.currentBankroll >= state.target) status = "TARGET HIT";
  else if (state.currentBankroll >= onPace) status = "AHEAD OF PACE";
  else if (state.currentBankroll >= onPace * 0.6) status = "BEHIND PACE";
  else status = "CRITICAL";

  return { status, onPace, reqMult, elapsed, daysLeft };
}

/** A day's suggested play structure: core play + degen shots + reserve. */
export function dailyPlayPlan(bankroll: number) {
  const plays = [
    { slot: "Core play (A/B grade)", ...positionPlan(bankroll, "A") },
    { slot: "Degen shot #1", ...positionPlan(bankroll, "5x POTENTIAL") },
    { slot: "Degen shot #2 (optional)", ...positionPlan(bankroll, "10x RUNNER") },
  ];
  const reservePct =
    100 - plays.reduce((a, p) => a + p.fraction * 100, 0);
  return { plays, reservePct: Math.max(0, reservePct) };
}
