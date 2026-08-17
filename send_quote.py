"""
Sends one quote per day to your brother (CUSTOMER_CHAT_ID), reports a copy
to you (ADMIN_CHAT_ID), and logs it to quote_state.json so
update_site.py can show it on the website.

Picks quotes from quotes.json without repeating any until the whole
library has been used once, then reshuffles.

Required repo secrets:
  BOT_TOKEN
  ADMIN_CHAT_ID
  CUSTOMER_CHAT_ID

Honest note: quotes.json is a mix of well-known, correctly-attributed
quotes and original unattributed lines - it is NOT a verified transcript
of specific Diary of a CEO episodes. Swap in exact verified quotes there
any time.
"""

import json
import os
import random
import sys
from datetime import date

from telegram_utils import send_text

ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID")
CUSTOMER_CHAT_ID = os.environ.get("CUSTOMER_CHAT_ID", "").strip()

QUOTES_PATH = "quotes.json"
STATE_PATH = "quote_state.json"


def load_quotes():
    with open(QUOTES_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_state():
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {"used_indices": [], "history": []}


def save_state(state):
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def pick_quote(quotes, state):
    used = set(state.get("used_indices", []))
    available = [i for i in range(len(quotes)) if i not in used]
    if not available:
        # everyone's been used - start a fresh cycle
        used = set()
        available = list(range(len(quotes)))
    idx = random.choice(available)
    used.add(idx)
    state["used_indices"] = sorted(used)
    return quotes[idx]


def build_message(quote: dict) -> str:
    text = f"💭 Today's quote:\n\n“{quote['text']}”"
    if quote.get("author"):
        text += f"\n— {quote['author']}"
    return text


def main():
    if not os.environ.get("BOT_TOKEN") or not ADMIN_CHAT_ID:
        print("Missing BOT_TOKEN or ADMIN_CHAT_ID.", file=sys.stderr)
        sys.exit(1)

    quotes = load_quotes()
    state = load_state()
    quote = pick_quote(quotes, state)
    message = build_message(quote)

    today = date.today().isoformat()
    state.setdefault("history", []).append({
        "date": today,
        "text": quote["text"],
        "author": quote.get("author"),
    })
    save_state(state)

    if CUSTOMER_CHAT_ID:
        send_text(CUSTOMER_CHAT_ID, message)
        print("Sent to customer.")
        send_text(ADMIN_CHAT_ID, "📤 Sent to your brother just now:\n\n" + message)
        print("Sent report to admin.")
    else:
        send_text(ADMIN_CHAT_ID, "⚠️ CUSTOMER_CHAT_ID not set - sent to you only:\n\n" + message)
        print("Sent to admin only (no customer chat id set).")


if __name__ == "__main__":
    main()
