// Binary market engine for YES/NO prediction platforms.
//
// The probability model is de-vigged bookmaker consensus (books are the
// sharpest free estimate on earth), blended with ELO as a sanity check.
// The edge is not "beat the books" — it's using the books' own numbers
// against softer prediction-market pricing.

import type {
  BinaryQuestion,
  FootballMatch,
  MatchEdge,
  OddsEvent,
} from "@/types";
import { EloBook } from "./elo";

/** Threshold band in cents around fair value before YES/NO has value. */
const BAND_CENTS = 4;

function normalize(name: string): string {
  return name
    .toLowerCase()
    .replace(/\b(fc|cf|afc|sl|bv|ssc)\b/g, "")
    .replace(/[^a-z ]/g, "")
    .trim();
}

function matchOdds(match: FootballMatch, odds: OddsEvent[]): OddsEvent | null {
  const home = normalize(match.homeTeam?.name ?? "");
  const away = normalize(match.awayTeam?.name ?? "");
  const kickoff = new Date(match.utcDate).getTime();

  for (const ev of odds) {
    const evHome = normalize(ev.home_team ?? "");
    const evAway = normalize(ev.away_team ?? "");
    const nameHit =
      (evHome.includes(home) || home.includes(evHome)) &&
      (evAway.includes(away) || away.includes(evAway));
    if (!nameHit) continue;
    const evTime = new Date(ev.commence_time).getTime();
    if (
      isFinite(kickoff) &&
      isFinite(evTime) &&
      Math.abs(kickoff - evTime) > 86_400_000
    )
      continue;
    return ev;
  }
  return null;
}

/**
 * De-vigged consensus: for every book quoting all three outcomes,
 * normalize implied probabilities (removes the overround), then average.
 */
function consensusProbs(
  ev: OddsEvent
): { probs: { home: number; draw: number; away: number }; books: number } | null {
  const perBook: { home: number; draw: number; away: number }[] = [];

  for (const bk of ev.bookmakers ?? []) {
    for (const market of bk.markets ?? []) {
      if (market.key !== "h2h") continue;
      let h = 0,
        d = 0,
        a = 0;
      for (const oc of market.outcomes ?? []) {
        if (oc.price <= 1) continue;
        if (oc.name === ev.home_team) h = 1 / oc.price;
        else if (oc.name === ev.away_team) a = 1 / oc.price;
        else if (oc.name === "Draw") d = 1 / oc.price;
      }
      const sum = h + d + a;
      if (h > 0 && d > 0 && a > 0 && sum > 1) {
        perBook.push({ home: h / sum, draw: d / sum, away: a / sum });
      }
    }
  }

  if (!perBook.length) return null;
  const n = perBook.length;
  return {
    probs: {
      home: perBook.reduce((s, p) => s + p.home, 0) / n,
      draw: perBook.reduce((s, p) => s + p.draw, 0) / n,
      away: perBook.reduce((s, p) => s + p.away, 0) / n,
    },
    books: n,
  };
}

function kellyYes(fairProb: number, priceCents: number): number {
  const p = priceCents / 100;
  if (p <= 0 || p >= 1 || fairProb <= p) return 0;
  // Binary contract: win (1-p)/p per $ staked with prob q
  const b = (1 - p) / p;
  const kelly = (fairProb * b - (1 - fairProb)) / b;
  return Math.min(0.25, Math.max(0, kelly)) * 100;
}

function buildQuestion(
  key: BinaryQuestion["key"],
  teamLabel: string,
  fairProb: number,
  booksCount: number
): BinaryQuestion {
  const fairCents = fairProb * 100;
  const buyYesBelow = Math.max(1, Math.round(fairCents - BAND_CENTS));
  const buyNoAbove = Math.min(99, Math.round(fairCents + BAND_CENTS));

  // Conviction: needs distance from coin-flip AND real book coverage
  let tier: BinaryQuestion["tier"] = "PASS";
  if (booksCount >= 3 && (fairProb >= 0.65 || fairProb <= 0.35)) tier = "STRONG";
  else if (booksCount >= 2 && (fairProb >= 0.55 || fairProb <= 0.45)) tier = "LEAN";

  return {
    key,
    question: key === "draw" ? "DRAW?" : `${teamLabel.toUpperCase()} TO WIN?`,
    fairProb,
    buyYesBelow,
    buyNoAbove,
    kellyYesPct: Number(kellyYes(fairProb, buyYesBelow).toFixed(1)),
    tier,
  };
}

export function findEdges(
  matches: FootballMatch[],
  odds: OddsEvent[],
  elo: EloBook
): MatchEdge[] {
  const out: MatchEdge[] = [];

  for (const m of matches) {
    const home = m.homeTeam?.name;
    const away = m.awayTeam?.name;
    if (!home || !away) continue;

    const eloProbs = elo.probabilities(home, away);
    const oddsEvent = matchOdds(m, odds);
    const consensus = oddsEvent ? consensusProbs(oddsEvent) : null;

    // Blend: books are sharp — they dominate when available.
    const blend = consensus
      ? {
          home: 0.85 * consensus.probs.home + 0.15 * eloProbs.home,
          draw: 0.85 * consensus.probs.draw + 0.15 * eloProbs.draw,
          away: 0.85 * consensus.probs.away + 0.15 * eloProbs.away,
        }
      : { home: eloProbs.home, draw: eloProbs.draw, away: eloProbs.away };

    const booksCount = consensus?.books ?? 0;
    const questions = [
      buildQuestion("home", home, blend.home, booksCount),
      buildQuestion("draw", "draw", blend.draw, booksCount),
      buildQuestion("away", away, blend.away, booksCount),
    ];

    out.push({
      matchId: m.id,
      home,
      away,
      competition: m.competition?.name ?? "",
      kickoff: m.utcDate,
      homeElo: eloProbs.homeElo,
      awayElo: eloProbs.awayElo,
      modelProbs: blend,
      consensusProbs: consensus?.probs ?? null,
      booksCount,
      questions,
      hasStrong: questions.some((q) => q.tier === "STRONG"),
    });
  }

  // Strong conviction first, then by kickoff
  return out.sort((a, b) => {
    if (a.hasStrong !== b.hasStrong) return a.hasStrong ? -1 : 1;
    return new Date(a.kickoff).getTime() - new Date(b.kickoff).getTime();
  });
}
