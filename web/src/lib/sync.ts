// Cross-device sync engine. Whole-snapshot, last-writer-wins:
// every localStorage store is bundled, pushed when changed, and pulled
// on load. The sync ID is the only credential — treat it like a password.

export const SYNC_KEYS = [
  "mi_watchlist_v1",
  "mi_challenge_v1",
  "mi_signal_log_v1",
  "mi_discipline_profile_v1",
  "mi_positions_v1",
  "mi_missed_trades_v1",
  "mi_settings",
];

const ID_KEY = "mi_sync_id";
const LAST_PUSH_KEY = "mi_sync_lastpush";
const LAST_HASH_KEY = "mi_sync_lasthash";

function isBrowser() {
  return typeof window !== "undefined";
}

export function getSyncId(): string {
  if (!isBrowser()) return "";
  let id = window.localStorage.getItem(ID_KEY);
  if (!id) {
    id = (crypto.randomUUID() + crypto.randomUUID()).replace(/-/g, "").slice(0, 48);
    window.localStorage.setItem(ID_KEY, id);
  }
  return id;
}

/** Link this device to an existing sync ID (from your other device). */
export async function linkSyncId(id: string): Promise<boolean> {
  if (!isBrowser() || !/^[A-Za-z0-9-]{20,80}$/.test(id)) return false;
  window.localStorage.setItem(ID_KEY, id);
  window.localStorage.removeItem(LAST_PUSH_KEY);
  window.localStorage.removeItem(LAST_HASH_KEY);
  const changed = await pullRemote(true);
  return changed;
}

function serializeStores(): { stores: Record<string, string | null>; str: string } {
  const stores: Record<string, string | null> = {};
  for (const key of SYNC_KEYS) {
    stores[key] = window.localStorage.getItem(key);
  }
  return { stores, str: JSON.stringify(stores) };
}

function djb2(str: string): string {
  let h = 5381;
  for (let i = 0; i < str.length; i++) {
    h = ((h << 5) + h + str.charCodeAt(i)) | 0;
  }
  return String(h);
}

export type SyncStatus = "off" | "synced" | "pushing" | "error";
let status: SyncStatus = "off";
export function getSyncStatus(): SyncStatus {
  return status;
}

/** Pull remote snapshot; apply if newer than our last push (or forced). */
export async function pullRemote(force = false): Promise<boolean> {
  if (!isBrowser()) return false;
  try {
    const res = await fetch(`/api/sync?id=${getSyncId()}`, { cache: "no-store" });
    if (res.status === 503) {
      status = "off"; // KV not configured — local-only mode
      return false;
    }
    if (!res.ok) {
      status = "error";
      return false;
    }
    const data = await res.json();
    const snap = data?.snapshot as
      | { stores: Record<string, string | null>; snapshotAt: number }
      | null;
    status = "synced";
    if (!snap?.stores) return false;

    const lastPush = Number(window.localStorage.getItem(LAST_PUSH_KEY) ?? 0);
    if (!force && snap.snapshotAt <= lastPush) return false;

    let changed = false;
    for (const key of SYNC_KEYS) {
      const remote = snap.stores[key] ?? null;
      const local = window.localStorage.getItem(key);
      if (remote === local) continue;
      if (remote === null) window.localStorage.removeItem(key);
      else window.localStorage.setItem(key, remote);
      changed = true;
    }
    window.localStorage.setItem(LAST_PUSH_KEY, String(snap.snapshotAt));
    window.localStorage.setItem(LAST_HASH_KEY, djb2(JSON.stringify(snap.stores)));
    return changed;
  } catch {
    status = "error";
    return false;
  }
}

/** Push the full snapshot if anything changed since the last push. */
export async function pushIfChanged(): Promise<void> {
  if (!isBrowser() || status === "off") return;
  const { stores, str } = serializeStores();
  const hash = djb2(str);
  if (window.localStorage.getItem(LAST_HASH_KEY) === hash) return;

  status = "pushing";
  try {
    const snapshotAt = Date.now();
    const res = await fetch("/api/sync", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: getSyncId(), snapshot: { stores, snapshotAt } }),
    });
    if (res.ok) {
      window.localStorage.setItem(LAST_HASH_KEY, hash);
      window.localStorage.setItem(LAST_PUSH_KEY, String(snapshotAt));
      status = "synced";
    } else {
      status = res.status === 503 ? "off" : "error";
    }
  } catch {
    status = "error";
  }
}

/** Start the sync loop. Returns cleanup. */
export function initSync(onRemoteApplied: () => void): () => void {
  if (!isBrowser()) return () => {};
  let stopped = false;

  (async () => {
    const changed = await pullRemote();
    if (changed && !stopped) onRemoteApplied();
    // First push establishes the snapshot for brand-new sync IDs
    await pushIfChanged();
  })();

  const interval = setInterval(pushIfChanged, 20_000);
  const onHide = () => {
    void pushIfChanged();
  };
  window.addEventListener("pagehide", onHide);
  document.addEventListener("visibilitychange", onHide);

  return () => {
    stopped = true;
    clearInterval(interval);
    window.removeEventListener("pagehide", onHide);
    document.removeEventListener("visibilitychange", onHide);
  };
}
