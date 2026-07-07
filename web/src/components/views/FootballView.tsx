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

  const edges = useMemo(
    () => (data?.edges ?? []).filter((m) => m.bestEdge !== null),
    [data]
  );
  const rest = useMemo(
    () => (data?.edges ?? []).filter((m) => m.bestEdge === null).slice(0, 10),
    [data]
  );

  useEffect(() => {
    onStatus(edges.length > 0);
  }, [edges, onStatus]);

  // Log edges; resolve past matches via result lookup
  useEffect(() => {
    for (const m of edges) {
      logSignal({
        module: "football",
        signal: {
          type: "edge",
          target: String(m.matchId),
          direction: m.bestEdge!.outcome,
          score: Math.round(m.bestEdge!.edge * 100),
          details: { home: m.home, away: m.away, odds: m.bestEdge!.bestOdds },
        },
        priceAtSignal: m.bestEdge!.bestOdds,
      });
    }
    if (edges.length) onLogged();
  }, [edges, onLogged]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      // Resolve edges older than 3h past their logging (match should be done)
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

  const keysMissing =
    error && String(error).includes("503");

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
            : `${data?.fixtures ?? 0} fixtures · ${data?.oddsEvents ?? 0} odds events · edges shown at 5%+`}
        </span>
      </div>

      {keysMissing && (
        <div className="card text-sm" style={{ color: "var(--signal-neutral)" }}>
          API keys not configured. Add FOOTBALL_DATA_API_KEY and ODDS_API_KEY
          to .env.local (or Vercel env settings) to enable this module.
        </div>
      )}

      {edges.length > 0 && (
        <>
          <h2 className="font-mono-display text-lg">
            EDGES DETECTED ({edges.length})
          </h2>
          {edges.map((m) => (
            <MatchCard key={m.matchId} match={m} />
          ))}
        </>
      )}

      {edges.length === 0 && !isLoading && !keysMissing && (
        <div className="card text-sm text-[var(--text-secondary)]">
          No 5%+ edges right now. The book prices and the model agree — betting
          without an edge is negative-EV, so the correct play is none.
        </div>
      )}

      {rest.length > 0 && (
        <details>
          <summary className="font-mono-display text-sm text-[var(--text-secondary)] cursor-pointer py-1">
            Upcoming matches without an edge ({rest.length})
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
