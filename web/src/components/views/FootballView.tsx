"use client";

import { useEffect, useMemo, useState } from "react";
import useSWR from "swr";
import MatchCard from "@/components/MatchCard";
import AccuracyBadge from "@/components/AccuracyBadge";
import { EloBook } from "@/modules/football/elo";
import { findEdges } from "@/modules/football/edge-finder";
import {
  COMPETITIONS,
  COMP_TO_SPORT,
  fetchFinished,
  fetchFixtures,
  fetchMatchResult,
  fetchOdds,
} from "@/modules/football/fetchers";
import { logSignal, pendingLogs, resolveLog } from "@/lib/accuracy-tracker";

async function loadCompetition(comp: string) {
  const sport = COMP_TO_SPORT[comp] ?? "soccer_epl";
  const [fixtures, finished, odds] = await Promise.all([
    fetchFixtures(comp),
    fetchFinished(comp).catch(() => []),
    fetchOdds(sport).catch(() => []),
  ]);
  const elo = new EloBook();
  elo.seedFromResults(finished);
  const edges = findEdges(fixtures.slice(0, 30), odds, elo);
  return { edges, fixtures: fixtures.length, oddsEvents: odds.length };
}

export default function FootballView({
  onStatus,
  onLogged,
}: {
  onStatus: (active: boolean) => void;
  onLogged: () => void;
}) {
  const [comp, setComp] = useState("PL");

  const { data, error, isLoading } = useSWR(
    ["football", comp],
    () => loadCompetition(comp),
    {
      refreshInterval: 30 * 60 * 1000, // odds cached 30min server-side anyway
      keepPreviousData: true,
      onErrorRetry: (_e, _k, _c, revalidate, { retryCount }) => {
        if (retryCount >= 3) return;
        setTimeout(() => revalidate({ retryCount }), 5000 * (retryCount + 1));
      },
    }
  );

  const strong = useMemo(
    () => (data?.edges ?? []).filter((m) => m.hasStrong),
    [data]
  );
  const rest = useMemo(
    () => (data?.edges ?? []).filter((m) => !m.hasStrong).slice(0, 12),
    [data]
  );

  useEffect(() => {
    onStatus(strong.length > 0);
  }, [strong, onStatus]);

  // Log STRONG YES-side calls (fair >= 60% on an outcome)
  useEffect(() => {
    for (const m of strong) {
      const q = m.questions.find(
        (x) => x.tier === "STRONG" && x.fairProb >= 0.6
      );
      if (!q) continue;
      logSignal({
        module: "football",
        signal: {
          type: "binary",
          target: String(m.matchId),
          direction: q.key,
          score: Math.round(q.fairProb * 100),
          details: { home: m.home, away: m.away, question: q.question },
        },
        priceAtSignal: q.fairProb,
      });
    }
    if (strong.length) onLogged();
  }, [strong, onLogged]);

  // Resolve past calls via final score
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const pending = pendingLogs("football", 5 * 3600 * 1000).slice(0, 3);
      for (const log of pending) {
        const match = await fetchMatchResult(Number(log.signal.target));
        if (cancelled) return;
        if (!match || match.status !== "FINISHED") continue;
        const hs = match.score?.fullTime?.home;
        const as = match.score?.fullTime?.away;
        if (hs == null || as == null) {
          resolveLog(log.id, "voided", null);
          continue;
        }
        const winner = hs > as ? "home" : hs < as ? "away" : "draw";
        resolveLog(log.id, winner === log.signal.direction ? "hit" : "miss", null);
      }
      if (pending.length) onLogged();
    })();
    return () => {
      cancelled = true;
    };
  }, [data, onLogged]);

  const keysMissing = error && String(error).includes("503");

  return (
    <div className="space-y-3">
      <div className="card flex items-center justify-between flex-wrap gap-2">
        <select
          value={comp}
          onChange={(e) => setComp(e.target.value)}
          className="bg-[var(--bg-elevated)] text-[var(--text-primary)] font-mono-display text-sm rounded-input px-2 py-1 border border-[var(--border-subtle)]"
        >
          {COMPETITIONS.map((c) => (
            <option key={c.code} value={c.code}>
              {c.name}
            </option>
          ))}
        </select>
        <span className="text-xs text-[var(--text-tertiary)] font-mono-display">
          {isLoading && !data
            ? "loading fixtures + odds…"
            : `${data?.fixtures ?? 0} fixtures · ${data?.oddsEvents ?? 0} odds events · fair value = de-vigged consensus + ELO`}
        </span>
      </div>

      {keysMissing && (
        <div className="card text-sm" style={{ color: "var(--signal-neutral)" }}>
          API keys not configured. Add FOOTBALL_DATA_API_KEY and ODDS_API_KEY
          to the Vercel env settings (or .env.local) to enable this module.
        </div>
      )}

      {strong.length > 0 && (
        <>
          <h2 className="font-mono-display text-lg">
            STRONG CALLS ({strong.length})
          </h2>
          <p className="text-xs text-[var(--text-tertiary)]">
            Fair value is 65¢+ (or 35¢-) with 3+ books behind it. Bet only when
            the platform&apos;s price is outside the band.
          </p>
          {strong.map((m) => (
            <MatchCard key={m.matchId} match={m} />
          ))}
        </>
      )}

      {strong.length === 0 && !isLoading && !keysMissing && (
        <div className="card text-sm text-[var(--text-secondary)]">
          No strong calls right now — every market is near fair value. Betting
          without an edge is negative-EV; the correct play is none.
        </div>
      )}

      {rest.length > 0 && (
        <details>
          <summary className="font-mono-display text-sm text-[var(--text-secondary)] cursor-pointer py-1">
            Other upcoming matches ({rest.length})
          </summary>
          <div className="space-y-2 mt-2">
            {rest.map((m) => (
              <MatchCard key={m.matchId} match={m} />
            ))}
          </div>
        </details>
      )}

      <AccuracyBadge module="football" />
    </div>
  );
}
