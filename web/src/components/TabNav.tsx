"use client";

import { cx } from "@/lib/utils";
import type { TabId } from "@/types";

interface Group {
  id: string;
  label: string;
  tabs: { id: TabId; label: string }[];
}

// Grouped navigation — 3 top-level groups, each expands to its tabs.
// Everything stays one tap away (no dropdowns) and the bar stays legible
// on mobile.
const GROUPS: Group[] = [
  {
    id: "discover",
    label: "DISCOVER",
    tabs: [
      { id: "memecoin", label: "Memecoins" },
      { id: "confluence", label: "Confluence" },
      { id: "creators", label: "Creators" },
      { id: "intel", label: "Safety" },
    ],
  },
  {
    id: "desk",
    label: "MY DESK",
    tabs: [
      { id: "positions", label: "Positions" },
      { id: "portfolio", label: "Portfolio" },
      { id: "challenge", label: "Challenge" },
    ],
  },
  {
    id: "markets",
    label: "MARKETS",
    tabs: [
      { id: "crypto", label: "Perps" },
      { id: "football", label: "Football" },
    ],
  },
];

function groupOf(tab: TabId): Group {
  return GROUPS.find((g) => g.tabs.some((t) => t.id === tab)) ?? GROUPS[0];
}

export default function TabNav({
  active,
  onChange,
}: {
  active: TabId;
  onChange: (id: TabId) => void;
}) {
  const activeGroup = groupOf(active);

  return (
    <div>
      {/* Group row */}
      <nav className="flex overflow-x-auto border-b border-[var(--border-subtle)]">
        {GROUPS.map((g) => {
          const isActive = g.id === activeGroup.id;
          return (
            <button
              key={g.id}
              onClick={() => onChange(g.tabs[0].id)}
              className={cx(
                "font-mono-display px-5 py-2.5 text-sm tracking-wider transition-colors whitespace-nowrap",
                isActive
                  ? "text-[var(--text-primary)]"
                  : "text-[var(--text-tertiary)] hover:text-[var(--text-secondary)]"
              )}
              style={
                isActive
                  ? { borderBottom: "2px solid var(--signal-edge)" }
                  : undefined
              }
            >
              {g.label}
            </button>
          );
        })}
      </nav>

      {/* Sub-tab row for the active group */}
      <nav className="flex overflow-x-auto border-b border-[var(--border-subtle)] bg-[var(--bg-surface)]">
        {activeGroup.tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => onChange(t.id)}
            className={cx(
              "font-mono-display px-4 py-2 text-xs tracking-wide transition-colors whitespace-nowrap",
              active === t.id
                ? "text-[var(--signal-edge)]"
                : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
            )}
          >
            {t.label}
          </button>
        ))}
      </nav>
    </div>
  );
}
