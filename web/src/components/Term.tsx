"use client";

import { useState } from "react";
import { lookupTerm } from "@/lib/glossary";

/**
 * Inline glossary term — a dotted-underlined word that reveals its plain-English
 * definition on hover or tap. Keeps jargon explained at the point of use
 * instead of only in a separate modal. If the key isn't in the glossary it
 * renders the label as plain text (never breaks the sentence).
 */
export default function Term({ k, children }: { k: string; children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const entry = lookupTerm(k);
  if (!entry) return <>{children}</>;

  return (
    <span
      className="relative inline"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
    >
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="underline decoration-dotted underline-offset-2 cursor-help"
        style={{ textDecorationColor: "var(--text-tertiary)" }}
        aria-label={`definition of ${entry.term}`}
      >
        {children}
      </button>
      {open && (
        <span
          role="tooltip"
          className="absolute left-0 bottom-full mb-1 z-30 block w-60 rounded-input px-3 py-2 text-xs font-normal normal-case tracking-normal"
          style={{
            background: "var(--bg-overlay)",
            border: "1px solid var(--border-active)",
            color: "var(--text-secondary)",
            boxShadow: "0 4px 20px rgba(0,0,0,0.5)",
          }}
        >
          <b className="text-[var(--text-primary)]">{entry.term}</b> — {entry.def}
        </span>
      )}
    </span>
  );
}
