"use client";

import { useCallback, useEffect, useState } from "react";
import {
  DEFAULT_LADDERS,
  POST_MORTEM_FAILURES,
  adherenceStat,
  applyPrices,
  checkEntry,
  getMissed,
  getPositions,
  getProfile,
  medianSizePct,
  saveMissed,
  savePositions,
  saveProfile,
  sizeGuidelinePct,
  type CoinType,
  type Conviction,
  type EntryCheck,
  type MissedTrade,
  type Position,
  type DisciplineProfile,
} from "@/lib/discipline";
import { logTrade } from "@/lib/storage";
import { fetchPrices, jsonFetcher, timeAgo } from "@/lib/utils";
import type { SafetyReport } from "@/types";

const COIN_TYPES: CoinType[] = ["meme", "utility", "ownership"];
const CONVICTIONS: Conviction[] = ["LOW", "MEDIUM", "HIGH"];

/** Word-overlap (Jaccard) between two thesis texts, 0..1. Low = the thesis has
 *  drifted from the original — honest adaptation or quiet goalpost-moving. */
function thesisOverlap(a: string, b: string): number {
  const norm = (s: string) =>
    new Set(s.toLowerCase().replace(/[^a-z0-9\s]/g, " ").split(/\s+/).filter((w) => w.length > 2));
  const sa = norm(a);
  const sb = norm(b);
  if (!sa.size || !sb.size) return 1;
  const inter = Array.from(sa).filter((w) => sb.has(w)).length;
  return inter / (sa.size + sb.size - inter);
}

