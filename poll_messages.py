"""
Two-way relay, checked every 5 minutes:

1. Anything your brother (CUSTOMER_CHAT_ID) sends the bot gets forwarded
   to you (ADMIN_CHAT_ID) as a report.
2. Anything YOU send the bot (in your own chat with it, as ADMIN_CHAT_ID)
   gets relayed straight to your brother (CUSTOMER_CHAT_ID) - this is how
   you trigger an on-demand reminder: just message the bot yourself.

Messages starting with "/" (bot commands like /start) are never relayed -
only plain text you actually type to be forwarded.

Required repo secrets:
  BOT_TOKEN
  ADMIN_CHAT_ID
  CUSTOMER_CHAT_ID   (script exits quietly if this isn't set yet)

Uses state.json (committed back to the repo by the workflow) to remember
which messages have already been handled, so nothing gets double-sent and
nothing gets missed between runs.
"""

import json
import os
import sys

from telegram_utils import get_updates, send_text, describe_message

ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID")
CUSTOMER_CHAT_ID = os.environ.get("CUSTOMER_CHAT_ID", "").strip()
STATE_PATH = "state.json"


def load_offset() -> int:
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH) as f:
            return json.load(f).get("last_update_id", 0)
    return 0


def save_offset(update_id: int) -> None:
    with open(STATE_PATH, "w") as f:
        json.dump({"last_update_id": update_id}, f)


def handle_customer_message(message: dict) -> None:
    """Brother messaged the bot -> report it to admin."""
    summary = describe_message(message)
    report = f"\U0001F4AC Your brother messaged the bot:\n\n{summary}"
    send_text(ADMIN_CHAT_ID, report)
    print("Reported to admin:", summary)


def handle_admin_message(message: dict) -> None:
    """Admin messaged the bot -> relay plain text straight to the brother."""
    text = message.get("text", "")
    if text.startswith("/"):
        print("Ignored admin command:", text)
        return
    if not text:
        print("Ignored non-text admin message (only text is relayed).")
        return

    send_text(CUSTOMER_CHAT_ID, text)
    send_text(ADMIN_CHAT_ID, f"✅ Relayed to your brother:\n\n\"{text}\"")
    print("Relayed to customer:", text)


def main():
    if not os.environ.get("BOT_TOKEN") or not ADMIN_CHAT_ID:
        print("Missing BOT_TOKEN or ADMIN_CHAT_ID.", file=sys.stderr)
        sys.exit(1)

    if not CUSTOMER_CHAT_ID:
        print("CUSTOMER_CHAT_ID not set yet - nothing to relay. Skipping.")
        return

    offset = load_offset()
    updates = get_updates(offset)

    if not updates:
        print("No new updates.")
        return

    highest_id = offset - 1
    for update in updates:
        highest_id = max(highest_id, update["update_id"])
        message = update.get("message")
        if not message:
            continue

        chat_id = str(message["chat"]["id"])
        if chat_id == str(CUSTOMER_CHAT_ID):
            handle_customer_message(message)
        elif chat_id == str(ADMIN_CHAT_ID):
            handle_admin_message(message)
        else:
            print("Ignored message from unrecognized chat:", chat_id)

    save_offset(highest_id + 1)


if __name__ == "__main__":
    main()
