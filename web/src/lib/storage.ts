// localStorage-backed stores for watchlist, trades, and challenge state.

export interface WatchItem {
  address: string;
  symbol: string;
  name: string;
  entryPrice: number;
  target2x: number;
  grade: string;
  pairUrl: string;
  addedAt: number;
}

export interface TradeEntry {
  symbol: string;
  entryUsd: number;
  exitUsd: number;
  pnl: number;
  multiple: number;
  bankrollAfter: number | null;
  note: string;
  at: number;
}

export interface ChallengeState {
  active: boolean;
  startBankroll: number;
  target: number;
  days: number;
  currentBankroll: number;
  startedAt: number | null;
  trades: TradeEntry[];
}

export const DEFAULT_CHALLENGE: ChallengeState = {
  active: false,
  startBankroll: 100,
  target: 10_000,
  days: 7,
  currentBankroll: 100,
  startedAt: null,
  trades: [],
};

const WATCH_KEY = "mi_watchlist_v1";
const CHALLENGE_KEY = "mi_challenge_v1";

function read<T>(key: string, fallback: T): T {
  if (typeof window === "undefined") return fallback;
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? { ...fallback, ...JSON.parse(raw) } : fallback;
  } catch {
    return fallback;
  }
}

function readArray<T>(key: string): T[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(key);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function write(key: string, value: unknown) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* storage full */
  }
}

// ── Watchlist ─────────────────────────────────────────────────────────────

export function getWatchlist(): WatchItem[] {
  return readArray<WatchItem>(WATCH_KEY);
}

export function addWatch(item: Omit<WatchItem, "addedAt">): boolean {
  const list = getWatchlist();
  if (list.some((w) => w.address === item.address)) return false;
  list.push({ ...item, addedAt: Date.now() });
  write(WATCH_KEY, list);
  return true;
}

export function removeWatch(address: string) {
  write(
    WATCH_KEY,
    getWatchlist().filter((w) => w.address !== address)
  );
}

// ── Challenge ─────────────────────────────────────────────────────────────

export function getChallenge(): ChallengeState {
  return read<ChallengeState>(CHALLENGE_KEY, DEFAULT_CHALLENGE);
}

export function saveChallenge(state: ChallengeState) {
  write(CHALLENGE_KEY, state);
}

export function startChallenge(
  startBankroll: number,
  target: number,
  days: number
): ChallengeState {
  const state: ChallengeState = {
    active: true,
    startBankroll,
    target,
    days,
    currentBankroll: startBankroll,
    startedAt: Date.now(),
    trades: [],
  };
  saveChallenge(state);
  return state;
}

export function logTrade(
  symbol: string,
  entryUsd: number,
  exitUsd: number,
  note = ""
): ChallengeState {
  const state = getChallenge();
  const pnl = exitUsd - entryUsd;
  const bankrollAfter = state.active
    ? Math.max(0, state.currentBankroll + pnl)
    : null;
  if (state.active && bankrollAfter !== null) {
    state.currentBankroll = bankrollAfter;
  }
  state.trades.push({
    symbol,
    entryUsd,
    exitUsd,
    pnl,
    multiple: entryUsd > 0 ? exitUsd / entryUsd : 0,
    bankrollAfter,
    note,
    at: Date.now(),
  });
  saveChallenge(state);
  return state;
}
