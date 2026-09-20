"""
Sends one research-grounded habit suggestion per week to your brother
(CUSTOMER_CHAT_ID), reports a copy to you (ADMIN_CHAT_ID), and logs it to
weekly_habit_state.json.

Picks from habits.json without repeating any until the whole list has
been used once, then reshuffles - same pattern as send_quote.py.

Required repo secrets:
  BOT_TOKEN
  ADMIN_CHAT_ID
  CUSTOMER_CHAT_ID
"""

import json
import os
import random
import sys
from datetime import date

from telegram_utils import send_text

ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID")
CUSTOMER_CHAT_ID = os.environ.get("CUSTOMER_CHAT_ID", "").strip()

HABITS_PATH = "habits.json"
STATE_PATH = "weekly_habit_state.json"


def load_habits():
    with open(HABITS_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_state():
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {"used_indices": [], "history": []}


def save_state(state):
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def pick_habit(habits, state):
    used = set(state.get("used_indices", []))
    available = [i for i in range(len(habits)) if i not in used]
    if not available:
        used = set()
        available = list(range(len(habits)))
    idx = random.choice(available)
    used.add(idx)
    state["used_indices"] = sorted(used)
    return habits[idx]


def build_message(habit: dict) -> str:
    return (
        f"\U0001F331 This week's habit to try:\n\n"
        f"*{habit['title']}*\n\n"
        f"{habit['action']}\n\n"
        f"Why: {habit['why']}"
    )


def main():
    if not os.environ.get("BOT_TOKEN") or not ADMIN_CHAT_ID:
        print("Missing BOT_TOKEN or ADMIN_CHAT_ID.", file=sys.stderr)
        sys.exit(1)

    habits = load_habits()
    state = load_state()
    habit = pick_habit(habits, state)
    message = build_message(habit)

    today = date.today().isoformat()
    state.setdefault("history", []).append({
        "date": today,
        "title": habit["title"],
    })
    save_state(state)

    if CUSTOMER_CHAT_ID:
        send_text(CUSTOMER_CHAT_ID, message)
        print("Sent to customer.")
        send_text(ADMIN_CHAT_ID, "\U0001F4E4 Sent to your brother just now:\n\n" + message)
        print("Sent report to admin.")
    else:
        send_text(ADMIN_CHAT_ID, "\u26A0\uFE0F CUSTOMER_CHAT_ID not set - sent to you only:\n\n" + message)
        print("Sent to admin only (no customer chat id set).")


if __name__ == "__main__":
    main()
