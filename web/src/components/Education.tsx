"use client";

import { useEffect, useState } from "react";
import { GLOSSARY } from "@/lib/glossary";

interface FeatureStatus { key: string; label: string; live: boolean; powers: string; detail?: string }

/** Shows which env-backed features are live vs dormant on this deployment. */
function StatusTab() {
  const [features, setFeatures] = useState<FeatureStatus[] | null>(null);
  useEffect(() => {
    fetch("/api/status")
      .then((r) => r.json())
      .then((d) => setFeatures(d.features ?? []))
      .catch(() => setFeatures([]));
  }, []);

  if (!features) return <div className="text-sm text-[var(--text-tertiary)]">Checking…</div>;

  return (
    <div className="space-y-2">
      <div className="text-sm text-[var(--text-secondary)]">
        What&apos;s connected on this deployment. Dormant features work the moment
        their key is set — see <code>SETUP.md</code> in the repo.
      </div>
      {features.map((f) => (
        <div key={f.key} className="rounded-input px-3 py-2" style={{ background: "var(--bg-elevated)" }}>
          <div className="flex items-center justify-between">
            <span className="font-mono-display text-sm">{f.label}</span>
            <span
              className="font-mono-display text-xs px-2 py-0.5 rounded-input"
              style={{
                color: f.live ? "var(--signal-long)" : "var(--signal-neutral)",
                border: `1px solid ${f.live ? "var(--signal-long)" : "var(--signal-neutral)"}`,
              }}
            >
              {f.live ? `● LIVE${f.detail && f.detail !== "none" ? ` · ${f.detail}` : ""}` : "○ DORMANT"}
            </span>
          </div>
          <div className="text-xs text-[var(--text-tertiary)] mt-0.5">{f.powers}</div>
        </div>
      ))}
    </div>
  );
}

const SECURITY: string[] = [
  "Use a SEPARATE trading wallet from the wallet you connect to random sites.",
  "Write your seed phrase on paper or metal — never in a notes app, screenshot, or cloud.",
  "Keep meaningful size in a cold/hardware wallet, not your hot trading wallet.",
  "Buy hardware wallets ONLY from the manufacturer, never a marketplace reseller.",
  "Type URLs manually or use bookmarks. Never click a wallet/exchange link someone sent you.",
  "No legitimate support — ever — asks for your seed phrase. Anyone who does is a thief.",
  "Never disclose your portfolio size. It paints a target on you.",
];

const KNOWN_DOMAINS = [
  "dexscreener.com", "birdeye.so", "rugcheck.xyz", "jup.ag", "raydium.io",
  "pump.fun", "solscan.io", "phantom.app", "solflare.com", "binance.com",
  "bybit.com", "coingecko.com", "x.com", "twitter.com",
];

function checkUrl(raw: string): { level: "ok" | "warn" | "danger"; msg: string } {
  let host: string;
  try {
    host = new URL(raw.includes("://") ? raw : `https://${raw}`).hostname.toLowerCase().replace(/^www\./, "");
  } catch {
    return { level: "warn", msg: "Not a valid URL." };
  }
  if (KNOWN_DOMAINS.includes(host)) return { level: "ok", msg: `${host} is a known-legitimate domain.` };

  // Lookalike detection: close to a known domain but not exactly it
  for (const legit of KNOWN_DOMAINS) {
    const base = legit.split(".")[0];
    if (host.includes(base) && host !== legit) {
      return {
        level: "danger",
        msg: `⚠ "${host}" mimics "${legit}" but is NOT it. Classic phishing lookalike — do not connect your wallet.`,
      };
    }
  }
  // Suspicious TLDs common in scams
  if (/\.(xyz|top|click|gift|app\.link|com-[a-z]+)$/i.test(host) && !KNOWN_DOMAINS.includes(host)) {
    return { level: "warn", msg: `"${host}" isn't on the known list and uses a scam-common pattern. Verify independently.` };
  }
  return { level: "warn", msg: `"${host}" isn't on the known-legitimate list. Double-check before connecting a wallet.` };
}

