"""
Fallback path for Telegram updates: only does anything while the Vercel
webhook is NOT connected.

Normally the webhook delivers every message and button tap to GitHub
within seconds (see bot_brain.py). Telegram refuses getUpdates while a
webhook is set, so this script checks for one first and exits right away
if it finds it. If the webhook is ever disconnected (webhook.yml →
"disconnect"), this picks everything up again on its own schedule.

Everything it receives goes through bot_brain.Brain, so behaviour is
identical either way - just slower (GitHub runs this every few hours, not
every 5 minutes as the cron line suggests).

What a delivery report can and cannot tell you: Telegram confirms that a
message was accepted for delivery to his chat. It does NOT expose read
receipts to bots, so nothing here can tell you whether he opened it.

Required repo secrets:
  BOT_TOKEN
  ADMIN_CHAT_ID
  CUSTOMER_CHAT_ID
"""

import json
import os
import sys

import telegram_utils
from bot_brain import Brain

STATE_PATH = "state.json"


def load_offset() -> int:
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH) as f:
            return json.load(f).get("last_update_id", 0)
    return 0


def save_offset(update_id: int) -> None:
    with open(STATE_PATH, "w") as f:
        json.dump({"last_update_id": update_id}, f)


def webhook_connected() -> bool:
    url = telegram_utils.get_webhook_url()
    if url:
        print(f"Webhook is connected ({url.split('?')[0]}) - nothing to poll.")
    return bool(url)


def main():
    if not os.environ.get("BOT_TOKEN") or not os.environ.get("ADMIN_CHAT_ID"):
        print("Missing BOT_TOKEN or ADMIN_CHAT_ID.", file=sys.stderr)
        sys.exit(1)

    if "--check" in sys.argv:
        # used by the workflow to decide whether the processing job runs at all
        mode = "webhook" if webhook_connected() else "poll"
        out = os.environ.get("GITHUB_OUTPUT")
        if out:
            with open(out, "a") as f:
                f.write(f"mode={mode}\n")
        print(f"mode={mode}")
        return

    if webhook_connected():
        return

    offset = load_offset()
    updates = telegram_utils.get_updates(offset)
    if not updates:
        print("No new updates.")
        return

    brain = Brain()
    highest = offset - 1
    failed = False
    for update in updates:
        highest = max(highest, update["update_id"])
        try:
            brain.handle_update(update)
        except Exception as exc:  # noqa: BLE001 - one bad update must not block the rest
            failed = True
            print(f"update {update.get('update_id')} failed: {exc}", file=sys.stderr)

    save_offset(highest + 1)
    ok = brain.finish()
    sys.exit(0 if ok and not failed else 1)


if __name__ == "__main__":
    main()
