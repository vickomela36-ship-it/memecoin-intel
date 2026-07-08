import { NextRequest, NextResponse } from "next/server";
import { cachedScan } from "@/lib/scan-cache";
import type { MemeSignal } from "@/types";

export const dynamic = "force-dynamic";
// Run in Frankfurt: Binance/Bybit geo-block US datacenter IPs, and Vercel's
// default region is US. EU region lets the perp check work server-side.
export const preferredRegion = ["fra1"];
export const maxDuration = 60;

const TG = "https://api.telegram.org";

// In-memory dedup — survives while the lambda stays warm. Cold starts may
// occasionally re-alert; real persistence arrives with the KV upgrade.
const alerted = new Map<string, number>();
const DEDUP_MS = 6 * 3600 * 1000;

function shouldAlert(key: string): boolean {
  const now = Date.now();
  // prune
  alerted.forEach((t, k) => {
    if (now - t > DEDUP_MS) alerted.delete(k);
  });
  if (alerted.has(key)) return false;
  alerted.set(key, now);
  return true;
}

async function tgCall<T>(token: string, method: string, body?: object): Promise<T | null> {
  try {
    const res = await fetch(`${TG}/bot${token}/${method}`, {
      method: body ? "POST" : "GET",
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
      cache: "no-store",
    });
    const data = await res.json();
    return data?.ok ? (data.result as T) : null;
  } catch {
    return null;
  }
}

/** Chat ID from env, or auto-detected from the bot's latest received message. */
async function resolveChatId(token: string): Promise<string | null> {
  if (process.env.TELEGRAM_CHAT_ID) return process.env.TELEGRAM_CHAT_ID;
  const updates = await tgCall<{ message?: { chat?: { id: number } } }[]>(
    token,
    "getUpdates"
  );
  if (!updates?.length) return null;
  for (let i = updates.length - 1; i >= 0; i--) {
    const id = updates[i]?.message?.chat?.id;
    if (id) return String(id);
  }
  return null;
}

function memeAlertLines(scan: Awaited<ReturnType<typeof cachedScan>>): string[] {
  const lines: string[] = [];
  const push = (s: MemeSignal, label: string) => {
    if (!shouldAlert(`${s.address}-${s.playType}`)) return;
    lines.push(
      `🚨 <b>${label}</b> $${s.symbol} — score ${s.score}\n` +
        `MCap $${(s.fdv / 1000).toFixed(0)}K · Liq $${(s.liquidity / 1000).toFixed(0)}K · ` +
        `1h ${s.h1 >= 0 ? "+" : ""}${s.h1.toFixed(0)}% · B/S ${s.buySellRatio.toFixed(1)}x\n` +
        `Plan: ${s.sizingKey} sizing · <a href="https://jup.ag/swap/SOL-${s.address}">Jupiter</a> · ` +
        `<a href="${s.pairUrl}">DexScreener</a>`
    );
  };

  for (const s of scan.sure2x) push(s, "2x GRINDER");
  for (const s of scan.momentum.filter((x) => x.score >= 75)) push(s, "MOMENTUM RIDER");
  for (const s of scan.launches.filter((x) => x.score >= 75)) push(s, "HOT LAUNCH");
  for (const s of scan.degens.filter(
    (x) => (x.tier === "100x MOONSHOT" && x.score >= 80) || (x.tier === "10x RUNNER" && x.score >= 75)
  ))
    push(s, s.tier ?? "DEGEN");

  return lines.slice(0, 5); // never spam more than 5 per run
}

export async function GET(req: NextRequest) {
  const url = new URL(req.url);
  const token = process.env.TELEGRAM_BOT_TOKEN;
  const secret = process.env.ALERTS_SECRET;

  if (secret && url.searchParams.get("key") !== secret) {
    return NextResponse.json({ error: "bad key" }, { status: 401 });
  }
  if (!token) {
    return NextResponse.json(
      { error: "TELEGRAM_BOT_TOKEN not configured in env" },
      { status: 503 }
    );
  }

  const chatId = await resolveChatId(token);

  // Setup mode: /api/alerts?setup=1 — verifies wiring, sends a test message
  if (url.searchParams.get("setup")) {
    if (!chatId) {
      return NextResponse.json({
        ok: false,
        hint: "No chat found. Open Telegram, send your bot any message, then reload this URL.",
      });
    }
    await tgCall(token, "sendMessage", {
      chat_id: chatId,
      text: "✅ Memecoin Intel alerts connected. You'll get pinged when high-conviction signals fire.",
    });
    return NextResponse.json({ ok: true, chatId, note: "Test message sent. Set TELEGRAM_CHAT_ID env var to this value to skip auto-detection." });
  }

  if (!chatId) {
    return NextResponse.json({ ok: false, error: "no chat id — message the bot once, or set TELEGRAM_CHAT_ID" });
  }

  let sent = 0;
  const errors: string[] = [];

  // ── Memecoin alerts ──────────────────────────────────────────────────
  try {
    const scan = await cachedScan();
    for (const line of memeAlertLines(scan)) {
      const ok = await tgCall(token, "sendMessage", {
        chat_id: chatId,
        text: line,
        parse_mode: "HTML",
        disable_web_page_preview: true,
      });
      if (ok) sent++;
    }
  } catch {
    errors.push("meme scan failed");
  }

  // ── Perp squeeze alerts (EU region can reach Binance) ────────────────
  try {
    const { buildAllTickets } = await import("@/modules/crypto/perps");
    const tickets = await buildAllTickets();
    for (const t of tickets) {
      const key = `perp-${t.symbol}-${t.direction}`;
      if (t.squeezeWatch && t.confidence !== "LOW" && shouldAlert(`squeeze-${t.symbol}`)) {
        const ok = await tgCall(token, "sendMessage", {
          chat_id: chatId,
          text: `⚡ <b>${t.display}</b> ${t.squeezeWatch}\nBias ${t.bias >= 0 ? "+" : ""}${t.bias} (${t.direction}) · funding ${t.fundingPct8h}%/8h · OI 24h ${t.oiChange24hPct >= 0 ? "+" : ""}${t.oiChange24hPct}%`,
          parse_mode: "HTML",
        });
        if (ok) sent++;
      } else if (t.confidence === "HIGH" && t.direction !== "STAND ASIDE" && shouldAlert(key)) {
        const ok = await tgCall(token, "sendMessage", {
          chat_id: chatId,
          text:
            `📐 <b>${t.display} ${t.direction}</b> — bias ${t.bias >= 0 ? "+" : ""}${t.bias} (HIGH)\n` +
            `${t.regime}\nEntry ~${t.markPrice} · stop -${t.stopPct}% · TP 1.5R/3R · max ${t.maxLev}x`,
          parse_mode: "HTML",
        });
        if (ok) sent++;
      }
    }
  } catch {
    errors.push("perp check unavailable from server region");
  }

  return NextResponse.json({ ok: true, sent, errors });
}
