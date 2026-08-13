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

/**
 * Coordinated-KOL detection: multiple distinct accounts posting the same token
 * inside a short window is the pattern where a group bundles a coin at launch,
 * splits supply, then takes turns posting to fake independent organic hype.
 * Operates on the posts already returned for one token — pure, no extra data.
 */
export function detectCoordinatedKOLs(
  posts: RawPost[],
  windowMin = 90
): { coordinated: boolean; authors: string[]; withinMin: number | null; note: string } {
  // Earliest post per distinct author, then look for a tight cluster of them.
  const firstByAuthor = new Map<string, number>();
  for (const p of posts) {
    const prev = firstByAuthor.get(p.author);
    if (prev === undefined || p.createdAt < prev) firstByAuthor.set(p.author, p.createdAt);
  }
  const times = Array.from(firstByAuthor.entries()).sort((a, b) => a[1] - b[1]);
  if (times.length < 3) {
    return { coordinated: false, authors: [], withinMin: null, note: "Too few distinct accounts to judge coordination." };
  }
  // Slide a window; find the largest set of distinct authors within windowMin.
  const winMs = windowMin * 60_000;
  let best: [string, number][] = [];
  for (let i = 0; i < times.length; i++) {
    const group = times.filter(([, t]) => t >= times[i][1] && t <= times[i][1] + winMs);
    if (group.length > best.length) best = group;
  }
  const coordinated = best.length >= 3;
  const span = best.length >= 2 ? (best[best.length - 1][1] - best[0][1]) / 60_000 : 0;
  return {
    coordinated,
    authors: best.map(([a]) => a),
    withinMin: coordinated ? Math.round(span) : null,
    note: coordinated
      ? `${best.length} separate accounts first posted this within ${Math.round(span)} minutes — possible coordinated push dressed as organic hype. Weight the "buzz" accordingly.`
      : "No tight cluster of accounts posting together — chatter looks staggered.",
  };
}

const SOL_ADDR = /\b[1-9A-HJ-NP-Za-km-z]{32,44}\b/;

/**
 * Best-effort handle↔wallet resolver: pull a Solana address out of a post/bio
 * (people paste their wallet, a .sol tip address, a disclosure). Returns null
 * if none — never guesses. The caller can then cross-check on-chain whether the
 * poster is selling what they're shilling.
 */
export function extractWallet(text: string): string | null {
  const m = text.match(SOL_ADDR);
  // Exclude obvious non-wallet 32-44 char strings by requiring base58-ish and
  // not looking like a URL slug.
  if (!m) return null;
  const cand = m[0];
  if (/^[0-9]+$/.test(cand)) return null;
  return cand;
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
