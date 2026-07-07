import type {
  FootballMatch,
  MatchEdge,
  OddsEvent,
  OutcomeEdge,
} from "@/types";
import { EloBook } from "./elo";

/** Minimum edge to surface — below 5% it's noise. */
export const EDGE_MIN = 0.05;

function normalize(name: string): string {
  return name
    .toLowerCase()
    .replace(/\b(fc|cf|afc|sl|bv|ssc)\b/g, "")
    .replace(/[^a-z ]/g, "")
    .trim();
}

function matchOdds(
  match: FootballMatch,
  odds: OddsEvent[]
): OddsEvent | null {
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
    if (isFinite(kickoff) && isFinite(evTime) && Math.abs(kickoff - evTime) > 86_400_000)
      continue;
    return ev;
  }
  return null;
}

function bestOddsPerOutcome(ev: OddsEvent) {
  const best = {
    home: { odds: 0, book: "" },
    draw: { odds: 0, book: "" },
    away: { odds: 0, book: "" },
  };
  for (const bk of ev.bookmakers ?? []) {
    for (const market of bk.markets ?? []) {
      if (market.key !== "h2h") continue;
      for (const oc of market.outcomes ?? []) {
        let slot: keyof typeof best | null = null;
        if (oc.name === ev.home_team) slot = "home";
        else if (oc.name === ev.away_team) slot = "away";
        else if (oc.name === "Draw") slot = "draw";
        if (slot && oc.price > best[slot].odds) {
          best[slot] = { odds: oc.price, book: bk.title };
        }
      }
    }
  }
  return best;
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

    const probs = elo.probabilities(home, away);
    const oddsEvent = matchOdds(m, odds);
    if (!oddsEvent) continue; // no odds → no edge computable

    const best = bestOddsPerOutcome(oddsEvent);
    const edges: OutcomeEdge[] = [];

    (["home", "draw", "away"] as const).forEach((oc) => {
      const b = best[oc];
      if (b.odds <= 1) return;
      const implied = 1 / b.odds;
      const modelProb = probs[oc];
      const edge = modelProb - implied;
      const kelly =
        edge > 0 ? (modelProb * b.odds - 1) / (b.odds - 1) : 0;
      edges.push({
        outcome: oc,
        modelProb,
        impliedProb: implied,
        edge,
        bestOdds: b.odds,
        bestBook: b.book,
        kellyFraction: Math.min(Math.max(kelly, 0), 0.25),
        signal: edge > 0.1 ? "STRONG" : edge > EDGE_MIN ? "MODERATE" : "NONE",
      });
    });

    const positive = edges
      .filter((e) => e.signal !== "NONE")
      .sort((a, b) => b.edge - a.edge);

    out.push({
      matchId: m.id,
      home,
      away,
      competition: m.competition?.name ?? "",
      kickoff: m.utcDate,
      homeElo: probs.homeElo,
      awayElo: probs.awayElo,
      probs: { home: probs.home, draw: probs.draw, away: probs.away },
      edges,
      bestEdge: positive[0] ?? null,
    });
  }

  // Edges first (largest first), then the rest by kickoff
  return out.sort((a, b) => {
    const ea = a.bestEdge?.edge ?? -1;
    const eb = b.bestEdge?.edge ?? -1;
    if (ea !== eb) return eb - ea;
    return new Date(a.kickoff).getTime() - new Date(b.kickoff).getTime();
  });
}
