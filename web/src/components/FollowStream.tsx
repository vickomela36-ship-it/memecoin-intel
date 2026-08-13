"use client";

import { useEffect, useState } from "react";

interface Buy { mint: string; amount: number; ts: number; description: string }
interface Wallet { addr: string; label: string }

const KEY = "mi_followed_wallets_v1";

function load(): Wallet[] {
  try { return JSON.parse(localStorage.getItem(KEY) ?? "[]"); } catch { return []; }
}
function save(list: Wallet[]) {
  try { localStorage.setItem(KEY, JSON.stringify(list.slice(0, 20))); } catch { /* full */ }
}
function short(a: string) { return `${a.slice(0, 4)}…${a.slice(-4)}`; }
function ago(ts: number) {
  const h = (Date.now() - ts) / 3_600_000;
  return h < 1 ? `${Math.round(h * 60)}m` : h < 24 ? `${h.toFixed(0)}h` : `${(h / 24).toFixed(0)}d`;
}

/**
 * Follow-don't-copy: what tracked wallets have been BUYING, as an information
 * stream — never a buy signal. Carries the abuse warning loudly: a followed
 * trader can buy on private wallets first, then make a small visible buy that
 * pings followers who pile in and provide their exit liquidity.
 */
export default function FollowStream() {
  const [wallets, setWallets] = useState<Wallet[]>([]);
  const [addr, setAddr] = useState("");
  const [label, setLabel] = useState("");
  const [activity, setActivity] = useState<Record<string, Buy[]>>({});
  const [loading, setLoading] = useState<string | null>(null);

  useEffect(() => setWallets(load()), []);

  function add() {
    const m = addr.trim().match(/[A-Za-z0-9]{32,44}/);
    if (!m) return;
    const next = [...wallets.filter((w) => w.addr !== m[0]), { addr: m[0], label: label.trim() || short(m[0]) }];
    setWallets(next);
    save(next);
    setAddr("");
    setLabel("");
    void fetchActivity(m[0]);
  }
  function remove(a: string) {
    const next = wallets.filter((w) => w.addr !== a);
    setWallets(next);
    save(next);
  }
  async function fetchActivity(a: string) {
    setLoading(a);
    try {
      const r = await fetch(`/api/follow?addr=${a}`);
      const j = await r.json();
      setActivity((prev) => ({ ...prev, [a]: j.buys ?? [] }));
    } catch {
      setActivity((prev) => ({ ...prev, [a]: [] }));
    } finally {
      setLoading(null);
    }
  }

  return (
    <div className="card space-y-2">
      <h3 className="font-display text-base font-semibold">FOLLOWED WALLETS</h3>
      <div
        className="text-xs rounded-input px-3 py-2"
        style={{ background: "var(--bg-elevated)", borderLeft: "3px solid var(--signal-short)", color: "var(--signal-neutral)" }}
      >
        ⚠ Information stream — NOT a buy signal. A tracked trader can buy on private
        wallets first, then make a small visible buy to trigger followers who pile
        in and become their exit liquidity. Watch what they do; never copy it blind.
      </div>

      <div className="flex gap-2 flex-wrap">
        <input
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          placeholder="label"
          className="w-28 bg-[var(--bg-elevated)] rounded-input px-3 py-2 text-sm border border-[var(--border-subtle)] focus:border-[var(--border-active)] outline-none font-mono-display"
        />
        <input
          value={addr}
          onChange={(e) => setAddr(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && add()}
          placeholder="wallet address to follow…"
          className="flex-1 min-w-[180px] bg-[var(--bg-elevated)] rounded-input px-3 py-2 text-sm border border-[var(--border-subtle)] focus:border-[var(--border-active)] outline-none font-mono-display"
        />
        <button
          onClick={add}
          className="font-mono-display text-sm px-4 py-2 rounded-btn"
          style={{ background: "var(--signal-edge)", color: "var(--bg-primary)" }}
        >
          FOLLOW
        </button>
      </div>

      {wallets.length === 0 ? (
        <div className="text-xs text-[var(--text-tertiary)]">No wallets followed yet.</div>
      ) : (
        <div className="space-y-2">
          {wallets.map((w) => (
            <div key={w.addr} className="rounded-input px-3 py-2" style={{ background: "var(--bg-elevated)" }}>
              <div className="flex items-center justify-between">
                <span className="font-mono-display text-sm">
                  {w.label}{" "}
                  <a href={`https://solscan.io/account/${w.addr}`} target="_blank" rel="noopener noreferrer" className="text-[var(--text-tertiary)] hover:underline">
                    {short(w.addr)} ↗
                  </a>
                </span>
                <div className="flex gap-2">
                  <button onClick={() => fetchActivity(w.addr)} className="text-xs font-mono-display text-[var(--signal-edge)] hover:underline">
                    {loading === w.addr ? "loading…" : "recent buys"}
                  </button>
                  <button onClick={() => remove(w.addr)} className="text-xs text-[var(--text-tertiary)] hover:text-[var(--signal-short)]">✕</button>
                </div>
              </div>
              {activity[w.addr] && (
                activity[w.addr].length ? (
                  <ul className="mt-1 space-y-0.5 text-xs">
                    {activity[w.addr].map((b, i) => (
                      <li key={i} className="flex items-center justify-between gap-2">
                        <span className="text-[var(--text-secondary)] truncate">
                          {b.description || `bought ${short(b.mint)}`}
                        </span>
                        <span className="flex items-center gap-2 shrink-0">
                          <span className="text-[var(--text-tertiary)]">{ago(b.ts)} ago</span>
                          <button onClick={() => window.dispatchEvent(new CustomEvent("mi:goto-safety", { detail: b.mint }))} className="text-[var(--signal-edge)] hover:underline">check</button>
                        </span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <div className="mt-1 text-xs text-[var(--text-tertiary)]">No recent parsed swaps for this wallet.</div>
                )
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
