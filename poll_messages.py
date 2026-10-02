"""
Fallback path for Telegram updates: only does anything while the Vercel
webhook is NOT connected.

Normally the webhook delivers every message and button tap to GitHub
within seconds (see bot_brain.py). Telegram refuses getUpdates while a
webhook is set, so this script checks for one first and exits right away
if it finds it. If the webhook is ever disconnected (webhook.yml →
"disconnect"), this picks everything up again on its own schedule.

Everything it receives goes through bot_brain.drain/Brain, so behaviour
is identical either way - just slower (GitHub runs this every few hours,
not every 5 minutes as the cron line suggests; the hourly quote ticks also
drain updates).

What a delivery report can and cannot tell you: Telegram confirms that a
message was accepted for delivery to his chat. It does NOT expose read
receipts to bots, so nothing here can tell you whether he opened it.

Required repo secrets:
  BOT_TOKEN
  ADMIN_CHAT_ID
  CUSTOMER_CHAT_ID
"""

import os
import sys

import telegram_utils
from bot_brain import Brain, drain


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

    brain = Brain()
    handled = drain(brain)
    if handled < 0:
        print("Webhook is connected - nothing to poll.")
        return
    print(f"Handled {handled} update(s).")
    ok = brain.finish()
    sys.exit(0 if ok and not brain.failures else 1)


if __name__ == "__main__":
    main()
