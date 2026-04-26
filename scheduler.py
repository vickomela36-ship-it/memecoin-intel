#!/usr/bin/env python3
"""
Persistent hourly scheduler for the memecoin pipeline.
Runs run_pipeline.main() immediately, then at the top of every hour.
Start with: nohup python3 scheduler.py &
"""
import time
import traceback
from datetime import datetime, timezone

import run_pipeline


def seconds_until_next_hour() -> float:
    now = datetime.now(timezone.utc)
    elapsed = now.minute * 60 + now.second + now.microsecond / 1e6
    return max(0.0, 3600.0 - elapsed)


def main() -> None:
    print(f"[scheduler] started — first run now, then every hour on the hour")
    while True:
        try:
            run_pipeline.main()
        except Exception:
            traceback.print_exc()

        wait = seconds_until_next_hour()
        next_run = datetime.now(timezone.utc)
        print(f"[scheduler] next run in {wait/60:.1f} min  (at {next_run.strftime('%H:%M')} UTC + {wait:.0f}s)")
        time.sleep(wait)


if __name__ == "__main__":
    main()
