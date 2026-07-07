import type { FootballMatch } from "@/types";

export const K = 32;
export const HOME_ADVANTAGE = 65;

/** Prior ratings for national + major club sides; unknown teams start at 1500. */
export const SEED_ELO: Record<string, number> = {
  // Nations
  Argentina: 2150, France: 2100, Brazil: 2050, England: 2040, Spain: 2030,
  Germany: 2000, Netherlands: 1990, Portugal: 1980, Belgium: 1960, Italy: 1950,
  Croatia: 1940, Uruguay: 1920, Colombia: 1910, USA: 1880, Mexico: 1870,
  Morocco: 1860, Japan: 1850, Senegal: 1840, Switzerland: 1830, Denmark: 1820,
  // Clubs
  "Real Madrid": 2080, "Manchester City": 2070, "Bayern Munich": 2040,
  Liverpool: 2030, "FC Barcelona": 2020, Arsenal: 2010,
  "Paris Saint-Germain": 2000, "Inter Milan": 1990, "AC Milan": 1960,
  Juventus: 1950, "Borussia Dortmund": 1940, "Atlético Madrid": 1930,
  Chelsea: 1920, Napoli: 1910, "Bayer Leverkusen": 1900,
  "Manchester United": 1870, "Tottenham Hotspur": 1880, "Aston Villa": 1860,
  "Newcastle United": 1850, Benfica: 1850, "RB Leipzig": 1840, Atalanta: 1830,
  Porto: 1830, "Real Sociedad": 1840, "Athletic Club": 1820, Villarreal: 1810,
  "AS Roma": 1810, Lazio: 1820, Fiorentina: 1800, Sevilla: 1800,
  "West Ham United": 1830, "Brighton & Hove Albion": 1830, "Crystal Palace": 1790,
  Fulham: 1780, Brentford: 1780, "Wolverhampton Wanderers": 1770,
  "Nottingham Forest": 1770, Everton: 1750, Bournemouth: 1770,
};

const ALIASES: Record<string, string> = {
  "Korea Republic": "South Korea",
  "United States": "USA",
  "IR Iran": "Iran",
  "Türkiye": "Turkey",
  Czechia: "Czech Republic",
  "FC Bayern München": "Bayern Munich",
  "BV Borussia 09 Dortmund": "Borussia Dortmund",
  "Club Atlético de Madrid": "Atlético Madrid",
  "SSC Napoli": "Napoli",
  "Bayer 04 Leverkusen": "Bayer Leverkusen",
  "Manchester City FC": "Manchester City",
  "Manchester United FC": "Manchester United",
  "Liverpool FC": "Liverpool",
  "Arsenal FC": "Arsenal",
  "Chelsea FC": "Chelsea",
  "Tottenham Hotspur FC": "Tottenham Hotspur",
  "Aston Villa FC": "Aston Villa",
  "Newcastle United FC": "Newcastle United",
  "West Ham United FC": "West Ham United",
  "Brighton & Hove Albion FC": "Brighton & Hove Albion",
  "Crystal Palace FC": "Crystal Palace",
  "Fulham FC": "Fulham",
  "Brentford FC": "Brentford",
  "Everton FC": "Everton",
  "AFC Bournemouth": "Bournemouth",
  "Nottingham Forest FC": "Nottingham Forest",
  "Wolverhampton Wanderers FC": "Wolverhampton Wanderers",
  "Real Madrid CF": "Real Madrid",
  "Paris Saint-Germain FC": "Paris Saint-Germain",
  "SL Benfica": "Benfica",
  "FC Porto": "Porto",
};

export function canonicalName(name: string): string {
  return ALIASES[name] ?? name;
}

export function expectedScore(ratingA: number, ratingB: number): number {
  return 1 / (1 + Math.pow(10, (ratingB - ratingA) / 400));
}

export class EloBook {
  private ratings = new Map<string, number>();

  get(team: string): number {
    const canon = canonicalName(team);
    return this.ratings.get(canon) ?? SEED_ELO[canon] ?? 1500;
  }

  private set(team: string, rating: number) {
    this.ratings.set(canonicalName(team), rating);
  }

  /** Apply finished matches chronologically to sharpen the seed ratings. */
  seedFromResults(finished: FootballMatch[]) {
    const sorted = [...finished].sort(
      (a, b) => new Date(a.utcDate).getTime() - new Date(b.utcDate).getTime()
    );
    for (const m of sorted) {
      const hs = m.score?.fullTime?.home;
      const as = m.score?.fullTime?.away;
      if (hs == null || as == null) continue;
      const home = m.homeTeam?.name;
      const away = m.awayTeam?.name;
      if (!home || !away) continue;

      const rh = this.get(home) + HOME_ADVANTAGE;
      const ra = this.get(away);
      const expHome = expectedScore(rh, ra);
      const actual = hs > as ? 1 : hs < as ? 0 : 0.5;
      const delta = K * (actual - expHome);
      this.set(home, this.get(home) + delta);
      this.set(away, this.get(away) - delta);
    }
  }

  /** Win/draw/win probabilities with an ELO-gap-shaped draw model. */
  probabilities(home: string, away: string) {
    const homeElo = this.get(home);
    const awayElo = this.get(away);
    const expHome = expectedScore(homeElo + HOME_ADVANTAGE, awayElo);
    const gap = homeElo + HOME_ADVANTAGE - awayElo;
    // Draws peak ~27% for equal sides, shrink for mismatches
    const draw = 0.27 * Math.exp(-Math.abs(gap) / 600);
    const homeWin = expHome * (1 - draw);
    const awayWin = (1 - expHome) * (1 - draw);
    const total = homeWin + draw + awayWin;
    return {
      homeElo,
      awayElo,
      home: homeWin / total,
      draw: draw / total,
      away: awayWin / total,
    };
  }
}
