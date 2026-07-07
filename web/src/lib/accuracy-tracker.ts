import type { ModuleAccuracy, ModuleId, SignalLog } from "@/types";

const KEY = "mi_signal_log_v1";

// Hit definitions — displayed verbatim in the Track Record panel.
export const HIT_DEFINITIONS: Record<ModuleId, string> = {
  memecoin:
    "Launch/Degen: +50% within 24h. Recovery (low & higher cap): +20% within 24h.",
  football: "STRONG binary call (fair ≥ 60%) wins the match.",
  crypto: "Perp bias (LONG/SHORT) matches sign of the next 24h move.",
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

export function exportLogsJson(): string {
  return JSON.stringify(getLogs(), null, 2);
}
