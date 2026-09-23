import { NextRequest, NextResponse } from "next/server";
import { cachedScan } from "@/lib/scan-cache";
import type { MemeSignal, MemeScanResult } from "@/types";

export const dynamic = "force-dynamic";
export const maxDuration = 60;

// Email digest via Resend — runs the shared scan and emails the ATH-reclaim
// picks (with profit targets) + the top pick per upside tier. Meant to be hit
// on a schedule (Vercel cron on Pro, or an external/Claude routine hourly
// during peak hours on Hobby). Guarded by DIGEST_SECRET so it isn't publicly
// triggerable. Env: RESEND_API_KEY, RESEND_FROM, DIGEST_TO, DIGEST_SECRET.

const money = (n: number) =>
  n >= 1_000_000 ? `$${(n / 1_000_000).toFixed(1)}M` : n >= 1_000 ? `$${(n / 1000).toFixed(0)}K` : `$${n.toFixed(0)}`;

function price(n: number): string {
  if (n <= 0) return "$0";
  if (n < 0.00001) return `$${n.toExponential(2)}`;
  if (n < 1) return `$${n.toPrecision(3)}`;
  return `$${n.toFixed(2)}`;
}

const dexUrl = (s: MemeSignal) => s.pairUrl || `https://dexscreener.com/solana/${s.address}`;

function best(arr: MemeSignal[]): MemeSignal | null {
  return arr.length ? arr.slice().sort((a, b) => b.score - a.score)[0] : null;
}

function row(label: string, s: MemeSignal | null, roi: string): string {
  if (!s) return `<tr><td style="padding:6px 10px;color:#8a93a6">${label}</td><td colspan="3" style="padding:6px 10px;color:#4a5163">no pick</td></tr>`;
  return `<tr>
    <td style="padding:6px 10px;font-weight:700;color:#14f195">${label}</td>
    <td style="padding:6px 10px"><a href="${dexUrl(s)}" style="color:#e6edf3;text-decoration:none">$${s.symbol}</a></td>
    <td style="padding:6px 10px;color:#8a93a6">${money(s.fdv)} · score ${s.score}</td>
    <td style="padding:6px 10px;color:#14f195;font-weight:700">${roi}</td>
  </tr>`;
}

function buildHtml(scan: MemeScanResult): { html: string; subject: string } {
  const all = [
    ...scan.hot, ...scan.trending, ...scan.sure2x, ...scan.recovery3x, ...scan.momentum,
    ...scan.volumePlays, ...scan.higherCap, ...scan.athReclaim, ...scan.pumpfun, ...scan.launches, ...scan.degens,
  ];
  const byTier = (t: string) => best(all.filter((s) => s.tier === t));

  const ath = scan.athReclaim ?? [];
  const athRows = ath.length
    ? ath.map((s) => {
        const worst = Math.min(s.h6, s.h24);
        const target = s.profitTarget;
        return `<tr>
          <td style="padding:8px 10px"><a href="${dexUrl(s)}" style="color:#e6edf3;text-decoration:none;font-weight:700">$${s.symbol}</a></td>
          <td style="padding:8px 10px;color:#8a93a6">${money(s.fdv)} · ${money(s.liquidity)} liq</td>
          <td style="padding:8px 10px;color:#ff4d6d">${worst.toFixed(0)}% dip</td>
          <td style="padding:8px 10px;color:#14f195;font-weight:700">${target ? `${price(target.price)} (+${target.pct}%)` : "—"}</td>
        </tr>`;
      }).join("")
    : `<tr><td colspan="4" style="padding:8px 10px;color:#4a5163">No ATH-reclaim picks this scan — no established, deep-liquidity token is in a retracement right now.</td></tr>`;

  const highlightRows = [
    row("2x", best(scan.sure2x) ?? byTier("3x POSSIBLE"), "target +100%"),
    row("3x", best(scan.recovery3x) ?? byTier("5x POTENTIAL"), "target +200%"),
    row("5x", byTier("5x POTENTIAL"), "target +400%"),
    row("10x", byTier("10x RUNNER"), "target +900%"),
    row("100x", byTier("100x MOONSHOT"), "target +9900%"),
  ].join("");

  const pulse = scan.pulse;
  const subject = `Memecoin Intel — ${ath.length} ATH pick${ath.length === 1 ? "" : "s"}, market ${pulse?.greenPct ?? "?"}% green`;

  const html = `<!doctype html><html><body style="margin:0;background:#0a0e14;color:#e6edf3;font-family:-apple-system,Segoe UI,Roboto,sans-serif">
  <div style="max-width:640px;margin:0 auto;padding:20px">
    <h1 style="font-size:18px;letter-spacing:2px;margin:0 0 4px">MEMECOIN INTEL</h1>
    <p style="color:#8a93a6;font-size:13px;margin:0 0 16px">
      Market: ${pulse?.greenPct ?? "?"}% green · median 24h ${pulse ? (pulse.medianH24 >= 0 ? "+" : "") + pulse.medianH24 : "?"}% · ${pulse ? money(pulse.totalVol24hUsd) : "?"} vol
    </p>

    <h2 style="font-size:14px;color:#9945ff;margin:16px 0 6px">ATH RECLAIM — BLUE-CHIP DIPS</h2>
    <table style="width:100%;border-collapse:collapse;font-size:13px;background:#111721;border-radius:6px;overflow:hidden">
      <tr style="color:#8a93a6;text-align:left"><th style="padding:8px 10px">Token</th><th style="padding:8px 10px">Cap / Liq</th><th style="padding:8px 10px">Pullback</th><th style="padding:8px 10px">Profit target</th></tr>
      ${athRows}
    </table>

    <h2 style="font-size:14px;color:#9945ff;margin:20px 0 6px">HIGHLIGHTS — TOP PICK PER TIER</h2>
    <table style="width:100%;border-collapse:collapse;font-size:13px;background:#111721;border-radius:6px;overflow:hidden">
      ${highlightRows}
    </table>

    <p style="color:#4a5163;font-size:11px;margin:18px 0 0;line-height:1.5">
      Targets are the tier's target (or reclaim of the recent high for ATH) — NOT a prediction a token reaches them.
      This surfaces information; it is not financial advice. Memecoin trading carries substantial risk of total loss.
    </p>
  </div></body></html>`;

  return { html, subject };
}

export async function GET(req: NextRequest) {
  const secret = process.env.DIGEST_SECRET;
  const key = new URL(req.url).searchParams.get("key");
  if (secret && key !== secret) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  const apiKey = process.env.RESEND_API_KEY;
  const from = process.env.RESEND_FROM;
  const to = process.env.DIGEST_TO;
  if (!apiKey || !from || !to) {
    return NextResponse.json(
      { error: "email not configured — set RESEND_API_KEY, RESEND_FROM, DIGEST_TO", configured: false },
      { status: 503 }
    );
  }

  try {
    const scan = await cachedScan();
    const { html, subject } = buildHtml(scan);
    const res = await fetch("https://api.resend.com/emails", {
      method: "POST",
      headers: { Authorization: `Bearer ${apiKey}`, "Content-Type": "application/json" },
      body: JSON.stringify({ from, to: to.split(",").map((s) => s.trim()), subject, html }),
      cache: "no-store",
    });
    const data = await res.json();
    if (!res.ok) {
      return NextResponse.json({ error: "resend failed", detail: data }, { status: 502 });
    }
    return NextResponse.json({ ok: true, id: data?.id ?? null, athPicks: scan.athReclaim.length });
  } catch {
    return NextResponse.json({ error: "digest failed" }, { status: 502 });
  }
}
