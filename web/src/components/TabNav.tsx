"use client";

import { cx } from "@/lib/utils";
import type { TabId } from "@/types";

const TABS: { id: TabId; label: string }[] = [
  { id: "memecoin", label: "MEMECOINS" },
  { id: "challenge", label: "CHALLENGE" },
  { id: "portfolio", label: "PORTFOLIO" },
  { id: "football", label: "FOOTBALL" },
  { id: "crypto", label: "CRYPTO SCORE" },
];

export default function TabNav({
  active,
  onChange,
}: {
  active: TabId;
  onChange: (id: TabId) => void;
}) {
  return (
    <nav className="flex overflow-x-auto border-b border-[var(--border-subtle)]">
      {TABS.map((t) => (
        <button
          key={t.id}
          onClick={() => onChange(t.id)}
          className={cx(
            "font-mono-display px-4 py-3 text-sm tracking-wider transition-colors whitespace-nowrap",
            active === t.id
              ? "text-[var(--text-primary)] border-b-2 border-[var(--signal-edge)]"
              : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
          )}
        >
          {t.label}
        </button>
      ))}
    </nav>
  );
}
