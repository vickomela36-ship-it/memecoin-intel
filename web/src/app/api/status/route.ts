import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

// Feature status — reports which env-backed capabilities are configured, as
// booleans only. NEVER returns the secret values themselves. Drives the
// in-app status panel so you can see what's live vs dormant.

export async function GET() {
  const kv = !!(
    (process.env.KV_REST_API_URL ?? process.env.UPSTASH_REDIS_REST_URL) &&
    (process.env.KV_REST_API_TOKEN ?? process.env.UPSTASH_REDIS_REST_TOKEN)
  );
  const lunar = !!process.env.LUNARCRUSH_API_KEY;
  const xreach = !!process.env.XREACH_URL;
  const helius = !!process.env.HELIUS_API_KEY;
  const birdeye = !!process.env.BIRDEYE_API_KEY;
  const telegram = !!(process.env.TELEGRAM_BOT_TOKEN && process.env.TELEGRAM_CHAT_ID);

  return NextResponse.json({
    features: [
      { key: "kv", label: "Persistence (Vercel KV)", live: kv,
        powers: "Call ledger, KOL track-record, creator balance/cluster tracking, trenches heat gauge, cross-device sync" },
      { key: "social", label: "Social signal", live: lunar || xreach,
        powers: "Bot filtering, early-poster ranking, KOL ledger, coordinated-KOL",
        detail: lunar ? "LunarCrush" : xreach ? "Agent-Reach worker" : "none" },
      { key: "helius", label: "On-chain (Helius)", live: helius,
        powers: "Holder tracing, fresh wallets, funding clusters, creator balance, followed-wallet buys" },
      { key: "birdeye", label: "Market data (Birdeye)", live: birdeye,
        powers: "OHLCV for botted-chart + market-structure TA, whale flow" },
      { key: "telegram", label: "Alerts (Telegram)", live: telegram,
        powers: "Outbound scan/HOT alerts" },
    ],
  });
}
