import { NextRequest, NextResponse } from "next/server";
import { mineNarrativeWords } from "@/modules/memecoin/detectors";

export const dynamic = "force-dynamic";

// Narrative word-frequency miner: the user pastes discourse (an article, an
// announcement, a thread), we surface the most-repeated distinctive words, and
// for the top word we check whether a Solana token already exists for it. This
// catches the "$TRILLIONS ran on one repeated word" pattern. The corpus comes
// from the user — nothing is scraped or fabricated here.

interface DexSearchResp {
  pairs?: {
    chainId?: string;
    baseToken?: { address?: string; symbol?: string; name?: string };
    volume?: { h24?: number };
    fdv?: number;
    marketCap?: number;
    pairCreatedAt?: number;
  }[];
}

async function tokenForWord(word: string) {
  try {
    const res = await fetch(
      `https://api.dexscreener.com/latest/dex/search?q=${encodeURIComponent(word)}`,
      { cache: "no-store" }
    );
    if (!res.ok) return null;
    const data = (await res.json()) as DexSearchResp;
    const sol = (data.pairs ?? []).filter((p) => p.chainId === "solana");
    if (!sol.length) return null;
    // Prefer an exact symbol/name match; else the highest-volume pair.
    const exact = sol.find(
      (p) =>
        (p.baseToken?.symbol ?? "").toLowerCase() === word ||
        (p.baseToken?.name ?? "").toLowerCase() === word
    );
    const best = exact ?? sol.reduce((a, b) => ((a.volume?.h24 ?? 0) >= (b.volume?.h24 ?? 0) ? a : b));
    return {
      exists: true,
      exactMatch: !!exact,
      symbol: best.baseToken?.symbol ?? "?",
      address: best.baseToken?.address ?? "",
      mcap: Number(best.marketCap ?? best.fdv ?? 0),
      vol24: Number(best.volume?.h24 ?? 0),
    };
  } catch {
    return null;
  }
}

export async function POST(req: NextRequest) {
  let text = "";
  try {
    const body = await req.json();
    text = typeof body?.text === "string" ? body.text : "";
  } catch {
    /* empty */
  }
  if (text.trim().length < 20) {
    return NextResponse.json({ error: "Paste at least a sentence or two of discourse to mine." }, { status: 400 });
  }

  const words = mineNarrativeWords(text, 6);
  if (!words.length) {
    return NextResponse.json({ words: [], top: null, match: null });
  }

  // Reverse-lookup the single most-repeated word.
  const match = await tokenForWord(words[0].word);
  return NextResponse.json({ words, top: words[0].word, match });
}
