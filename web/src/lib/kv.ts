// Persistence adapter. Emulates the small subset of Redis commands the app
// uses (GET, SET [EX] [NX], SADD, SMEMBERS) over Postgres via Neon's serverless
// HTTP driver — so every call site keeps its existing kv([...]) interface while
// the backend is now free-tier Postgres (Neon/Supabase), not Upstash.
//
// Works with any Neon-compatible connection string in DATABASE_URL (Neon's
// Vercel integration injects it, plus POSTGRES_URL variants). Tables are
// created lazily on first use — no manual migration. When no DB is configured
// every command returns null/[], so features stay dormant instead of erroring.

import { neon, type NeonQueryFunction } from "@neondatabase/serverless";

const DB_URL =
  process.env.DATABASE_URL ??
  process.env.POSTGRES_URL ??
  process.env.POSTGRES_PRISMA_URL ??
  process.env.POSTGRES_URL_NON_POOLING;

let sql: NeonQueryFunction<false, false> | null = null;
try {
  sql = DB_URL ? neon(DB_URL) : null;
} catch {
  sql = null;
}

export function kvConfigured(): boolean {
  return !!sql;
}

let ready: Promise<void> | null = null;
function ensure(): Promise<void> {
  if (!sql) return Promise.resolve();
  if (!ready) {
    const s = sql;
    ready = (async () => {
      await s`CREATE TABLE IF NOT EXISTS kv_store (k text PRIMARY KEY, v text NOT NULL, expires_at bigint)`;
      await s`CREATE TABLE IF NOT EXISTS kv_sets (s text NOT NULL, m text NOT NULL, PRIMARY KEY (s, m))`;
    })().catch((e) => {
      // Reset so a later request can retry table creation.
      ready = null;
      throw e;
    });
  }
  return ready;
}

/**
 * Execute one Redis-style command against Postgres. Returns values shaped like
 * the Upstash REST `result` field so existing call sites are unchanged:
 *  - GET      → string | null
 *  - SET      → "OK" (or null when NX and the key already exists)
 *  - SADD     → number of members added
 *  - SMEMBERS → string[]
 */
export async function kv(cmd: (string | number)[]): Promise<unknown> {
  if (!sql) return null;
  try {
    await ensure();
    const op = String(cmd[0]).toUpperCase();

    if (op === "GET") {
      const key = String(cmd[1]);
      const rows = (await sql`SELECT v, expires_at FROM kv_store WHERE k = ${key}`) as {
        v: string;
        expires_at: number | string | null;
      }[];
      const row = rows[0];
      if (!row) return null;
      if (row.expires_at != null && Number(row.expires_at) <= Date.now()) {
        await sql`DELETE FROM kv_store WHERE k = ${key}`;
        return null;
      }
      return row.v;
    }

    if (op === "SET") {
      const key = String(cmd[1]);
      const val = String(cmd[2]);
      let expires: number | null = null;
      let nx = false;
      for (let i = 3; i < cmd.length; i++) {
        const o = String(cmd[i]).toUpperCase();
        if (o === "EX") {
          expires = Date.now() + Number(cmd[i + 1]) * 1000;
          i++;
        } else if (o === "NX") {
          nx = true;
        }
      }
      if (nx) {
        // Clear an expired key so NX can succeed after expiry, then insert.
        await sql`DELETE FROM kv_store WHERE k = ${key} AND expires_at IS NOT NULL AND expires_at <= ${Date.now()}`;
        const res = (await sql`
          INSERT INTO kv_store (k, v, expires_at) VALUES (${key}, ${val}, ${expires})
          ON CONFLICT (k) DO NOTHING RETURNING k`) as unknown[];
        return res.length ? "OK" : null;
      }
      await sql`
        INSERT INTO kv_store (k, v, expires_at) VALUES (${key}, ${val}, ${expires})
        ON CONFLICT (k) DO UPDATE SET v = EXCLUDED.v, expires_at = EXCLUDED.expires_at`;
      return "OK";
    }

    if (op === "SADD") {
      const setKey = String(cmd[1]);
      const member = String(cmd[2]);
      const res = (await sql`
        INSERT INTO kv_sets (s, m) VALUES (${setKey}, ${member})
        ON CONFLICT DO NOTHING RETURNING m`) as unknown[];
      return res.length;
    }

    if (op === "SMEMBERS") {
      const setKey = String(cmd[1]);
      const rows = (await sql`SELECT m FROM kv_sets WHERE s = ${setKey}`) as { m: string }[];
      return rows.map((r) => r.m);
    }

    return null;
  } catch {
    // Never throw from persistence — features degrade to dormant.
    return null;
  }
}
