"use client";

import { useState } from "react";

interface MinedWord { word: string; count: number; share: number }
interface Match {
  exists: boolean;
  exactMatch: boolean;
  symbol: string;
  address: string;
  mcap: number;
  vol24: number;
}
interface Resp { words?: MinedWord[]; top?: string | null; match?: Match | null; error?: string }

/**
 * Paste discourse (an announcement, article, thread) → the most-repeated
 * distinctive word, and whether a token already exists for it. Catches the
 * "every article repeats one word, a token launches on nothing but that word"
 * pattern. The corpus is user-supplied; nothing is scraped.
 */
export default function NarrativeMiner() {
  const [text, setText] = useState("");
  const [resp, setResp] = useState<Resp | null>(null);
  const [loading, setLoading] = useState(false);

  async function mine() {
    setLoading(true);
    setResp(null);
    try {
      const r = await fetch("/api/narrative", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      setResp(await r.json());
    } catch {
      setResp({ error: "Miner unreachable — try again." });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="card space-y-2">
      <h3 className="font-display text-base font-semibold">NARRATIVE MINER</h3>
      <p className="text-xs text-[var(--text-tertiary)]">
        Paste the discourse around a launch or event — an article, an announcement, a
        thread. The tool surfaces the word everyone is repeating and checks whether a
        token already exists for it. The word is the narrative; find it before the crowd names it.
      </p>
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Paste an article, announcement, or thread…"
        rows={4}
        className="w-full bg-[var(--bg-elevated)] rounded-input px-3 py-2 text-sm border border-[var(--border-subtle)] focus:border-[var(--border-active)] outline-none resize-y"
      />
      <button
        onClick={mine}
        disabled={loading || text.trim().length < 20}
        className="font-mono-display text-sm px-4 py-1.5 rounded-btn disabled:opacity-40"
        style={{ background: "var(--signal-edge)", color: "var(--bg-primary)" }}
      >
        {loading ? "MINING…" : "MINE NARRATIVE"}
      </button>

      {resp?.error && <div className="text-xs" style={{ color: "var(--signal-short)" }}>{resp.error}</div>}

      {resp?.words && resp.words.length > 0 && (
        <div className="space-y-2">
          <div className="flex flex-wrap gap-1.5">
            {resp.words.map((w, i) => (
              <span
                key={w.word}
                className="font-mono-display text-xs px-2 py-0.5 rounded-input"
                style={{
                  background: "var(--bg-elevated)",
                  color: i === 0 ? "var(--signal-edge)" : "var(--text-secondary)",
                  border: i === 0 ? "1px solid var(--border-active)" : "1px solid var(--border-subtle)",
                }}
              >
                {w.word} ×{w.count}
              </span>
            ))}
          </div>
          <div className="rounded-input px-3 py-2 text-xs" style={{ background: "var(--bg-elevated)" }}>
            Dominant word: <b className="text-[var(--signal-edge)]">&quot;{resp.top}&quot;</b> —{" "}
            {resp.match ? (
              <>
                a token already exists:{" "}
                <button
                  onClick={() => window.dispatchEvent(new CustomEvent("mi:goto-safety", { detail: resp.match!.address }))}
                  className="font-mono-display text-[var(--signal-long)] hover:underline"
                >
                  ${resp.match.symbol}
                </button>{" "}
                {resp.match.exactMatch ? "(exact name match)" : "(closest match)"} · $
                {(resp.match.mcap / 1000).toFixed(0)}K mcap · ${(resp.match.vol24 / 1000).toFixed(0)}K vol.
                {resp.match.exactMatch
                  ? " Canonical name — the crowd hasn't left much room, but it's the right coin."
                  : " No exact-name coin yet — a correctly-named launch could still take the narrative."}
              </>
            ) : (
              <span style={{ color: "var(--signal-neutral)" }}>
                no Solana token exists for this word yet. If the narrative catches, the first
                correctly-named coin tends to win it.
              </span>
            )}
          </div>
        </div>
      )}

      {resp?.words && resp.words.length === 0 && (
        <div className="text-xs text-[var(--text-tertiary)]">
          No word repeats enough to be a narrative. Paste more of the discourse.
        </div>
      )}
    </div>
  );
}
