"""
Hourly memecoin signal scheduler.

Runs check_signals.py every hour; if any "buy now" signals are found it pipes
the result to notify.py which sends an email and logs a Notion row.

Required env vars (passed through to notify.py):
  GMAIL_SENDER       - Gmail address used to send alerts
  GMAIL_APP_PASSWORD - Gmail App Password
  NOTION_API_KEY     - Notion integration token (secret_...)

Run:
  python scheduler.py

Or as a background daemon:
  nohup python scheduler.py >> logs/scheduler.log 2>&1 &
"""

import json
import logging
import subprocess
import sys
import time
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
    stream=sys.stdout,
)
log = logging.getLogger(__name__)

INTERVAL_SECONDS = 3600  # 1 hour
BASE_DIR = Path(__file__).parent


def _run_once() -> None:
    log.info("Checking signals...")

    try:
        check = subprocess.run(
            [sys.executable, str(BASE_DIR / "check_signals.py")],
            capture_output=True,
            text=True,
            timeout=90,
            cwd=BASE_DIR,
        )
        payload = json.loads(check.stdout)
    except subprocess.TimeoutExpired:
        log.error("check_signals.py timed out — skipping this run")
        return
    except json.JSONDecodeError as exc:
        log.error("check_signals.py returned invalid JSON: %s", exc)
        return
    except Exception as exc:
        log.error("check_signals.py failed: %s", exc)
        return

    if "error" in payload:
        log.warning("Signal error: %s", payload["error"])
        return

    buy_now = payload.get("buy_now", [])
    total   = len(payload.get("all", []))
    log.info("Scanned %d token(s) — %d buy-now signal(s)", total, len(buy_now))

    if not buy_now:
        return

    for t in buy_now:
        log.info("  BUY NOW  %s (%s)  @ $%s  pressure=%s",
                 t.get("token"), t.get("symbol"),
                 t.get("price_usd"), t.get("buy_pressure"))

    try:
        notify = subprocess.run(
            [sys.executable, str(BASE_DIR / "notify.py")],
            input=check.stdout,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=BASE_DIR,
        )
        for line in notify.stdout.splitlines():
            log.info("  notify: %s", line)
        if notify.returncode != 0:
            log.error("notify.py error: %s", notify.stderr.strip())
    except subprocess.TimeoutExpired:
        log.error("notify.py timed out")
    except Exception as exc:
        log.error("notify.py failed: %s", exc)


def main() -> None:
    log.info("Memecoin Intel scheduler started  (interval=%ds)", INTERVAL_SECONDS)
    while True:
        try:
            _run_once()
        except Exception as exc:
            log.exception("Unexpected error in run loop: %s", exc)
        log.info("Next check in %d minutes.", INTERVAL_SECONDS // 60)
        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
