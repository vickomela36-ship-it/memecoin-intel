#!/usr/bin/env python3
"""
monitor.py – run by Claude Code's hourly loop.
Reads signals.py output and prints structured JSON for Claude to act on.
Claude then sends the Gmail alert and logs the entry to Notion.

Usage (by Claude's loop prompt):
    python3 monitor.py
"""

import json
import subprocess
import sys
from pathlib import Path

SIGNALS_SCRIPT = Path(__file__).parent / "signals.py"


def main():
    result = subprocess.run(
        [sys.executable, str(SIGNALS_SCRIPT)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        data = {
            "signal": "error",
            "error": result.stderr or "No output from signals.py",
        }

    print(json.dumps(data, indent=2))
    return data


if __name__ == "__main__":
    main()
