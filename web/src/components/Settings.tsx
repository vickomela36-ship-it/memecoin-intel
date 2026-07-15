"use client";

import { useEffect, useState } from "react";
import { getSyncId, getSyncStatus, linkSyncId } from "@/lib/sync";

export interface AppSettings {
  cryptoRefreshMs: number;
  memeRefreshMs: number;
}

export const DEFAULT_SETTINGS: AppSettings = {
  cryptoRefreshMs: 30_000,
  memeRefreshMs: 60_000,
};

export function loadSettings(): AppSettings {
  if (typeof window === "undefined") return DEFAULT_SETTINGS;
  try {
    const raw = window.localStorage.getItem("mi_settings");
    return raw ? { ...DEFAULT_SETTINGS, ...JSON.parse(raw) } : DEFAULT_SETTINGS;
  } catch {
    return DEFAULT_SETTINGS;
  }
}

export default function Settings({
  settings,
  onChange,
}: {
  settings: AppSettings;
  onChange: (s: AppSettings) => void;
}) {
  const [open, setOpen] = useState(false);

  function update(patch: Partial<AppSettings>) {
    const next = { ...settings, ...patch };
    onChange(next);
    try {
      window.localStorage.setItem("mi_settings", JSON.stringify(next));
    } catch {
      /* ignore */
    }
  }

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="text-[var(--text-secondary)] hover:text-[var(--text-primary)] font-mono-display text-sm px-2"
        aria-label="settings"
      >
        ⚙
      </button>
      {open && (
        <div className="absolute right-0 top-8 z-10 card w-64 space-y-3 shadow-xl">
          <div className="font-mono-display text-xs uppercase tracking-wider text-[var(--text-secondary)]">
            Refresh intervals
          </div>
          <label className="block text-sm">
            <span className="text-[var(--text-secondary)] text-xs">Perp desk</span>
            <select
              value={settings.cryptoRefreshMs}
              onChange={(e) => update({ cryptoRefreshMs: Number(e.target.value) })}
              className="w-full mt-1 bg-[var(--bg-elevated)] rounded-input px-2 py-1 text-sm border border-[var(--border-subtle)]"
            >
              <option value={30_000}>30s</option>
              <option value={60_000}>60s</option>
              <option value={300_000}>5m</option>
            </select>
          </label>
          <label className="block text-sm">
            <span className="text-[var(--text-secondary)] text-xs">Memecoin scanner</span>
            <select
              value={settings.memeRefreshMs}
              onChange={(e) => update({ memeRefreshMs: Number(e.target.value) })}
              className="w-full mt-1 bg-[var(--bg-elevated)] rounded-input px-2 py-1 text-sm border border-[var(--border-subtle)]"
            >
              <option value={30_000}>30s</option>
              <option value={60_000}>60s</option>
              <option value={300_000}>5m</option>
            </select>
          </label>
          <div className="text-xs text-[var(--text-tertiary)]">
            Football refreshes every 30m — odds are cached server-side to
            respect the 500 req/month free tier.
          </div>

          <SyncSection />
        </div>
      )}
    </div>
  );
}

function SyncSection() {
  const [syncId, setSyncId] = useState("");
  const [status, setStatus] = useState("off");
  const [linkInput, setLinkInput] = useState("");
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    setSyncId(getSyncId());
    setStatus(getSyncStatus());
    const id = setInterval(() => setStatus(getSyncStatus()), 3000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="border-t border-[var(--border-subtle)] pt-3 space-y-2">
      <div className="font-mono-display text-xs uppercase tracking-wider text-[var(--text-secondary)]">
        Device sync{" "}
        <span
          style={{
            color:
              status === "synced"
                ? "var(--signal-long)"
                : status === "error"
                  ? "var(--signal-short)"
                  : "var(--text-tertiary)",
          }}
        >
          · {status === "off" ? "local only" : status}
        </span>
      </div>
      <div className="text-xs text-[var(--text-tertiary)]">
        Your sync code is the only key to your data — treat it like a password.
        Paste it on your other device to share watchlist, positions, and
        challenge state.
      </div>
      <div className="flex gap-2 items-center">
        <code className="text-xs font-mono-display bg-[var(--bg-primary)] rounded-input px-2 py-1 break-all flex-1">
          {syncId ? `${syncId.slice(0, 10)}…${syncId.slice(-4)}` : "—"}
        </code>
        <button
          onClick={() => {
            navigator.clipboard?.writeText(syncId);
            setCopied(true);
            setTimeout(() => setCopied(false), 1500);
          }}
          className="text-xs font-mono-display px-2 py-1 rounded-btn border border-[var(--border-subtle)] text-[var(--text-secondary)]"
        >
          {copied ? "copied" : "copy"}
        </button>
      </div>
      <div className="flex gap-2">
        <input
          value={linkInput}
          onChange={(e) => setLinkInput(e.target.value)}
          placeholder="paste code from other device"
          className="flex-1 bg-[var(--bg-primary)] rounded-input px-2 py-1 text-xs border border-[var(--border-subtle)] font-mono-display"
        />
        <button
          onClick={async () => {
            const ok = await linkSyncId(linkInput.trim());
            if (ok || linkInput.trim()) window.location.reload();
          }}
          className="text-xs font-mono-display px-2 py-1 rounded-btn border border-[var(--border-active)] text-[var(--signal-edge)]"
        >
          LINK
        </button>
      </div>
    </div>
  );
}
