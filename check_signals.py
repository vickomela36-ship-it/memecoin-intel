"""
Hourly signal checker.
Run this directly to get JSON output consumed by the Claude Code loop handler.
Exit code 0 always; prints JSON with buy_now list + all results.
"""

import json
import sys
from dataclasses import asdict
from signals import get_signals

def main():
    try:
        results = get_signals()
    except Exception as e:
        print(json.dumps({"error": str(e), "buy_now": [], "all": []}))
        sys.exit(0)

    buy_now = [asdict(r) for r in results if r.signal == "buy now"]
    all_res = [asdict(r) for r in results]

    print(json.dumps({"buy_now": buy_now, "all": all_res}, indent=2))

if __name__ == "__main__":
    main()
