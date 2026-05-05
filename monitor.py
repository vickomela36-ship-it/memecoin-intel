#!/usr/bin/env python3
"""
Hourly monitor — run once per invocation.

Prints JSON to stdout:
  {
    "checked": <int>,
    "buy_now": [ { Signal fields ... }, ... ]
  }

Exit code 0 always; errors are reported inside the JSON.
"""

import json
import sys
from dataclasses import asdict

from signals import get_signals


def main() -> dict:
    try:
        all_signals = get_signals()
    except Exception as exc:
        result = {"error": str(exc), "checked": 0, "buy_now": []}
        print(json.dumps(result))
        return result

    buy_now = [asdict(s) for s in all_signals if s.signal == "buy now"]
    result = {
        "checked": len(all_signals),
        "buy_now": buy_now,
    }
    print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    main()
