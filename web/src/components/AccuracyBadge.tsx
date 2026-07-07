"use client";

import { useEffect, useState } from "react";
import { moduleAccuracy } from "@/lib/accuracy-tracker";
import type { ModuleAccuracy, ModuleId } from "@/types";

/** Honest historical accuracy line — shows sample size, never a fake number. */
export default function AccuracyBadge({ module }: { module: ModuleId }) {
  const [acc, setAcc] = useState<ModuleAccuracy | null>(null);

  useEffect(() => {
    setAcc(moduleAccuracy(module));
  }, [module]);

  if (!acc) return null;

  return (
    <div className="text-xs text-[var(--text-tertiary)] font-mono-display border-t border-[var(--border-subtle)] pt-2 mt-2">
      {acc.hitRate !== null ? (
        <>
          Historical: {(acc.hitRate * 100).toFixed(0)}% hit rate on{" "}
          {acc.resolved} resolved signals ({acc.fired} fired). {acc.note}
        </>
      ) : (
        <>
          Track record building: {acc.fired} signals fired, {acc.resolved}{" "}
          resolved. {acc.note}.
        </>
      )}
    </div>
  );
}
