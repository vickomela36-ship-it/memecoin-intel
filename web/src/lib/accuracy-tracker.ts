import type { ModuleAccuracy, ModuleId, SignalLog } from "@/types";

const KEY = "mi_signal_log_v1";

// Hit definitions — displayed verbatim in the Track Record panel.
export const HIT_DEFINITIONS: Record<ModuleId, string> = {
  memecoin:
    "Launch/Degen: +50% in 24h. 2x Grinder/3x Recovery/Momentum/Trending: +30%. Higher-cap: +20%.",
};

function isBrowser() {
  return typeof window !== "undefined";
}

export function getLogs(): SignalLog[] {
  if (!isBrowser()) return [];
  try {
    const raw = window.localStorage.getItem(KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function saveLogs(logs: SignalLog[]) {
  if (!isBrowser()) return;
  try {
    // Cap at 500 entries to keep localStorage sane
    window.localStorage.setItem(KEY, JSON.stringify(logs.slice(-500)));
  } catch {
    /* storage full — drop silently */
  }
}

/** Log a signal once per (module, target, type) per 12h window to avoid spam. */
export function logSignal(
  entry: Omit<SignalLog, "id" | "timestamp" | "outcome"> & {
    priceAtSignal: number;
  }
): void {
  const logs = getLogs();
  const twelveH = 12 * 3600 * 1000;
  const dup = logs.find(
    (l) =>
      l.module === entry.module &&
      l.signal.target === entry.signal.target &&
      l.signal.type === entry.signal.type &&
      Date.now() - l.timestamp < twelveH
  );
  if (dup) return;

  logs.push({
    id: `${entry.module}-${entry.signal.target}-${Date.now()}`,
    module: entry.module,
    timestamp: Date.now(),
    signal: entry.signal,
    outcome: {
      resolved: false,
      result: null,
      priceAtSignal: entry.priceAtSignal,
      priceAtResolution: null,
      resolvedAt: null,
    },
  });
  saveLogs(logs);
}

export function pendingLogs(module: ModuleId, olderThanMs: number): SignalLog[] {
  return getLogs().filter(
    (l) =>
      l.module === module &&
      !l.outcome.resolved &&
      Date.now() - l.timestamp >= olderThanMs
  );
}

export function resolveLog(
  id: string,
  result: "hit" | "miss" | "partial" | "voided",
  priceAtResolution: number | null
): void {
  const logs = getLogs();
  const log = logs.find((l) => l.id === id);
  if (!log) return;
  log.outcome.resolved = true;
  log.outcome.result = result;
  log.outcome.priceAtResolution = priceAtResolution;
  log.outcome.resolvedAt = Date.now();
  saveLogs(logs);
}

export function moduleAccuracy(module: ModuleId): ModuleAccuracy {
  const logs = getLogs().filter((l) => l.module === module);
  const resolved = logs.filter(
    (l) => l.outcome.resolved && l.outcome.result !== "voided"
  );
  const hits = resolved.filter((l) => l.outcome.result === "hit");
  return {
    module,
    fired: logs.length,
    resolved: resolved.length,
    hits: hits.length,
    hitRate: resolved.length >= 5 ? hits.length / resolved.length : null,
    note:
      resolved.length < 5
        ? `Tracking — ${resolved.length}/5 resolved signals needed before a rate is shown`
        : HIT_DEFINITIONS[module],
  };
}

/**
 * Per-signal-TYPE precision — "this flag has been right X% over N logged
 * instances." Returns null rate until >= 5 resolved so we never show a
 * meaningless number. `belowChance` flags types no better than a coin flip.
 */
export function typeAccuracy(
  module: ModuleId,
  type: string
): { resolved: number; hits: number; rate: number | null; belowChance: boolean } {
  const logs = getLogs().filter(
    (l) => l.module === module && l.signal.type === type && l.outcome.resolved && l.outcome.result !== "voided"
  );
  const hits = logs.filter((l) => l.outcome.result === "hit").length;
  const rate = logs.length >= 5 ? hits / logs.length : null;
  return {
    resolved: logs.length,
    hits,
    rate,
    belowChance: rate !== null && rate < 0.5,
  };
}

export function exportLogsJson(): string {
  return JSON.stringify(getLogs(), null, 2);
}
