import { NextResponse } from "next/server";
import WebSocket from "ws";
import { kv, kvConfigured } from "@/lib/kv";

export const dynamic = "force-dynamic";
export const maxDuration = 60;

// Graduation-rate sampler. Serverless can't hold a persistent socket, so this
// cron connects to the PumpPortal data WebSocket, subscribes to new-token and
// migration ("graduation") events, counts them for a short window, and appends
// one {at, newTokens, migrations} sample to a rolling series in Postgres. The
// trenches route averages the series into a graduation rate. This is a sampled
// ESTIMATE — accuracy improves with cron frequency (see SETUP).
//
// The API key is read from env (PUMPPORTAL_API_KEY) and never committed.

const WINDOW_MS = 25_000;
const SAMPLES_KEY = "mi:grad:samples";
const MAX_SAMPLES = 300;

interface Sample { at: number; newTokens: number; migrations: number }

function collect(url: string): Promise<{ newTokens: number; migrations: number }> {
  return new Promise((resolve) => {
    let newTokens = 0;
    let migrations = 0;
    let ws: WebSocket | null = null;
    let done = false;

    const finish = () => {
      if (done) return;
      done = true;
      try { ws?.close(); } catch { /* ignore */ }
      resolve({ newTokens, migrations });
    };

    try {
      ws = new WebSocket(url);
    } catch {
      resolve({ newTokens: 0, migrations: 0 });
      return;
    }

    const timer = setTimeout(finish, WINDOW_MS);

    ws.on("open", () => {
      ws!.send(JSON.stringify({ method: "subscribeNewToken" }));
      ws!.send(JSON.stringify({ method: "subscribeMigration" }));
    });

    ws.on("message", (raw: WebSocket.RawData) => {
      try {
        const msg = JSON.parse(raw.toString());
        const tx = String(msg?.txType ?? "").toLowerCase();
        // Migration events graduate a token off the bonding curve.
        if (tx.includes("migrat") || msg?.pool || msg?.migration) migrations++;
        else if (tx === "create" || msg?.txType === "create") newTokens++;
      } catch {
        /* ignore malformed frame */
      }
    });

    ws.on("error", () => { clearTimeout(timer); finish(); });
    ws.on("close", () => { clearTimeout(timer); finish(); });
  });
}

export async function GET() {
  if (!kvConfigured()) {
    return NextResponse.json({ ok: false, reason: "storage not configured" });
  }
  const key = process.env.PUMPPORTAL_API_KEY;
  const url = `wss://pumpportal.fun/api/data${key ? `?api-key=${encodeURIComponent(key)}` : ""}`;

  const { newTokens, migrations } = await collect(url);

  // Append to the rolling series (read-modify-write; cron runs are serialized).
  let series: Sample[] = [];
  try {
    const raw = (await kv(["GET", SAMPLES_KEY])) as string | null;
    series = raw ? JSON.parse(raw) : [];
    if (!Array.isArray(series)) series = [];
  } catch {
    series = [];
  }
  series.push({ at: Date.now(), newTokens, migrations });
  series = series.slice(-MAX_SAMPLES);
  await kv(["SET", SAMPLES_KEY, JSON.stringify(series)]);

  return NextResponse.json({ ok: true, sample: { newTokens, migrations }, samplesStored: series.length });
}
