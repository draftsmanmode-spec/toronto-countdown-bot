"""
Sends the scheduled quote for today to your brother (CUSTOMER_CHAT_ID),
reports a copy to you (ADMIN_CHAT_ID), and logs it to quote_state.json so
update_site.py can put it on the website.

Which quote goes out is decided in advance by the schedule (schedule.json),
not randomly at send time - so you can preview and swap upcoming quotes
before they ever reach him.

Required repo secrets:
  BOT_TOKEN
  ADMIN_CHAT_ID
  CUSTOMER_CHAT_ID
Optional:
  LANG_MODE   both (default) | uk | en
"""

import os
import sys
from datetime import date

from telegram_utils import send_text
from render import build_quote_message
import schedule_utils as su

ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID")
CUSTOMER_CHAT_ID = os.environ.get("CUSTOMER_CHAT_ID", "").strip()


def todays_quote(today):
    """Return (quote, index, from_schedule)."""
    quotes = su.load_library("quotes")
    sched = su.load_schedule()
    idx = su.scheduled_index("quotes", today, sched)
    if idx is not None and 0 <= idx < len(quotes):
        return quotes[idx], idx, True

    # Nothing queued for today (schedule ran dry or was cleared) - fall back
    # so the send never silently fails, and flag it in the admin report.
    idx = su.pick_index("quotes", sched)
    return quotes[idx], idx, False


def main():
    if not os.environ.get("BOT_TOKEN") or not ADMIN_CHAT_ID:
        print("Missing BOT_TOKEN or ADMIN_CHAT_ID.", file=sys.stderr)
        sys.exit(1)

    today = date.today()
    quote, idx, from_schedule = todays_quote(today)
    message = build_quote_message(quote)

    # log it for the website + no-repeat tracking
    state = su.load_json(su.QUOTE_STATE_PATH, {"used_indices": [], "history": []})
    used = set(state.get("used_indices", []))
    used.add(idx)
    state["used_indices"] = sorted(used)
    entry = {
        "date": today.isoformat(),
        "index": idx,
        "text": quote["text"],
        "text_uk": quote.get("text_uk"),
        "author": quote.get("author"),
    }
    history = state.setdefault("history", [])
    if history and history[-1].get("date") == entry["date"]:
        history[-1] = entry  # re-run on the same day replaces, never duplicates
    else:
        history.append(entry)
    su.save_json(su.QUOTE_STATE_PATH, state)

    note = "" if from_schedule else (
        "\n\n⚠️ Nothing was scheduled for today, so this one was picked "
        "automatically. Run \"Generate schedule\" to refill the queue."
    )

    if CUSTOMER_CHAT_ID:
        send_text(CUSTOMER_CHAT_ID, message)
        print("Sent to customer.")
        send_text(ADMIN_CHAT_ID, "\U0001F4E4 Sent to your brother just now:\n\n" + message + note)
        print("Sent report to admin.")
    else:
        send_text(ADMIN_CHAT_ID, "⚠️ CUSTOMER_CHAT_ID not set - sent to you only:\n\n" + message)
        print("Sent to admin only (no customer chat id set).")

    print(f"Quote index {idx}, from_schedule={from_schedule}")


if __name__ == "__main__":
    main()
