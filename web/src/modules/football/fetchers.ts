import type { FootballMatch, OddsEvent } from "@/types";
import { jsonFetcher } from "@/lib/utils";

// All football calls go through our own API routes:
//  - football-data.org rejects browser CORS
//  - keys stay server-side

export async function fetchFixtures(comp: string): Promise<FootballMatch[]> {
  const data = await jsonFetcher<{ matches?: FootballMatch[] }>(
    `/api/football?comp=${encodeURIComponent(comp)}&status=SCHEDULED`
  );
  return data.matches ?? [];
}

export async function fetchFinished(comp: string): Promise<FootballMatch[]> {
  const data = await jsonFetcher<{ matches?: FootballMatch[] }>(
    `/api/football?comp=${encodeURIComponent(comp)}&status=FINISHED`
  );
  return data.matches ?? [];
}

export async function fetchMatchResult(
  id: number
): Promise<FootballMatch | null> {
  try {
    return await jsonFetcher<FootballMatch>(`/api/football?match=${id}`);
  } catch {
    return null;
  }
}

export async function fetchOdds(sportKey: string): Promise<OddsEvent[]> {
  const data = await jsonFetcher<OddsEvent[]>(
    `/api/odds?sport=${encodeURIComponent(sportKey)}`
  );
  return Array.isArray(data) ? data : [];
}

/** Competition code → Odds API sport key */
export const COMP_TO_SPORT: Record<string, string> = {
  PL: "soccer_epl",
  PD: "soccer_spain_la_liga",
  BL1: "soccer_germany_bundesliga",
  SA: "soccer_italy_serie_a",
  FL1: "soccer_france_ligue_one",
  CL: "soccer_uefa_champs_league",
  DED: "soccer_netherlands_eredivisie",
  PPL: "soccer_portugal_primeira_liga",
  ELC: "soccer_efl_champ",
  WC: "soccer_fifa_world_cup",
};

export const COMPETITIONS = [
  { code: "PL", name: "Premier League" },
  { code: "PD", name: "La Liga" },
  { code: "BL1", name: "Bundesliga" },
  { code: "SA", name: "Serie A" },
  { code: "FL1", name: "Ligue 1" },
  { code: "CL", name: "Champions League" },
  { code: "DED", name: "Eredivisie" },
  { code: "PPL", name: "Primeira Liga" },
  { code: "ELC", name: "Championship" },
  { code: "WC", name: "World Cup" },
];
