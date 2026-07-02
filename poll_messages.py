"""
Checks for any new messages your brother has sent to the bot, and forwards
a report of each one to you.

Runs on a short schedule (every 5 minutes) rather than instantly, because
there's no always-on server here — this is "near real-time", not instant.

Required repo secrets:
  BOT_TOKEN
  ADMIN_CHAT_ID
  CUSTOMER_CHAT_ID   (script exits quietly if this isn't set yet)

Uses state.json (committed back to the repo by the workflow) to remember
which messages it has already reported, so nothing gets double-sent and
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


def main():
    if not os.environ.get("BOT_TOKEN") or not ADMIN_CHAT_ID:
        print("Missing BOT_TOKEN or ADMIN_CHAT_ID.", file=sys.stderr)
        sys.exit(1)

    if not CUSTOMER_CHAT_ID:
        print("CUSTOMER_CHAT_ID not set yet - nothing to poll for. Skipping.")
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
        if chat_id != str(CUSTOMER_CHAT_ID):
            continue  # ignore messages from anyone except your brother

        summary = describe_message(message)
        report = f"\U0001F4AC Your brother messaged the bot:\n\n{summary}"
        send_text(ADMIN_CHAT_ID, report)
        print("Forwarded:", summary)

    save_offset(highest_id + 1)


if __name__ == "__main__":
    main()
