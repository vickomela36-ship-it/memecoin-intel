"""
Hourly runner — checks signals and prints JSON to stdout.
Claude's /loop reads this output then fires Gmail + Notion alerts.
"""

import json
from signals import get_signals

signals = get_signals()
buy_now = [s for s in signals if s.get("signal") == "buy now"]

print(json.dumps({"buy_now": buy_now, "total_checked": len(signals)}))
