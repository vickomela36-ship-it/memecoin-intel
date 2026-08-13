#!/usr/bin/env bash
#
# capture-perf.sh — capture the live runtime metrics that PERF_BASELINE.md
# lists as "to capture on live URL". Run this from a machine with normal
# outbound network (the sandboxed build env cannot reach vercel.app).
#
# Usage:
#   ./scripts/capture-perf.sh [URL]
#
# Default URL is the production deployment. Requires Node (for npx lighthouse)
# and curl. Writes a Markdown block to stdout AND perf-capture.md — paste the
# table into ../PERF_RESULTS.md under "Live runtime metrics".
#
set -euo pipefail

URL="${1:-https://memecoin-intel-baoa.vercel.app/}"
OUT="perf-capture.md"

echo "→ Capturing perf for: $URL"
echo

# ── 1. Edge/network timing via curl (5 runs, report the median-ish last) ────
echo "## curl timing (cold vs warm edge)"
for i in 1 2 3; do
  curl -sS -o /dev/null \
    -w "run $i: http=%{http_code} total=%{time_total}s ttfb=%{time_starttransfer}s dl=%{size_download}B\n" \
    "$URL" || echo "run $i: request failed"
done
echo

# Grab cache + region headers (Vercel exposes x-vercel-cache, x-vercel-id)
echo "## response headers (cache / region)"
curl -sS -D - -o /dev/null "$URL" \
  | grep -iE 'x-vercel-cache|x-vercel-id|cache-control|content-encoding|age' \
  || echo "(no vercel cache headers seen)"
echo

# ── 2. Lighthouse mobile + desktop ──────────────────────────────────────────
# Records Performance score, LCP, TBT, CLS, FCP, TTI. Needs Chrome/Chromium.
run_lh () {
  local preset="$1" label="$2"
  echo "→ Lighthouse ($label)…" >&2
  npx --yes lighthouse "$URL" \
    ${preset:+--preset="$preset"} \
    --only-categories=performance \
    --chrome-flags="--headless=new --no-sandbox" \
    --output=json --output-path=stdout --quiet 2>/dev/null \
  | node -e '
      let s="";process.stdin.on("data",d=>s+=d).on("end",()=>{
        const j=JSON.parse(s), a=j.audits, cat=j.categories.performance;
        const m=k=>a[k]?.displayValue ?? "n/a";
        console.log(JSON.stringify({
          perf: Math.round((cat.score??0)*100),
          FCP: m("first-contentful-paint"),
          LCP: m("largest-contentful-paint"),
          TBT: m("total-blocking-time"),
          CLS: m("cumulative-layout-shift"),
          TTI: m("interactive"),
          transferKB: Math.round((a["total-byte-weight"]?.numericValue??0)/1024),
        }));
      });'
}

MOBILE_JSON="$(run_lh "" mobile || echo '{}')"
DESKTOP_JSON="$(run_lh desktop desktop || echo '{}')"

# ── 3. Emit a paste-ready Markdown block ────────────────────────────────────
{
  echo "## Live runtime metrics — $(date -u '+%Y-%m-%d %H:%M UTC')"
  echo
  echo "URL: \`$URL\`"
  echo
  echo "| Profile | Perf | FCP | LCP | TBT | CLS | TTI | Transfer |"
  echo "|---|---|---|---|---|---|---|---|"
  for pair in "Mobile:$MOBILE_JSON" "Desktop:$DESKTOP_JSON"; do
    label="${pair%%:*}"; js="${pair#*:}"
    node -e '
      const j=JSON.parse(process.argv[2]||"{}");
      const g=k=>j[k]??"—";
      console.log(`| ${process.argv[1]} | ${g("perf")} | ${g("FCP")} | ${g("LCP")} | ${g("TBT")} | ${g("CLS")} | ${g("TTI")} | ${g("transferKB")+" kB"} |`);
    ' "$label" "$js"
  done
  echo
  echo "_Captured with \`scripts/capture-perf.sh\`. Compare against the bundle"
  echo "deltas already in this file; these are the field timings the baseline"
  echo "left open._"
} | tee "$OUT"

echo
echo "→ Wrote $OUT — paste its table into ../PERF_RESULTS.md"
