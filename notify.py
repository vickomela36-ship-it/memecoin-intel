"""
Hourly notifier: runs signal checks, emails buy-now alerts, and logs to Notion.
Designed to be invoked by the Claude Code /loop skill prompt.
Outputs structured JSON so the calling Claude session can act on results.
"""

import json
import subprocess
import sys
from datetime import datetime, timezone


def run_signals(mock: bool = False) -> list[dict]:
    args = [sys.executable, "signals.py"]
    if mock:
        args.append("--mock")
    result = subprocess.run(
        args,
        capture_output=True,
        text=True,
        cwd=__file__.rsplit("/", 1)[0],
    )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return []


def format_email_html(signals: list[dict]) -> str:
    rows = ""
    for s in signals:
        rows += f"""
        <tr>
          <td style="padding:8px;border:1px solid #ddd;font-weight:bold">{s['token']}</td>
          <td style="padding:8px;border:1px solid #ddd;color:#16a34a;font-weight:bold">
            {s['signal'].upper()}
          </td>
          <td style="padding:8px;border:1px solid #ddd">${s['price']:.6f}</td>
          <td style="padding:8px;border:1px solid #ddd">{s['score']}/100</td>
          <td style="padding:8px;border:1px solid #ddd">{s['reason']}</td>
        </tr>"""

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return f"""
    <html><body style="font-family:sans-serif;max-width:700px;margin:auto">
      <h2 style="color:#16a34a">Memecoin BUY NOW Alert - {ts}</h2>
      <p>{len(signals)} token(s) triggered a <strong>BUY NOW</strong> signal.</p>
      <table style="border-collapse:collapse;width:100%">
        <thead>
          <tr style="background:#f3f4f6">
            <th style="padding:8px;border:1px solid #ddd;text-align:left">Token</th>
            <th style="padding:8px;border:1px solid #ddd;text-align:left">Signal</th>
            <th style="padding:8px;border:1px solid #ddd;text-align:left">Price</th>
            <th style="padding:8px;border:1px solid #ddd;text-align:left">Score</th>
            <th style="padding:8px;border:1px solid #ddd;text-align:left">Reason</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
      <p style="color:#6b7280;font-size:12px;margin-top:24px">
        This is an automated alert from memecoin-intel. Not financial advice.
      </p>
    </body></html>"""


def format_email_plain(signals: list[dict]) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [f"Memecoin BUY NOW Alert — {ts}", "=" * 50]
    for s in signals:
        lines += [
            f"Token:  {s['token']}",
            f"Signal: {s['signal'].upper()}",
            f"Price:  ${s['price']:.6f}",
            f"Score:  {s['score']}/100",
            f"Reason: {s['reason']}",
            "-" * 40,
        ]
    lines.append("Not financial advice.")
    return "\n".join(lines)


if __name__ == "__main__":
    mock = "--mock" in sys.argv
    all_signals = run_signals(mock=mock)
    buy_signals = [s for s in all_signals if s["signal"] == "buy now"]

    output = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_checked": len(all_signals),
        "buy_now_count": len(buy_signals),
        "buy_signals": buy_signals,
        "all_signals": all_signals,
        "email_subject": f"Memecoin BUY NOW Alert: {', '.join(s['token'] for s in buy_signals)}" if buy_signals else "",
        "email_html": format_email_html(buy_signals) if buy_signals else "",
        "email_plain": format_email_plain(buy_signals) if buy_signals else "",
    }

    print(json.dumps(output, indent=2))
