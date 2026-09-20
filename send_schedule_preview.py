"""
Sends YOU (ADMIN_CHAT_ID only - never the customer) a preview of what's
queued to go out, so you can approve it or swap anything you don't like
before your brother ever sees it.

Runs weekly on Saturdays, and on demand from the Actions tab
("Send schedule preview").

Env:
  PREVIEW_DAYS    how many days of quotes to show (default 14)
  PREVIEW_WEEKS   how many upcoming habits to show (default 4)
"""

import os
import sys
from datetime import date, timedelta

from telegram_utils import send_text
from render import short_label
import schedule_utils as su

ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID")
PREVIEW_DAYS = int(os.environ.get("PREVIEW_DAYS") or 14)
PREVIEW_WEEKS = int(os.environ.get("PREVIEW_WEEKS") or 4)

TELEGRAM_LIMIT = 4000  # real cap is 4096; leave headroom


def fmt_day(d: date) -> str:
    return d.strftime("%d %b (%a)")


def build_preview(today=None):
    today = today or date.today()
    sched = su.load_schedule()
    quotes = su.load_library("quotes")
    habits = su.load_library("habits")

    lines = ["\U0001F4C5 Upcoming sends — review before they go out", ""]

    lines.append(f"QUOTES — next {PREVIEW_DAYS} days")
    shown = 0
    for offset in range(PREVIEW_DAYS):
        day = today + timedelta(days=offset)
        idx = sched["quotes"].get(day.isoformat())
        if idx is None or not (0 <= idx < len(quotes)):
            continue
        marker = "→" if offset == 0 else "·"
        lines.append(f"{fmt_day(day)} {marker} {short_label(quotes[idx], 'quotes')}")
        shown += 1
    if shown == 0:
        lines.append("(nothing queued — run \"Generate schedule\")")

    lines.append("")
    lines.append(f"HABITS — next {PREVIEW_WEEKS} Mondays")
    shown = 0
    for monday in su.upcoming_mondays(today, PREVIEW_WEEKS):
        idx = sched["habits"].get(monday.isoformat())
        if idx is None or not (0 <= idx < len(habits)):
            continue
        lines.append(f"{fmt_day(monday)} · {short_label(habits[idx], 'habits')}")
        shown += 1
    if shown == 0:
        lines.append("(nothing queued — run \"Generate schedule\")")

    lines += [
        "",
        "Don't like one? GitHub → Actions → \"Reroll scheduled item\"",
        "→ enter the date (e.g. " + (today + timedelta(days=1)).isoformat() + ") and quotes/habits.",
    ]

    text = "\n".join(lines)
    if len(text) > TELEGRAM_LIMIT:
        text = text[:TELEGRAM_LIMIT - 20].rstrip() + "\n…(truncated)"
    return text


def main():
    if not os.environ.get("BOT_TOKEN") or not ADMIN_CHAT_ID:
        print("Missing BOT_TOKEN or ADMIN_CHAT_ID.", file=sys.stderr)
        sys.exit(1)

    text = build_preview()
    send_text(ADMIN_CHAT_ID, text)
    print("Preview sent to admin only.")
    print(text)


if __name__ == "__main__":
    main()
