"use client";

import { cx } from "@/lib/utils";

export interface StripState {
  meme: boolean; // memecoin signal firing
  edge: boolean; // football edge detected
  crypto: boolean; // crypto momentum shifting (any |score-50| >= 30)
}

/** The 3px live bar. Left = memecoin, middle = football, right = crypto. */
export default function SignalStrip({ state }: { state: StripState }) {
  return (
    <div className="flex w-full" aria-label="signal strip">
      <div
        className={cx("strip-segment", state.meme && "strip-meme pulse-live")}
      />
      <div
        className={cx("strip-segment", state.edge && "strip-edge pulse-live")}
      />
      <div
        className={cx(
          "strip-segment",
          state.crypto && "strip-crypto pulse-live"
        )}
      />
    </div>
  );
}
