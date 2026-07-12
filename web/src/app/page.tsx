"use client";

import { useCallback, useEffect, useState } from "react";
import SignalStrip, { type StripState } from "@/components/SignalStrip";
import TabNav from "@/components/TabNav";
import TrackRecord from "@/components/TrackRecord";
import Settings, {
  DEFAULT_SETTINGS,
  loadSettings,
  type AppSettings,
} from "@/components/Settings";
import CryptoView from "@/components/views/CryptoView";
import MemeView from "@/components/views/MemeView";
import FootballView from "@/components/views/FootballView";
import ChallengeView from "@/components/views/ChallengeView";
import PortfolioView from "@/components/views/PortfolioView";
import ConfluenceView from "@/components/views/ConfluenceView";
import type { TabId } from "@/types";

export default function Home() {
  const [tab, setTab] = useState<TabId>("memecoin");
  const [strip, setStrip] = useState<StripState>({
    meme: false,
    edge: false,
    crypto: false,
  });
  const [settings, setSettings] = useState<AppSettings>(DEFAULT_SETTINGS);
  const [trackKey, setTrackKey] = useState(0);

  useEffect(() => {
    setSettings(loadSettings());
  }, []);

  const onMeme = useCallback(
    (v: boolean) => setStrip((s) => (s.meme === v ? s : { ...s, meme: v })),
    []
  );
  const onEdge = useCallback(
    (v: boolean) => setStrip((s) => (s.edge === v ? s : { ...s, edge: v })),
    []
  );
  const onCrypto = useCallback(
    (v: boolean) => setStrip((s) => (s.crypto === v ? s : { ...s, crypto: v })),
    []
  );
  const onLogged = useCallback(() => setTrackKey((k) => k + 1), []);

  return (
    <main className="min-h-screen max-w-5xl mx-auto flex flex-col">
      {/* Signal strip — the 3-second answer to "anything worth looking at?" */}
      <div className="sticky top-0 z-20 bg-[var(--bg-primary)]">
        <SignalStrip state={strip} />
        <header className="flex items-center justify-between px-4 py-3 border-b border-[var(--border-subtle)]">
          <h1 className="font-mono-display text-lg tracking-widest">
            MEMECOIN&nbsp;INTEL
          </h1>
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-1.5 text-xs font-mono-display text-[var(--text-secondary)]">
              <span
                className="inline-block w-1.5 h-1.5 rounded-full pulse-live"
                style={{ background: "var(--signal-long)" }}
              />
              Live
            </span>
            <Settings settings={settings} onChange={setSettings} />
          </div>
        </header>
        <TabNav active={tab} onChange={setTab} />
      </div>

      <div className="flex-1 px-4 py-4">
        {/* Data modules stay mounted so the strip reflects ALL of them —
            display:none the inactive ones. Challenge/Portfolio mount on
            demand so they re-read localStorage each visit. */}
        <div style={{ display: tab === "memecoin" ? "block" : "none" }}>
          <MemeView
            onStatus={onMeme}
            refreshInterval={settings.memeRefreshMs}
            onLogged={onLogged}
          />
        </div>
        <div style={{ display: tab === "football" ? "block" : "none" }}>
          <FootballView onStatus={onEdge} onLogged={onLogged} />
        </div>
        <div style={{ display: tab === "crypto" ? "block" : "none" }}>
          <CryptoView
            onStatus={onCrypto}
            refreshInterval={settings.cryptoRefreshMs}
            onLogged={onLogged}
          />
        </div>
        {tab === "confluence" && <ConfluenceView />}
        {tab === "challenge" && <ChallengeView />}
        {tab === "portfolio" && <PortfolioView />}
      </div>

      <TrackRecord refreshKey={trackKey} />
    </main>
  );
}
