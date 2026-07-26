"use client";

import { useCallback, useEffect, useState } from "react";
import SignalStrip from "@/components/SignalStrip";
import TabNav from "@/components/TabNav";
import TrackRecord from "@/components/TrackRecord";
import Settings, {
  DEFAULT_SETTINGS,
  loadSettings,
  type AppSettings,
} from "@/components/Settings";
import dynamic from "next/dynamic";
import MemeView from "@/components/views/MemeView";
import type { TabId } from "@/types";
import { initSync } from "@/lib/sync";

// Code-split every non-default surface so opening the Scanner never ships
// Confluence/Safety/Creators/Positions/Portfolio/Challenge JS. They only
// load when their tab is first opened.
function PanelSkeleton() {
  return <div className="card text-sm text-[var(--text-secondary)]">Loading…</div>;
}

const ConfluenceView = dynamic(() => import("@/components/views/ConfluenceView"), { loading: PanelSkeleton, ssr: false });
const IntelView = dynamic(() => import("@/components/views/IntelView"), { loading: PanelSkeleton, ssr: false });
const CreatorsView = dynamic(() => import("@/components/views/CreatorsView"), { loading: PanelSkeleton, ssr: false });
const PositionsView = dynamic(() => import("@/components/views/PositionsView"), { loading: PanelSkeleton, ssr: false });
const PortfolioView = dynamic(() => import("@/components/views/PortfolioView"), { loading: PanelSkeleton, ssr: false });
const ChallengeView = dynamic(() => import("@/components/views/ChallengeView"), { loading: PanelSkeleton, ssr: false });
const Education = dynamic(() => import("@/components/Education"), { ssr: false });
const WatchSafetyPopup = dynamic(() => import("@/components/WatchSafetyPopup"), { ssr: false });

export default function Home() {
  const [tab, setTab] = useState<TabId>("memecoin");
  const [memeActive, setMemeActive] = useState(false);
  const [settings, setSettings] = useState<AppSettings>(DEFAULT_SETTINGS);
  const [trackKey, setTrackKey] = useState(0);
  const [showEdu, setShowEdu] = useState(false);

  useEffect(() => {
    setSettings(loadSettings());
    // One-time security onboarding on first ever load
    if (!localStorage.getItem("mi_edu_seen")) {
      localStorage.setItem("mi_edu_seen", "1");
      setShowEdu(true);
    }
    // Signal cards can deep-link into the Safety tab. The Safety view mounts
    // AFTER this event fires, so stash the CA for it to consume on mount.
    const onGotoSafety = (e: Event) => {
      const addr = (e as CustomEvent<string>).detail;
      if (addr) sessionStorage.setItem("mi_pending_safety", addr);
      setTab("intel");
    };
    window.addEventListener("mi:goto-safety", onGotoSafety);
    // Cross-device sync: pull remote state on boot, push changes every 20s.
    const cleanupSync = initSync(() => {
      if (!sessionStorage.getItem("mi_sync_applied")) {
        sessionStorage.setItem("mi_sync_applied", "1");
        window.location.reload();
      }
    });
    return () => {
      window.removeEventListener("mi:goto-safety", onGotoSafety);
      cleanupSync();
    };
  }, []);

  const onMeme = useCallback((v: boolean) => setMemeActive(v), []);
  const onLogged = useCallback(() => setTrackKey((k) => k + 1), []);

  return (
    <main className="min-h-screen max-w-5xl mx-auto flex flex-col">
      {/* Signal strip — the 3-second answer to "anything worth looking at?" */}
      <div className="sticky top-0 z-20 bg-[var(--bg-primary)]">
        <SignalStrip active={memeActive} />
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
            <button
              onClick={() => setShowEdu(true)}
              className="text-[var(--text-secondary)] hover:text-[var(--text-primary)] font-mono-display text-sm px-1"
              aria-label="help"
            >
              ?
            </button>
            <Settings settings={settings} onChange={setSettings} />
          </div>
        </header>
        <TabNav active={tab} onChange={setTab} />
      </div>

      <div className="flex-1 px-4 py-4">
        <div style={{ display: tab === "memecoin" ? "block" : "none" }}>
          <MemeView
            onStatus={onMeme}
            refreshInterval={settings.memeRefreshMs}
            onLogged={onLogged}
          />
        </div>
        {tab === "confluence" && <ConfluenceView />}
        {tab === "intel" && <IntelView />}
        {tab === "creators" && <CreatorsView />}
        {tab === "positions" && <PositionsView />}
        {tab === "challenge" && <ChallengeView />}
        {tab === "portfolio" && <PortfolioView />}
      </div>

      {showEdu && <Education onClose={() => setShowEdu(false)} />}
      <WatchSafetyPopup />

      <TrackRecord refreshKey={trackKey} />
    </main>
  );
}