export default function PositionsView() {
  const [profile, setProfile] = useState<DisciplineProfile>(() => getProfile());
  const [positions, setPositions] = useState<Position[]>(() => getPositions());
  const [missed, setMissed] = useState<MissedTrade[]>(() => getMissed());
  const [showNew, setShowNew] = useState(false);
  const [checks, setChecks] = useState<EntryCheck[] | null>(null);
  const [pendingDraft, setPendingDraft] = useState<Position | null>(null);
  const [closing, setClosing] = useState<Position | null>(null);

  // Live on-chain / narrative events per open position, for cross-feed
  // invalidation alerts (creator selling, structure break, vamp risk).
  const [intel, setIntel] = useState<Record<string, string[]>>({});

  const open = positions.filter((p) => p.status === "OPEN");
  const closed = positions.filter((p) => p.status === "CLOSED");
  const adherence = adherenceStat(positions);

  // Live prices every 60s for open positions with addresses
  const refresh = useCallback(async () => {
    const addrs = getPositions()
      .filter((p) => p.status === "OPEN" && p.address)
      .map((p) => p.address);
    if (!addrs.length) return;
    try {
      const map = await fetchPrices(addrs);
      const prices = new Map<string, number>();
      map.forEach((v, addr) => {
        if (v.price > 0) prices.set(addr, v.price);
      });
      setPositions(applyPrices(prices));
    } catch {
      /* stale prices are shown as-is */
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 60_000);
    return () => clearInterval(id);
  }, [refresh]);

  // Cross-feed thesis-invalidation watch: pull each open position's safety
  // report (server-cached 5 min) and derive adverse events that should quote
  // the user's own invalidation back at them. Slow interval — few positions.
  const refreshIntel = useCallback(async () => {
    const addrs = getPositions()
      .filter((p) => p.status === "OPEN" && p.address)
      .map((p) => p.address);
    for (const addr of Array.from(new Set(addrs))) {
      try {
        const r = await jsonFetcher<SafetyReport>(`/api/safety?mint=${addr}`);
        const events: string[] = [];
        if (r.creator?.status === "distributing") events.push("The creator wallet is distributing (selling).");
        if (r.chart?.structure?.state === "DOWNTREND") events.push("Market structure just broke down to a downtrend.");
        if (r.collision?.vampRisk) events.push("A vamp risk appeared — a better-named competitor is threatening the narrative.");
        if (r.deep?.clusterTrend && r.deep.clusterTrend.startsWith("⚠")) events.push("A funding cluster is reducing (coordinated selling).");
        setIntel((prev) => ({ ...prev, [addr]: events }));
      } catch {
        /* leave prior intel in place */
      }
    }
  }, []);

  useEffect(() => {
    refreshIntel();
    // Cross-feed intel (creator/structure/vamp/cluster) doesn't invalidate on a
    // 5-min scale — it pulls a full safety report per open position, so a 15-min
    // cadence cuts those provider-heavy fetches to a third with no signal loss.
    const id = setInterval(refreshIntel, 900_000);
    return () => clearInterval(id);
  }, [refreshIntel]);

  function persistPositions(next: Position[]) {
    savePositions(next);
    setPositions([...next]);
  }
  function persistProfile(next: DisciplineProfile) {
    saveProfile(next);
    setProfile({ ...next });
  }

  // ── Entry submission with friction pipeline ─────────────────────────
  async function attemptOpen(draft: Position) {
    let tokenH1: number | null = null;
    if (draft.address) {
      try {
        const map = await fetchPrices([draft.address]);
        const row = map.get(draft.address);
        tokenH1 = row ? row.h1 : null;
        if (row && row.price > 0) draft.entryPrice = row.price;
      } catch {
        /* no live data — proceed without FOMO chart check */
      }
    }
    const result = checkEntry({
      profile,
      openPositions: open,
      closedPositions: closed,
      draft,
      tokenH1,
    });
    if (result.length) {
      setChecks(result);
      setPendingDraft(draft);
      if (result.some((c) => c.level === "block" && c.title.startsWith("FOMO gate"))) {
        // 5-minute cooldown starts now
        persistProfile({ ...profile, cooldownUntil: Date.now() + 5 * 60_000 });
      }
      return;
    }
    finalizeOpen(draft);
  }

  function finalizeOpen(draft: Position) {
    persistPositions([...positions, draft]);
    setShowNew(false);
    setChecks(null);
    setPendingDraft(null);
  }

  return (
    <div className="space-y-3">
      {/* Non-dismissible disclaimer */}
      <div className="text-xs text-[var(--text-tertiary)] border border-[var(--border-subtle)] rounded-card px-3 py-2">
        This tool surfaces information and creates friction — it does not
        predict outcomes and never emits buy/sell calls. Memecoin trading
        carries substantial risk of total loss. Not financial advice.
      </div>

      {/* Profile setup */}
      {(profile.portfolioUsd <= 0 || profile.lifeChangingUsd <= 0 || !profile.traderType) ? (
        <ProfileSetup profile={profile} onSave={persistProfile} />
      ) : (
        <div className="card flex items-center justify-between flex-wrap gap-2">
          <span className="font-mono-display text-sm text-[var(--text-secondary)]">
            Portfolio ${profile.portfolioUsd.toLocaleString()} ·{" "}
            {profile.traderType} · {open.length}/{profile.maxOpenPositions} open ·
            plan adherence{" "}
            {adherence.hit ? `${adherence.complied}/${adherence.hit} levels honored` : "no levels hit yet"}
            {profile.rules.length > 0 && ` · ${profile.rules.length} personal rule(s)`}
          </span>
          <button
            onClick={() => setShowNew(!showNew)}
            className="font-mono-display text-sm px-4 py-2 rounded-btn"
            style={{ background: "var(--signal-edge)", color: "var(--bg-primary)" }}
          >
            {showNew ? "CANCEL" : "+ NEW POSITION"}
          </button>
        </div>
      )}

      {/* Friction modal */}
      {checks && pendingDraft && (
        <FrictionModal
          checks={checks}
          onAbort={() => {
            setChecks(null);
            setPendingDraft(null);
          }}
          onProceed={
            checks.some((c) => c.level === "block")
              ? null
              : () => finalizeOpen(pendingDraft)
          }
        />
      )}

      {showNew && profile.portfolioUsd > 0 && (
        <NewPositionForm profile={profile} onSubmit={attemptOpen} />
      )}

      {/* Open positions */}
      {open.length > 0 && (
        <>
          <h2 className="font-mono-display text-lg">OPEN POSITIONS ({open.length})</h2>
          {open.map((p) => (
            <PositionCard
              key={p.id}
              p={p}
              profile={profile}
              events={p.address ? intel[p.address] ?? [] : []}
              onChange={(next) => {
                persistPositions(positions.map((x) => (x.id === next.id ? next : x)));
              }}
              onClose={() => setClosing(p)}
            />
          ))}
        </>
      )}

      {/* Close / post-mortem flow */}
      {closing && (
        <CloseModal
          p={closing}
          onDone={(updated, newRule) => {
            persistPositions(positions.map((x) => (x.id === updated.id ? updated : x)));
            if (newRule) {
              persistProfile({ ...profile, rules: [...profile.rules, newRule] });
            }
            if (updated.exitUsd !== null) {
              // Feed the challenge bankroll + shared trade log
              logTrade(updated.symbol, updated.sizeUsd, updated.exitUsd, "position");
            }
            setClosing(null);
          }}
          onCancel={() => setClosing(null)}
        />
      )}

      {/* Missed-trade log */}
      <MissedLog missed={missed} onAdd={(m) => { const next = [...missed, m]; saveMissed(next); setMissed(next); }} />

      {/* Journal */}
      {closed.length > 0 && (
        <div className="card overflow-x-auto">
          <h3 className="font-mono-display text-base mb-2">JOURNAL ({closed.length})</h3>
          <table className="data-table">
            <thead>
              <tr><th>Token</th><th>Size</th><th>Exit</th><th>PnL</th><th>Failure named</th><th>Rule created</th></tr>
            </thead>
            <tbody>
              {[...closed].reverse().map((p) => {
                const pnl = (p.exitUsd ?? 0) - p.sizeUsd;
                return (
                  <tr key={p.id}>
                    <td className="font-mono-display">{p.symbol}</td>
                    <td>${p.sizeUsd.toFixed(0)}</td>
                    <td>${(p.exitUsd ?? 0).toFixed(0)}</td>
                    <td style={{ color: pnl >= 0 ? "var(--signal-long)" : "var(--signal-short)" }}>
                      {pnl >= 0 ? "+" : ""}${pnl.toFixed(0)}
                    </td>
                    <td className="text-[var(--text-secondary)] text-xs">{p.postMortem?.failure ?? "—"}</td>
                    <td className="text-[var(--text-secondary)] text-xs">{p.postMortem?.rule || "—"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ── Sub-components ────────────────────────────────────────────────────────

function ProfileSetup({
  profile,
  onSave,
}: {
  profile: DisciplineProfile;
  onSave: (p: DisciplineProfile) => void;
}) {
  const [portfolio, setPortfolio] = useState(String(profile.portfolioUsd || ""));
  const [lifeChanging, setLifeChanging] = useState(String(profile.lifeChangingUsd || ""));
  const [type, setType] = useState<string>(profile.traderType ?? "");
  const [lockout, setLockout] = useState(String(profile.revengeLockoutMin || 0));

  return (
    <div className="card space-y-3">
      <h3 className="font-mono-display text-base">SET UP YOUR DISCIPLINE PROFILE</h3>
      <p className="text-xs text-[var(--text-secondary)]">
        Answer these once, while calm. The tool will quote your own answers
        back to you at the exact moments you won&apos;t want to hear them.
      </p>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <Input label="Portfolio size ($)" value={portfolio} onChange={setPortfolio} />
        <Input
          label="Life-changing amount ($) — the roundtrip alarm fires here"
          value={lifeChanging}
          onChange={setLifeChanging}
        />
        <label className="block text-sm">
          <span className="text-xs text-[var(--text-secondary)] font-mono-display uppercase">
            Trader type — neither is wrong
          </span>
          <select
            value={type}
            onChange={(e) => setType(e.target.value)}
            className="w-full mt-1 bg-[var(--bg-elevated)] rounded-input px-2 py-1.5 text-sm border border-[var(--border-subtle)]"
          >
            <option value="">choose…</option>
            <option value="FISH">FISH — methodical, consistent, lower variance</option>
            <option value="MONKEY">MONKEY — high conviction moonshots, high variance</option>
          </select>
        </label>
        <Input
          label="Revenge lockout (minutes, 0 = off) — agree to this NOW, while calm"
          value={lockout}
          onChange={setLockout}
        />
      </div>
      <button
        onClick={() => {
          const p = Number(portfolio);
          const l = Number(lifeChanging);
          if (!(p > 0) || !(l > 0) || !type) return;
          onSave({
            ...profile,
            portfolioUsd: p,
            lifeChangingUsd: l,
            traderType: type as DisciplineProfile["traderType"],
            revengeLockoutMin: Math.max(0, Number(lockout) || 0),
          });
        }}
        className="font-mono-display text-sm px-4 py-2 rounded-btn border border-[var(--border-active)] text-[var(--signal-edge)]"
      >
        SAVE PROFILE
      </button>
    </div>
  );
}

function NewPositionForm({
  profile,
  onSubmit,
}: {
  profile: DisciplineProfile;
  onSubmit: (p: Position) => void;
}) {
  const [symbol, setSymbol] = useState("");
  const [address, setAddress] = useState("");
  const [coinType, setCoinType] = useState<CoinType>("meme");
  const [conviction, setConviction] = useState<Conviction>("MEDIUM");
  const [why, setWhy] = useState("");
  const [invalidation, setInvalidation] = useState("");
  const [sizePct, setSizePct] = useState("2");

  const guideline = sizeGuidelinePct(conviction, coinType, profile.traderType);
  const sizeUsd = (Number(sizePct) / 100) * profile.portfolioUsd;

  return (
    <div className="card space-y-3">
      <h3 className="font-mono-display text-base">MANDATORY PRE-TRADE THESIS</h3>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <Input label="Token symbol *" value={symbol} onChange={setSymbol} />
        <Input label="Contract address (enables live tracking + alarms)" value={address} onChange={setAddress} />
        <label className="block text-sm">
          <span className="text-xs text-[var(--text-secondary)] font-mono-display uppercase">Coin type — sets time horizon + exit logic</span>
          <select value={coinType} onChange={(e) => setCoinType(e.target.value as CoinType)}
            className="w-full mt-1 bg-[var(--bg-elevated)] rounded-input px-2 py-1.5 text-sm border border-[var(--border-subtle)]">
            {COIN_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </label>
        <label className="block text-sm">
          <span className="text-xs text-[var(--text-secondary)] font-mono-display uppercase">Conviction</span>
          <select value={conviction} onChange={(e) => setConviction(e.target.value as Conviction)}
            className="w-full mt-1 bg-[var(--bg-elevated)] rounded-input px-2 py-1.5 text-sm border border-[var(--border-subtle)]">
            {CONVICTIONS.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </label>
      </div>
      <label className="block text-sm">
        <span className="text-xs text-[var(--text-secondary)] font-mono-display uppercase">Why am I buying? * (min 20 chars — if you can&apos;t articulate it, that&apos;s the answer)</span>
        <textarea value={why} onChange={(e) => setWhy(e.target.value)} rows={2}
          className="w-full mt-1 bg-[var(--bg-elevated)] rounded-input px-2 py-1.5 text-sm border border-[var(--border-subtle)]" />
      </label>
      <label className="block text-sm">
        <span className="text-xs text-[var(--text-secondary)] font-mono-display uppercase">What would make me sell? * (explicit invalidation)</span>
        <textarea value={invalidation} onChange={(e) => setInvalidation(e.target.value)} rows={2}
          className="w-full mt-1 bg-[var(--bg-elevated)] rounded-input px-2 py-1.5 text-sm border border-[var(--border-subtle)]" />
      </label>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 items-end">
        <Input label={`Size (% of portfolio) — guideline ${guideline}% for this profile`} value={sizePct} onChange={setSizePct} />
        <div className="text-sm font-mono-display text-[var(--text-secondary)]">
          = ${isFinite(sizeUsd) ? sizeUsd.toFixed(2) : "0"} · ladder preset: {DEFAULT_LADDERS[coinType].map((l) => `sell ${l.sellPct}% @ ${l.mult}x`).join(", ")}
        </div>
      </div>
      <button
        onClick={() => {
          if (!symbol.trim()) return;
          onSubmit({
            id: `${symbol}-${Date.now()}`,
            symbol: symbol.trim().toUpperCase(),
            address: address.trim(),
            coinType,
            conviction,
            why: why.trim(),
            invalidation: invalidation.trim(),
            sizePct: Number(sizePct) || 0,
            sizeUsd,
            entryPrice: 0,
            openedAt: Date.now(),
            ladder: DEFAULT_LADDERS[coinType].map((l) => ({ ...l })),
            reevals: [],
            thesisHistory: [{ at: Date.now(), why: why.trim(), invalidation: invalidation.trim() }],
            status: "OPEN",
            closedAt: null,
            exitUsd: null,
            postMortem: null,
            lastPrice: null,
            peakValueUsd: 0,
            roundtripAcked: false,
            stopAcked: false,
          });
        }}
        className="font-mono-display text-sm px-4 py-2 rounded-btn"
        style={{ background: "var(--signal-edge)", color: "var(--bg-primary)" }}
      >
        LOG POSITION
      </button>
    </div>
  );
}

function PositionCard({
  p,
  profile,
  events,
  onChange,
  onClose,
}: {
  p: Position;
  profile: DisciplineProfile;
  events: string[];
  onChange: (p: Position) => void;
  onClose: () => void;
}) {
  const [wouldBuy, setWouldBuy] = useState("");
  const [rewriting, setRewriting] = useState(false);
  const [newWhy, setNewWhy] = useState(p.why);
  const [newInv, setNewInv] = useState(p.invalidation);

  const value =
    p.entryPrice > 0 && p.lastPrice ? p.sizeUsd * (p.lastPrice / p.entryPrice) : null;
  const pnlPct = value !== null ? (value / p.sizeUsd - 1) * 100 : null;
  const ageDays = (Date.now() - p.openedAt) / 86_400_000;
  const roundtripFiring =
    value !== null && profile.lifeChangingUsd > 0 && value >= profile.lifeChangingUsd && !p.roundtripAcked;
  const stopFiring = pnlPct !== null && pnlPct <= -40 && !p.stopAcked;
  const upBig = pnlPct !== null && pnlPct >= 50;
  const thesisStale = ageDays >= 2 && p.thesisHistory.length === 1;
  const pendingLadder = p.ladder.find((l) => l.hit && l.complied === null);

  return (
    <div className="card space-y-2" style={roundtripFiring ? { borderColor: "var(--signal-edge)" } : undefined}>
      {/* ROUNDTRIP ALARM — blocking overlay */}
      {roundtripFiring && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: "var(--bg-overlay)" }}>
          <div className="card max-w-md w-full space-y-3" style={{ borderColor: "var(--signal-edge)" }}>
            <h3 className="font-mono-display text-xl" style={{ color: "var(--signal-edge)" }}>
              ROUNDTRIP ALARM: {p.symbol}
            </h3>
            <p className="text-sm">
              You defined <b>${profile.lifeChangingUsd.toLocaleString()}</b> as a
              life-changing amount — while you were calm. This position is now worth{" "}
              <b>${value!.toFixed(0)}</b>. Riding a life-changing gain back to zero is
              the single most expensive mistake in this game. The sell target that
              keeps moving up is how it happens.
            </p>
            <div className="flex gap-2">
              <button onClick={onClose}
                className="flex-1 font-mono-display text-sm px-3 py-2 rounded-btn"
                style={{ background: "var(--signal-long)", color: "var(--bg-primary)" }}>
                I&apos;M TAKING PROFITS
              </button>
              <button
                onClick={() => onChange({ ...p, roundtripAcked: true })}
                className="flex-1 font-mono-display text-sm px-3 py-2 rounded-btn border border-[var(--border-subtle)] text-[var(--text-secondary)]">
                I understand the risk and choose to ride
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <span className="font-mono-display text-lg">{p.symbol}</span>
          <span className="font-mono-display text-xs px-2 py-0.5 rounded-input border border-[var(--border-subtle)] text-[var(--text-secondary)]">
            {p.coinType} · {p.conviction} · {p.sizePct}%
          </span>
          <span className="text-xs text-[var(--text-tertiary)] font-mono-display">{timeAgo(p.openedAt)}</span>
        </div>
        <div className="font-mono-display text-sm">
          ${p.sizeUsd.toFixed(0)} →{" "}
          {value !== null ? (
            <span style={{ color: pnlPct! >= 0 ? "var(--signal-long)" : "var(--signal-short)" }}>
              ${value.toFixed(0)} ({pnlPct! >= 0 ? "+" : ""}{pnlPct!.toFixed(0)}%)
            </span>
          ) : (
            <span className="text-[var(--text-tertiary)]">no live price</span>
          )}
        </div>
      </div>

      {/* Cross-feed thesis-invalidation watch — quotes their own words when an
          on-chain/narrative event fires, not just on price */}
      {events.length > 0 && (
        <div className="px-3 py-2 rounded-input text-sm" style={{ background: "var(--signal-short)15", border: "1px solid var(--signal-short)" }}>
          <b style={{ color: "var(--signal-short)" }}>Thesis-invalidation watch:</b>
          <ul className="mt-0.5 space-y-0.5">
            {events.map((e, i) => (
              <li key={i} style={{ color: "var(--signal-short)" }}>• {e}</li>
            ))}
          </ul>
          <div className="mt-1 text-[var(--text-secondary)]">
            You said you&apos;d sell if: <i>&quot;{p.invalidation}&quot;</i> — does this count?
          </div>
        </div>
      )}

      {/* Stop-loss rule alert — quotes their own words */}
      {stopFiring && (
        <div className="px-3 py-2 rounded-input text-sm" style={{ background: "var(--signal-short)15", border: "1px solid var(--signal-short)" }}>
          <b style={{ color: "var(--signal-short)" }}>Down {pnlPct!.toFixed(0)}%.</b>{" "}
          If there is no new information explaining this drop, the market is pricing
          in something you don&apos;t know yet. You said you&apos;d sell if:{" "}
          <i>&quot;{p.invalidation}&quot;</i> — has that happened?
          <button onClick={() => onChange({ ...p, stopAcked: true })}
            className="ml-2 text-xs font-mono-display underline text-[var(--text-secondary)]">
            acknowledged
          </button>
        </div>
      )}

      {/* Ladder compliance prompt */}
      {pendingLadder && (
        <div className="px-3 py-2 rounded-input text-sm" style={{ background: "var(--accent-glow)", border: "1px solid var(--border-active)" }}>
          <b>Ladder level hit:</b> {p.symbol} touched {pendingLadder.mult}x. Your plan
          — written before entry, while calm — says sell {pendingLadder.sellPct}%. Did you?
          <span className="ml-2">
            <button onClick={() => onChange({ ...p, ladder: p.ladder.map((l) => l === pendingLadder ? { ...l, complied: true } : l) })}
              className="text-xs font-mono-display underline mr-2" style={{ color: "var(--signal-long)" }}>yes, sold</button>
            <button onClick={() => onChange({ ...p, ladder: p.ladder.map((l) => l === pendingLadder ? { ...l, complied: false } : l) })}
              className="text-xs font-mono-display underline" style={{ color: "var(--signal-short)" }}>no, held</button>
          </span>
        </div>
      )}

      {/* Thesis + lifecycle */}
      <div className="text-sm text-[var(--text-secondary)]">
        <b>Thesis:</b> {p.why} · <b>Sell if:</b> {p.invalidation}
        {p.thesisHistory.length > 1 && (
          <details className="mt-1">
            <summary className="text-xs cursor-pointer text-[var(--text-tertiary)]">original thesis (day 1)</summary>
            <div className="text-xs text-[var(--text-tertiary)]">
              {p.thesisHistory[0].why} · Sell if: {p.thesisHistory[0].invalidation}
            </div>
          </details>
        )}
      </div>
      {/* Semantic thesis divergence — the current thesis barely overlaps day 1 */}
      {p.thesisHistory.length > 1 &&
        thesisOverlap(p.thesisHistory[0].why, p.why) < 0.3 && (
          <div className="px-3 py-2 rounded-input text-xs" style={{ background: "var(--bg-elevated)", borderLeft: "3px solid var(--signal-neutral)", color: "var(--signal-neutral)" }}>
            ⚠ Your thesis has drifted from day one — the words barely overlap. That&apos;s
            fine if the story genuinely changed; it&apos;s a warning if you&apos;re quietly
            moving the goalposts to justify still holding.
          </div>
        )}
      {thesisStale && !rewriting && (
        <div className="px-3 py-2 rounded-input text-sm" style={{ background: "var(--bg-elevated)" }}>
          This position is {ageDays.toFixed(0)} days old and still running on its
          launch-day thesis. Day-one asks &quot;am I early?&quot; — day-{Math.round(ageDays)} asks
          &quot;is anything being built, is the community growing?&quot;{" "}
          <button onClick={() => setRewriting(true)} className="font-mono-display text-xs underline" style={{ color: "var(--signal-edge)" }}>
            re-write thesis
          </button>
        </div>
      )}
      {rewriting && (
        <div className="space-y-2">
          <textarea value={newWhy} onChange={(e) => setNewWhy(e.target.value)} rows={2}
            className="w-full bg-[var(--bg-elevated)] rounded-input px-2 py-1.5 text-sm border border-[var(--border-subtle)]" />
          <textarea value={newInv} onChange={(e) => setNewInv(e.target.value)} rows={2}
            className="w-full bg-[var(--bg-elevated)] rounded-input px-2 py-1.5 text-sm border border-[var(--border-subtle)]" />
          <button
            onClick={() => {
              onChange({ ...p, why: newWhy, invalidation: newInv, thesisHistory: [...p.thesisHistory, { at: Date.now(), why: newWhy, invalidation: newInv }] });
              setRewriting(false);
            }}
            className="font-mono-display text-xs px-3 py-1.5 rounded-btn border border-[var(--border-active)]" style={{ color: "var(--signal-edge)" }}>
            SAVE NEW THESIS
          </button>
        </div>
      )}

      {/* Re-evaluation slider — auto-emphasized when the position is up big */}
      <div
        className="px-3 py-2 rounded-input"
        style={
          upBig
            ? { background: "var(--bg-elevated)", border: "1px solid var(--signal-long)" }
            : { background: "var(--bg-elevated)" }
        }
      >
        {upBig && (
          <div className="text-xs font-mono-display mb-1" style={{ color: "var(--signal-long)" }}>
            ▲ UP {pnlPct!.toFixed(0)}% — this is exactly when to re-evaluate. Greed moves the target; the question below doesn&apos;t.
          </div>
        )}
        <div className="text-sm mb-1">
          <b>Re-evaluate:</b> if you didn&apos;t own this and saw it at the current
          price right now — how much would you buy?
        </div>
        <div className="flex gap-2 items-center flex-wrap">
          <input type="number" value={wouldBuy} onChange={(e) => setWouldBuy(e.target.value)} placeholder="$ amount"
            className="w-28 bg-[var(--bg-primary)] rounded-input px-2 py-1 text-sm border border-[var(--border-subtle)] font-mono-display" />
          <button
            onClick={() => {
              const wb = Number(wouldBuy);
              if (!isFinite(wb) || wb < 0 || value === null) return;
              const suggested = Math.max(0, value - wb);
              onChange({ ...p, reevals: [...p.reevals, { at: Date.now(), wouldBuyUsd: wb, positionValueUsd: value, suggestedSellUsd: suggested }] });
              setWouldBuy("");
            }}
            className="font-mono-display text-xs px-3 py-1.5 rounded-btn border border-[var(--border-active)]" style={{ color: "var(--signal-edge)" }}>
            COMPUTE
          </button>
          {p.reevals.length > 0 && (() => {
            const last = p.reevals[p.reevals.length - 1];
            return (
              <span className="text-sm font-mono-display">
                {last.wouldBuyUsd === 0 ? (
                  <span style={{ color: "var(--signal-short)" }}>
                    You&apos;d buy nothing → that IS the signal. Suggested trim: ${last.suggestedSellUsd.toFixed(0)} (all of it).
                  </span>
                ) : (
                  <span style={{ color: last.suggestedSellUsd > 0 ? "var(--signal-neutral)" : "var(--signal-long)" }}>
                    Suggested trim: ${last.suggestedSellUsd.toFixed(0)}
                    {last.suggestedSellUsd === 0 && " — conviction intact"}
                  </span>
                )}
              </span>
            );
          })()}
        </div>
      </div>

      <div className="flex justify-end">
        <button onClick={onClose} className="font-mono-display text-xs px-3 py-1.5 rounded-btn border border-[var(--border-subtle)] text-[var(--text-secondary)] hover:text-[var(--signal-short)]">
          CLOSE POSITION
        </button>
      </div>
    </div>
  );
}

function FrictionModal({
  checks,
  onAbort,
  onProceed,
}: {
  checks: EntryCheck[];
  onAbort: () => void;
  onProceed: (() => void) | null;
}) {
  const hasBlock = checks.some((c) => c.level === "block");
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: "var(--bg-overlay)" }}>
      <div className="card max-w-md w-full space-y-3" style={{ borderColor: hasBlock ? "var(--signal-short)" : "var(--signal-neutral)" }}>
        <h3 className="font-mono-display text-lg" style={{ color: hasBlock ? "var(--signal-short)" : "var(--signal-neutral)" }}>
          {hasBlock ? "ENTRY BLOCKED" : "BEFORE YOU DO THIS"}
        </h3>
        {checks.map((c) => (
          <div key={c.title} className="text-sm">
            <b style={{ color: c.level === "block" ? "var(--signal-short)" : "var(--signal-neutral)" }}>
              {c.title}.
            </b>{" "}
            {c.detail}
          </div>
        ))}
        <div className="flex gap-2">
          <button onClick={onAbort} className="flex-1 font-mono-display text-sm px-3 py-2 rounded-btn border border-[var(--border-subtle)]">
            {hasBlock ? "OK — NOT ENTERING" : "ABORT ENTRY"}
          </button>
          {onProceed && (
            <button onClick={onProceed} className="flex-1 font-mono-display text-sm px-3 py-2 rounded-btn border border-[var(--border-active)] text-[var(--text-secondary)]">
              acknowledged, proceed anyway
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function CloseModal({
  p,
  onDone,
  onCancel,
}: {
  p: Position;
  onDone: (p: Position, rule: { text: string; maxSizePct: number | null; createdAt: number; fromSymbol: string } | null) => void;
  onCancel: () => void;
}) {
  const [exitUsd, setExitUsd] = useState("");
  const [failure, setFailure] = useState("");
  const [ruleText, setRuleText] = useState("");
  const [ruleMax, setRuleMax] = useState("");
  const exit = Number(exitUsd);
  const isLoss = isFinite(exit) && exit < p.sizeUsd;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" style={{ background: "var(--bg-overlay)" }}>
      <div className="card max-w-md w-full space-y-3">
        <h3 className="font-mono-display text-lg">CLOSE {p.symbol}</h3>
        <Input label={`Total $ out (position was $${p.sizeUsd.toFixed(0)} in)`} value={exitUsd} onChange={setExitUsd} />
        {isLoss && (
          <>
            <label className="block text-sm">
              <span className="text-xs text-[var(--text-secondary)] font-mono-display uppercase">
                Post-mortem: name the specific failure *
              </span>
              <select value={failure} onChange={(e) => setFailure(e.target.value)}
                className="w-full mt-1 bg-[var(--bg-elevated)] rounded-input px-2 py-1.5 text-sm border border-[var(--border-subtle)]">
                <option value="">choose…</option>
                {POST_MORTEM_FAILURES.map((f) => <option key={f} value={f}>{f}</option>)}
              </select>
            </label>
            <label className="block text-sm">
              <span className="text-xs text-[var(--text-secondary)] font-mono-display uppercase">
                Convert it to a concrete rule (not &quot;be more careful&quot; — a hard constraint)
              </span>
              <input value={ruleText} onChange={(e) => setRuleText(e.target.value)}
                placeholder={'e.g. "No more than 3% on memes under 500k MC"'}
                className="w-full mt-1 bg-[var(--bg-elevated)] rounded-input px-2 py-1.5 text-sm border border-[var(--border-subtle)]" />
            </label>
            <Input label="Optional: max size % this rule enforces (auto-blocks future entries)" value={ruleMax} onChange={setRuleMax} />
          </>
        )}
        <div className="flex gap-2">
          <button onClick={onCancel} className="flex-1 font-mono-display text-sm px-3 py-2 rounded-btn border border-[var(--border-subtle)]">CANCEL</button>
          <button
            onClick={() => {
              if (!isFinite(exit) || exit < 0) return;
              if (isLoss && (!failure || ruleText.trim().length < 10)) return;
              onDone(
                {
                  ...p,
                  status: "CLOSED",
                  closedAt: Date.now(),
                  exitUsd: exit,
                  postMortem: isLoss ? { failure, rule: ruleText.trim() } : p.postMortem,
                },
                isLoss && ruleText.trim()
                  ? { text: ruleText.trim(), maxSizePct: Number(ruleMax) > 0 ? Number(ruleMax) : null, createdAt: Date.now(), fromSymbol: p.symbol }
                  : null
              );
            }}
            className="flex-1 font-mono-display text-sm px-3 py-2 rounded-btn"
            style={{ background: "var(--signal-edge)", color: "var(--bg-primary)" }}>
            {isLoss ? "CLOSE + SAVE RULE" : "CLOSE"}
          </button>
        </div>
        {isLoss && (
          <p className="text-xs text-[var(--text-tertiary)]">
            The rule you write here will be quoted back to you the moment you&apos;re
            about to break it.
          </p>
        )}
      </div>
    </div>
  );
}

function MissedLog({ missed, onAdd }: { missed: MissedTrade[]; onAdd: (m: MissedTrade) => void }) {
  const [symbol, setSymbol] = useState("");
  const [kind, setKind] = useState<MissedTrade["kind"]>("found-early-didnt-buy");
  const [note, setNote] = useState("");
  const byKind = missed.reduce<Record<string, number>>((a, m) => ({ ...a, [m.kind]: (a[m.kind] ?? 0) + 1 }), {});

  return (
    <div className="card space-y-2">
      <h3 className="font-mono-display text-base">MISSED-TRADE LOG ({missed.length})</h3>
      <p className="text-xs text-[var(--text-tertiary)]">
        Misses count as failures too. If the same type of miss recurs twenty times
        without examination, the pattern never breaks.
        {missed.length >= 3 && (
          <span style={{ color: "var(--signal-neutral)" }}>
            {" "}Your pattern so far: {Object.entries(byKind).map(([k, v]) => `${k} ×${v}`).join(", ")}.
          </span>
        )}
      </p>
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-2 items-end">
        <Input label="Token" value={symbol} onChange={setSymbol} />
        <label className="block text-sm sm:col-span-2">
          <span className="text-xs text-[var(--text-secondary)] font-mono-display uppercase">What happened</span>
          <select value={kind} onChange={(e) => setKind(e.target.value as MissedTrade["kind"])}
            className="w-full mt-1 bg-[var(--bg-elevated)] rounded-input px-2 py-1.5 text-sm border border-[var(--border-subtle)]">
            <option value="found-early-didnt-buy">Found it early, didn&apos;t buy</option>
            <option value="held-past-target">Blew through my target by holding</option>
            <option value="other">Other</option>
          </select>
        </label>
        <button
          onClick={() => {
            if (!symbol.trim()) return;
            onAdd({ symbol: symbol.trim().toUpperCase(), kind, note, at: Date.now() });
            setSymbol(""); setNote("");
          }}
          className="font-mono-display text-xs px-3 py-2 rounded-btn border border-[var(--border-active)]" style={{ color: "var(--signal-edge)" }}>
          LOG MISS
        </button>
      </div>
      {missed.length > 0 && (
        <div className="text-xs text-[var(--text-secondary)] space-y-0.5">
          {[...missed].reverse().slice(0, 5).map((m, i) => (
            <div key={i}>· {m.symbol} — {m.kind.replace(/-/g, " ")} ({timeAgo(m.at)})</div>
          ))}
        </div>
      )}
    </div>
  );
}

function Input({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <label className="block text-sm">
      <span className="text-xs text-[var(--text-secondary)] font-mono-display uppercase">{label}</span>
      <input value={value} onChange={(e) => onChange(e.target.value)}
        className="w-full mt-1 bg-[var(--bg-elevated)] rounded-input px-2 py-1.5 text-sm border border-[var(--border-subtle)] font-mono-display" />
    </label>
  );
}
