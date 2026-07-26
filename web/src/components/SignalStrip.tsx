"use client";

import { cx } from "@/lib/utils";

/** The 3px live bar — pulses when the scanner has live signals. */
export default function SignalStrip({ active }: { active: boolean }) {
  return (
    <div className="flex w-full" aria-label="signal strip">
      <div className={cx("strip-segment", active && "strip-meme pulse-live")} />
    </div>
  );
}
