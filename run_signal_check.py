"""
Hourly runner — checks signals and prints JSON to stdout.
Claude's /loop reads this output then fires Gmail + Notion alerts.
"""

import json
from signals import get_signals

signals = get_signals()
buy_now = [s for s in signals if s.get("signal") == "buy now"]
errors = [s for s in signals if s.get("fetch_failed")]

out = {"buy_now": buy_now, "total_checked": len(signals)}
if errors:
    out["error"] = errors[0].get("error", "unknown fetch error")

print(json.dumps(out))
