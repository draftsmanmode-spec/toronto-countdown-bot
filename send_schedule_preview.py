"""
Sends YOU (ADMIN_CHAT_ID only - never the customer) a preview of the
weekly habits queued to go out, plus where the daily quote approval stands.

Runs weekly on Saturdays, and on demand from the Actions tab
("Send schedule preview").

Env:
  PREVIEW_WEEKS   how many upcoming habits to show (default 4)
"""

import os
import sys
from datetime import date, timedelta

from telegram_utils import send_text
from render import short_label
import schedule_utils as su

ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID")
PREVIEW_WEEKS = int(os.environ.get("PREVIEW_WEEKS") or 4)

TELEGRAM_LIMIT = 4000  # real cap is 4096; leave headroom


def fmt_day(d: date) -> str:
    return d.strftime("%d %b (%a)")


def quote_status_line(today) -> str:
    """Today's approval status plus how many quotes are ready, without touching state."""
    import approval
    state = approval.load_state()
    pool = approval.build_pool(state["enriched"])
    approval.seed_from_history(state, pool)
    ready = approval.eligible(pool, state, today, (), 0)
    fresh = sum(1 for i in ready if approval.is_fresh_article(i, today))
    day = state["days"].get(today.isoformat())
    status = {"sent": "sent ✅", "skipped": "skipped ⏭", "pending": "waiting for your tap",
              "expired": "no answer"}.get((day or {}).get("status"), "card not out yet")
    return (f"Today: {status}. {len(ready)} ready to offer ({fresh} fresh articles). "
            "Each morning's card comes with ✅ ⏭ 🚫 🔄 buttons.")


def build_preview(today=None):
    if today is None:
        import approval
        today = approval.now_local().date()
    sched = su.load_schedule()
    habits = su.load_library("habits")

    lines = ["\U0001F4C5 Upcoming sends — review before they go out", ""]

    lines.append("QUOTES — daily approval")
    lines.append(quote_status_line(today))
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
        "Don't like a habit? GitHub → Actions → \"Reroll scheduled item\"",
        "→ enter the date (e.g. " + (today + timedelta(days=1)).isoformat() + ").",
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
