"use client";

import { useEffect, useRef, useState } from "react";

/**
 * A number that briefly flashes green/red when its value changes — the
 * terminal "tick" feel. The flash class is CSS-driven and is automatically
 * suppressed under `prefers-reduced-motion` (see globals.css), so this stays
 * accessible without any JS branch here.
 */
export default function TickValue({
  value,
  format,
  className = "",
}: {
  value: number;
  format: (v: number) => string;
  className?: string;
}) {
  const prev = useRef(value);
  const [flash, setFlash] = useState<"" | "tick-up" | "tick-down">("");

  useEffect(() => {
    if (value === prev.current) return;
    setFlash(value > prev.current ? "tick-up" : "tick-down");
    prev.current = value;
    const t = setTimeout(() => setFlash(""), 600);
    return () => clearTimeout(t);
  }, [value]);

  return (
    <span className={`tabular rounded-sm px-0.5 ${flash} ${className}`}>
      {format(value)}
    </span>
  );
}
