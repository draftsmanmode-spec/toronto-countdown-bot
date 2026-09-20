"""
Sends the scheduled habit for this Monday to your brother
(CUSTOMER_CHAT_ID) and reports a copy to you (ADMIN_CHAT_ID).

Which habit goes out is decided in advance by schedule.json, so you can
preview and swap upcoming habits before they're sent.

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
from render import build_habit_message
import schedule_utils as su

ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID")
CUSTOMER_CHAT_ID = os.environ.get("CUSTOMER_CHAT_ID", "").strip()


def todays_habit(today):
    """Return (habit, index, from_schedule)."""
    habits = su.load_library("habits")
    sched = su.load_schedule()
    idx = su.scheduled_index("habits", today, sched)
    if idx is not None and 0 <= idx < len(habits):
        return habits[idx], idx, True

    idx = su.pick_index("habits", sched)
    return habits[idx], idx, False


def main():
    if not os.environ.get("BOT_TOKEN") or not ADMIN_CHAT_ID:
        print("Missing BOT_TOKEN or ADMIN_CHAT_ID.", file=sys.stderr)
        sys.exit(1)

    today = date.today()
    habit, idx, from_schedule = todays_habit(today)
    message = build_habit_message(habit)

    state = su.load_json(su.HABIT_STATE_PATH, {"used_indices": [], "history": []})
    used = set(state.get("used_indices", []))
    used.add(idx)
    state["used_indices"] = sorted(used)
    entry = {
        "date": today.isoformat(),
        "index": idx,
        "title": habit["title"],
        "title_uk": habit.get("title_uk"),
    }
    history = state.setdefault("history", [])
    if history and history[-1].get("date") == entry["date"]:
        history[-1] = entry  # re-run on the same day replaces, never duplicates
    else:
        history.append(entry)
    su.save_json(su.HABIT_STATE_PATH, state)

    if from_schedule:
        note = ""
    elif today.weekday() != 0:
        note = (
            "\n\nℹ️ Habits are scheduled for Mondays, so this off-day run picked "
            "one automatically — it did not use the queue."
        )
    else:
        note = (
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

    print(f"Habit index {idx}, from_schedule={from_schedule}")


if __name__ == "__main__":
    main()
