"""
Hourly memecoin signal runner.

Executes the signal check and prints a structured JSON result that the
Claude Code loop agent reads to decide whether to send an email and log
to Notion.

Usage:
    python3 run_check.py
"""
import json
from signals import get_signal

if __name__ == "__main__":
    result = get_signal()
    print(json.dumps(result, indent=2))
