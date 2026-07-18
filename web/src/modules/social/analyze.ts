// Social signal quality — pure analysis over normalized X posts.
// The DATA comes from a pluggable worker (Agent-Reach or similar); this
// module never fabricates posts. It only classifies and ranks what it's given.

export interface RawPost {
  author: string;
  followers: number;
  text: string;
  createdAt: number; // ms
  url?: string;
  verified?: boolean;
}

export interface ScoredPost extends RawPost {
  isBot: boolean;
  botReasons: string[];
  hasThesis: boolean;
  earlyScore: number; // higher = earlier + smaller account + real reasoning
}

const BOT_PATTERNS = [
  { re: /\bup\s*\d+%?\s*(since|from)\b/i, why: "pure 'up X% since we called it' framing" },
  { re: /(t\.me\/|telegram\.me\/|join.*(private|vip).*(group|channel))/i, why: "links a private Telegram" },
  { re: /\b(1000x|100x|next\s+\w+\s+gem)\b/i, why: "templated moonshot hype" },
  { re: /(ape\s+now|don'?t\s+miss|last\s+chance|send\s+it)/i, why: "urgency/FOMO template" },
];

const THESIS_MARKERS = /\b(because|since|the reason|dev|team|narrative|holders|liquidity|volume|chart|thesis|utility|revenue|buyback)\b/i;

/** Classify a post as bot vs human using the guide's signatures. */
export function classifyPost(p: RawPost): ScoredPost {
  const reasons: string[] = [];
  for (const b of BOT_PATTERNS) if (b.re.test(p.text)) reasons.push(b.why);

  const hasThesis = THESIS_MARKERS.test(p.text) && p.text.length > 40;
  if (!hasThesis && p.text.length < 40) reasons.push("no stated reason for the call");

  // Templated structure: mostly cashtags/emojis, little prose
  const words = p.text.replace(/[$#@][\w]+/g, "").trim().split(/\s+/).filter(Boolean);
  if (words.length < 5 && !hasThesis) reasons.push("templated, minimal prose");

  const isBot = reasons.length >= 2;
  return { ...p, isBot, botReasons: reasons, hasThesis, earlyScore: 0 };
}

/**
 * Rank human posts by early + low-follower + real thesis — NOT engagement.
 * A 400-follower account that found it early and explained why beats a
 * 200k account shilling.
 */
export function rankPosts(posts: RawPost[], launchAt: number | null): {
  human: ScoredPost[];
  bots: ScoredPost[];
  earliestHuman: number | null;
} {
  const scored = posts.map(classifyPost);
  const human = scored.filter((p) => !p.isBot);
  const bots = scored.filter((p) => p.isBot);

  const earliestHuman = human.length ? Math.min(...human.map((p) => p.createdAt)) : null;
  const now = Date.now();

  for (const p of human) {
    // Earliness: closer to launch (or to earliestHuman) = higher
    const anchor = launchAt ?? earliestHuman ?? p.createdAt;
    const hoursAfter = Math.max(0, (p.createdAt - anchor) / 3_600_000);
    const earliness = Math.max(0, 40 - hoursAfter * 2); // decays over ~20h
    // Small account bonus (finding it before the big accounts)
    const smallness = p.followers > 0 ? Math.max(0, 30 - Math.log10(p.followers) * 6) : 15;
    const thesis = p.hasThesis ? 30 : 0;
    const recency = Math.max(0, 10 - (now - p.createdAt) / 3_600_000 / 24); // slight freshness
    p.earlyScore = Math.round(earliness + smallness + thesis + recency);
  }
  human.sort((a, b) => b.earlyScore - a.earlyScore);
  return { human, bots, earliestHuman };
}

export function timingContext(
  earliestHuman: number | null,
  launchAt: number | null
): { label: "EARLY" | "ON TIME" | "LATE" | "UNKNOWN"; detail: string } {
  if (earliestHuman === null) return { label: "UNKNOWN", detail: "No credible human posts found yet." };
  const now = Date.now();
  const sinceFirst = (now - earliestHuman) / 3_600_000;
  if (launchAt) {
    const firstAfterLaunch = (earliestHuman - launchAt) / 3_600_000;
    if (firstAfterLaunch < 2 && sinceFirst < 3)
      return { label: "EARLY", detail: `First credible post ${firstAfterLaunch.toFixed(1)}h after launch, ${sinceFirst.toFixed(1)}h ago.` };
  }
  if (sinceFirst < 6) return { label: "ON TIME", detail: `Credible chatter started ${sinceFirst.toFixed(1)}h ago.` };
  return { label: "LATE", detail: `Credible chatter is ${sinceFirst.toFixed(0)}h old — the early move may be gone.` };
}