export default function Education({ onClose }: { onClose: () => void }) {
  const [tab, setTab] = useState<"glossary" | "security" | "phishing" | "status">("glossary");
  const [url, setUrl] = useState("");
  const [result, setResult] = useState<ReturnType<typeof checkUrl> | null>(null);

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center p-4 overflow-y-auto" style={{ background: "var(--bg-overlay)" }}>
      <div className="card max-w-2xl w-full my-8 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex gap-2">
            {(["glossary", "security", "phishing", "status"] as const).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className="font-mono-display text-xs px-3 py-1.5 rounded-btn"
                style={{
                  color: tab === t ? "var(--text-primary)" : "var(--text-secondary)",
                  borderBottom: tab === t ? "2px solid var(--signal-edge)" : "2px solid transparent",
                }}
              >
                {t === "glossary" ? "GLOSSARY" : t === "security" ? "SECURITY" : t === "phishing" ? "URL CHECK" : "STATUS"}
              </button>
            ))}
          </div>
          <button onClick={onClose} className="font-mono-display text-sm text-[var(--text-secondary)] px-2">✕</button>
        </div>

        {tab === "glossary" && (
          <div className="space-y-2 max-h-[70vh] overflow-y-auto">
            {GLOSSARY.map((g) => (
              <div key={g.term} className="rounded-input px-3 py-2" style={{ background: "var(--bg-elevated)" }}>
                <b className="font-mono-display text-sm">{g.term}</b>
                <div className="text-xs text-[var(--text-secondary)] mt-0.5">{g.def}</div>
              </div>
            ))}
          </div>
        )}

        {tab === "security" && (
          <div className="space-y-2">
            <div className="text-sm text-[var(--text-secondary)]">
              The fastest way to lose everything isn&apos;t a bad trade — it&apos;s a drained wallet. Do these once.
            </div>
            {SECURITY.map((s, i) => (
              <div key={i} className="flex gap-2 text-sm rounded-input px-3 py-2" style={{ background: "var(--bg-elevated)" }}>
                <span style={{ color: "var(--signal-long)" }}>✓</span>
                <span>{s}</span>
              </div>
            ))}
          </div>
        )}

        {tab === "phishing" && (
          <div className="space-y-3">
            <div className="text-sm text-[var(--text-secondary)]">
              Paste a URL before connecting your wallet. This flags lookalike domains
              against known-legitimate crypto sites — but it can&apos;t catch everything,
              so verify independently.
            </div>
            <div className="flex gap-2">
              <input
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && setResult(checkUrl(url))}
                placeholder="paste URL…"
                className="flex-1 bg-[var(--bg-elevated)] rounded-input px-3 py-2 text-sm border border-[var(--border-subtle)] font-mono-display"
              />
              <button
                onClick={() => setResult(checkUrl(url))}
                className="font-mono-display text-sm px-4 py-2 rounded-btn"
                style={{ background: "var(--signal-edge)", color: "var(--bg-primary)" }}
              >
                CHECK
              </button>
            </div>
            {result && (
              <div
                className="rounded-input px-3 py-2 text-sm"
                style={{
                  border: `1px solid ${result.level === "ok" ? "var(--signal-long)" : result.level === "danger" ? "var(--signal-short)" : "var(--signal-neutral)"}`,
                  color: result.level === "ok" ? "var(--signal-long)" : result.level === "danger" ? "var(--signal-short)" : "var(--signal-neutral)",
                }}
              >
                {result.msg}
              </div>
            )}
          </div>
        )}

        {tab === "status" && <StatusTab />}

        <div className="text-xs text-[var(--text-tertiary)] border-t border-[var(--border-subtle)] pt-2">
          Informed traders are more profitable traders — but nothing here is
          financial advice, and memecoin trading carries substantial risk of total loss.
        </div>
      </div>
    </div>
  );
}
