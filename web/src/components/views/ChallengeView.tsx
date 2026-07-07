"use client";

import { useState } from "react";
import {
  DEFAULT_CHALLENGE,
  getChallenge,
  logTrade,
  saveChallenge,
  startChallenge,
  type ChallengeState,
} from "@/lib/storage";
import { dailyPlayPlan, paceStatus } from "@/lib/challenge";

const STATUS_COLOR: Record<string, string> = {
  "TARGET HIT": "var(--signal-long)",
  "AHEAD OF PACE": "var(--signal-long)",
  "BEHIND PACE": "var(--signal-neutral)",
  CRITICAL: "var(--signal-short)",
};

export default function ChallengeView() {
  const [state, setState] = useState<ChallengeState>(() => getChallenge());
  const [startAmt, setStartAmt] = useState("100");
  const [targetAmt, setTargetAmt] = useState("10000");
  const [days, setDays] = useState("7");
  const [tSym, setTSym] = useState("");
  const [tIn, setTIn] = useState("");
  const [tOut, setTOut] = useState("");

  if (!state.active) {
    return (
      <div className="space-y-3">
        <div className="card">
          <h2 className="font-mono-display text-lg mb-1">
            CHALLENGE — $100 → $10,000
          </h2>
          <p className="text-sm text-[var(--text-secondary)]">
            Set your bankroll and target. Every signal card sizes its trade
            plan off your live bankroll. One rug must never end the run — the
            sizing rules exist to keep you alive long enough to compound.
          </p>
        </div>
        <div className="card grid grid-cols-1 sm:grid-cols-4 gap-3 items-end">
          <Field label="Starting bankroll ($)" value={startAmt} onChange={setStartAmt} />
          <Field label="Target ($)" value={targetAmt} onChange={setTargetAmt} />
          <Field label="Days" value={days} onChange={setDays} />
          <button
            onClick={() => {
              const s = startChallenge(
                Math.max(10, Number(startAmt) || 100),
                Math.max(100, Number(targetAmt) || 10000),
                Math.max(1, Math.floor(Number(days) || 7))
              );
              setState(s);
            }}
            className="font-mono-display text-sm px-4 py-2 rounded-btn"
            style={{
              background: "var(--signal-edge)",
              color: "var(--bg-primary)",
            }}
          >
            START CHALLENGE
          </button>
        </div>
      </div>
    );
  }

  const { status, onPace, reqMult, elapsed, daysLeft } = paceStatus(state);
  const clr = STATUS_COLOR[status];
  const progressMult = state.currentBankroll / state.startBankroll;
  const pct = Math.min(100, (state.currentBankroll / state.target) * 100);
  const wins = state.trades.filter((t) => t.pnl > 0).length;
  const { plays, reservePct } = dailyPlayPlan(state.currentBankroll);

  function submitTrade() {
    const entry = Number(tIn);
    const exit = Number(tOut);
    if (!tSym.trim() || !(entry > 0) || !(exit >= 0)) return;
    setState({ ...logTrade(tSym.trim().toUpperCase(), entry, exit) });
    setTSym("");
    setTIn("");
    setTOut("");
  }

  return (
    <div className="space-y-3">
      {/* Status banner */}
      <div
        className="card"
        style={{ borderColor: clr, background: `${clr}10` }}
      >
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div>
            <span className="font-mono-display text-2xl">
              ${state.currentBankroll.toFixed(2)}
            </span>
            <span className="text-sm text-[var(--text-secondary)] ml-2">
              of ${state.target.toLocaleString()} target
            </span>
          </div>
          <span className="font-mono-display text-lg" style={{ color: clr }}>
            {status}
          </span>
        </div>
        <div className="text-sm text-[var(--text-secondary)] mt-1">
          {progressMult.toFixed(2)}x so far · Day {elapsed.toFixed(1)} of{" "}
          {state.days} · on-pace bankroll: ${onPace.toFixed(0)}
        </div>
        <div className="h-1.5 mt-2 rounded-sm bg-[var(--bg-elevated)] overflow-hidden">
          <div
            className="h-full transition-all"
            style={{ width: `${Math.max(1, pct)}%`, background: clr }}
          />
        </div>
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        <Metric
          label="Needed / day"
          value={isFinite(reqMult) ? `${reqMult.toFixed(2)}x` : "—"}
        />
        <Metric label="Days left" value={daysLeft.toFixed(1)} />
        <Metric label="Trades" value={String(state.trades.length)} />
        <Metric
          label="Win rate"
          value={state.trades.length ? `${wins}/${state.trades.length}` : "—"}
        />
      </div>

      {/* Today's play structure */}
      <div className="card">
        <h3 className="font-mono-display text-base mb-1">
          TODAY&apos;S PLAY STRUCTURE
        </h3>
        <p className="text-xs text-[var(--text-secondary)] mb-3">
          To sustain {isFinite(reqMult) ? reqMult.toFixed(2) : "—"}x/day: run
          the core play daily, add degen shots only when the market is
          healthy. Reserve: {reservePct.toFixed(0)}% stays in cash.
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
          {plays.map((p) => (
            <div
              key={p.slot}
              className="rounded-input p-3"
              style={{ background: "var(--bg-elevated)" }}
            >
              <div className="text-xs font-mono-display text-[var(--text-secondary)] uppercase">
                {p.slot}
              </div>
              <div
                className="font-mono-display text-xl mt-1"
                style={{ color: "var(--signal-long)" }}
              >
                ${p.sizeUsd.toFixed(2)}
                <span className="text-xs text-[var(--text-tertiary)] ml-1">
                  ({(p.fraction * 100).toFixed(0)}%)
                </span>
              </div>
              <div className="text-xs text-[var(--text-secondary)] mt-1">
                Stop -{p.stopPct}% · TP {p.tp1Mult}x / {p.tp2Mult}x
              </div>
              <div className="text-xs text-[var(--text-tertiary)] mt-1">
                {p.why}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Log a trade */}
      <div className="card">
        <h3 className="font-mono-display text-base mb-2">LOG A COMPLETED TRADE</h3>
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 items-end">
          <Field label="Token symbol" value={tSym} onChange={setTSym} text />
          <Field label="$ in" value={tIn} onChange={setTIn} />
          <Field label="$ out" value={tOut} onChange={setTOut} />
          <button
            onClick={submitTrade}
            className="font-mono-display text-sm px-4 py-2 rounded-btn border border-[var(--border-active)] text-[var(--signal-edge)] hover:bg-[var(--accent-glow)]"
          >
            LOG TRADE
          </button>
        </div>
      </div>

      {/* Trade history */}
      {state.trades.length > 0 && (
        <div className="card overflow-x-auto">
          <h3 className="font-mono-display text-base mb-2">TRADE HISTORY</h3>
          <table className="data-table">
            <thead>
              <tr>
                <th>Token</th><th>In</th><th>Out</th><th>PnL</th><th>Mult</th><th>Bankroll</th>
              </tr>
            </thead>
            <tbody>
              {[...state.trades].reverse().map((t, i) => (
                <tr key={i}>
                  <td className="font-mono-display">{t.symbol}</td>
                  <td>${t.entryUsd.toFixed(2)}</td>
                  <td>${t.exitUsd.toFixed(2)}</td>
                  <td style={{ color: t.pnl >= 0 ? "var(--signal-long)" : "var(--signal-short)" }}>
                    {t.pnl >= 0 ? "+" : ""}${t.pnl.toFixed(2)}
                  </td>
                  <td className="font-mono-display">{t.multiple.toFixed(2)}x</td>
                  <td className="font-mono-display">
                    {t.bankrollAfter !== null ? `$${t.bankrollAfter.toFixed(2)}` : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="flex justify-end">
        <button
          onClick={() => {
            const next = { ...state, active: false };
            saveChallenge(next);
            setState({ ...DEFAULT_CHALLENGE, ...next });
          }}
          className="text-xs font-mono-display text-[var(--text-tertiary)] hover:text-[var(--signal-short)]"
        >
          reset challenge
        </button>
      </div>
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
  text = false,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  text?: boolean;
}) {
  return (
    <label className="block text-sm">
      <span className="text-xs text-[var(--text-secondary)] font-mono-display uppercase">
        {label}
      </span>
      <input
        type={text ? "text" : "number"}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full mt-1 bg-[var(--bg-elevated)] rounded-input px-2 py-1.5 text-sm border border-[var(--border-subtle)] focus:border-[var(--border-active)] outline-none font-mono-display"
      />
    </label>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="card">
      <div className="text-xs text-[var(--text-tertiary)] font-mono-display uppercase">
        {label}
      </div>
      <div className="font-mono-display text-xl mt-0.5">{value}</div>
    </div>
  );
}
