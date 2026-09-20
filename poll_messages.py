"""
Two-way relay + delivery reporting, checked every 5 minutes.

1. Anything your brother (CUSTOMER_CHAT_ID) sends the bot is reported to
   you (ADMIN_CHAT_ID).
2. Anything YOU send the bot is relayed straight to him, and you get a
   delivery report back - a green check if Telegram accepted it, a red X
   with the reason if it did not. A failed send is never silent.
3. Commands you can text the bot instead of opening GitHub:
       /schedule  (or /preview)  - what's queued to go out next
       /help                     - list the commands

What a delivery report can and cannot tell you: Telegram's Bot API
confirms that a message was accepted for delivery to his chat. It does NOT
expose read receipts to bots, so nothing here can tell you whether he
actually opened it. That's a platform limit, not a gap in this code.

Required repo secrets:
  BOT_TOKEN
  ADMIN_CHAT_ID
  CUSTOMER_CHAT_ID   (script exits quietly if this isn't set yet)
"""

import json
import os
import sys

from telegram_utils import get_updates, send_text, describe_message

ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID")
CUSTOMER_CHAT_ID = os.environ.get("CUSTOMER_CHAT_ID", "").strip()
STATE_PATH = "state.json"

HELP_TEXT = (
    "\U0001F916 Bot commands\n\n"
    "/schedule — what's queued to send next\n"
    "/help — this list\n\n"
    "Anything else you type here is relayed straight to your brother, "
    "and you get a delivery report back."
)


def load_offset() -> int:
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH) as f:
            return json.load(f).get("last_update_id", 0)
    return 0


def save_offset(update_id: int) -> None:
    with open(STATE_PATH, "w") as f:
        json.dump({"last_update_id": update_id}, f)


def handle_customer_message(message: dict) -> None:
    """Brother messaged the bot -> report it to you."""
    summary = describe_message(message)
    send_text(ADMIN_CHAT_ID, f"\U0001F4AC Your brother messaged the bot:\n\n{summary}")
    print("Reported to admin:", summary)


def handle_command(text: str) -> bool:
    """Handle an admin command. Returns True if it was one."""
    cmd = text.split()[0].lower().lstrip("/")

    if cmd in ("schedule", "preview"):
        try:
            from send_schedule_preview import build_preview
            send_text(ADMIN_CHAT_ID, build_preview())
            print("Sent schedule preview on request.")
        except Exception as exc:  # noqa: BLE001
            send_text(ADMIN_CHAT_ID, f"❌ Couldn't build the schedule preview: {exc}")
            print("Preview failed:", exc, file=sys.stderr)
        return True

    if cmd in ("help", "start"):
        send_text(ADMIN_CHAT_ID, HELP_TEXT)
        print("Sent help.")
        return True

    send_text(ADMIN_CHAT_ID, f"❓ Unknown command “/{cmd}”. Send /help for the list.")
    print("Unknown command:", cmd)
    return True


def handle_admin_message(message: dict) -> None:
    """You messaged the bot -> run a command, or relay the text to him."""
    text = message.get("text", "")

    if text.startswith("/"):
        handle_command(text)
        return

    if not text:
        send_text(
            ADMIN_CHAT_ID,
            "ℹ️ Only text messages get relayed — that one wasn't sent on.",
        )
        print("Ignored non-text admin message.")
        return

    try:
        send_text(CUSTOMER_CHAT_ID, text)
    except Exception as exc:  # noqa: BLE001 - a failed relay must never be silent
        send_text(
            ADMIN_CHAT_ID,
            f"❌ NOT delivered to your brother:\n\n“{text}”\n\nReason: {exc}",
        )
        print("Relay FAILED:", exc, file=sys.stderr)
        return

    send_text(
        ADMIN_CHAT_ID,
        f"✅ Delivered to your brother:\n\n“{text}”",
    )
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
