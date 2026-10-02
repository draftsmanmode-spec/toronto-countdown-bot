"""
Connects or disconnects the Telegram webhook (run from Actions →
"Telegram webhook").

  connect     point Telegram at the Vercel relay (WEBHOOK_URL), so button
              taps and messages reach GitHub in seconds, then run `test`
  disconnect  remove it; poll_messages.py takes over again (slow, but needs
              nothing outside GitHub)
  test        send a fake "/ping" from you through the relay. If the whole
              chain works (Vercel → GitHub → bot) you get a "Pong" on Telegram
  status      just report what's set

The secret Telegram sends with every webhook call is derived from
BOT_TOKEN, so there's no second secret to manage. The relay forwards it and
bot_brain.dispatched_update() checks it on GitHub; if BOT_TOKEN is also set
in Vercel, vercel/api/telegram.py checks it there too. They must match.
"""

import hashlib
import os
import sys
import time

import requests

import telegram_utils as tg

MODE = (os.environ.get("WEBHOOK_MODE") or "status").strip().lower()
URL = (os.environ.get("WEBHOOK_URL") or "").strip().rstrip("/")
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID")


def webhook_secret(bot_token: str) -> str:
    return hashlib.sha256(f"tg-webhook:{bot_token}".encode()).hexdigest()[:48]


def self_test(token: str) -> str:
    """POST a fake /ping from the admin chat to the relay, exactly as Telegram would."""
    info = tg.api("getWebhookInfo") or {}
    hook = info.get("url")
    if not hook:
        return "Self-test skipped: no webhook connected."
    update = {
        "update_id": 0,
        "message": {
            "message_id": 0,
            "date": int(time.time()),
            "chat": {"id": int(ADMIN_CHAT_ID), "type": "private"},
            "text": "/ping",
        },
    }
    try:
        resp = requests.post(hook, json=update, timeout=20,
                             headers={"X-Telegram-Bot-Api-Secret-Token": webhook_secret(token)})
    except requests.RequestException as exc:
        return f"❌ Self-test: couldn't reach the relay ({exc})."
    if resp.status_code == 200 and resp.json().get("ok"):
        return "✅ Self-test: the relay handed a /ping to GitHub. A \"Pong\" should arrive in about 30 seconds."
    return f"❌ Self-test: relay answered {resp.status_code} {resp.text[:150]}"


def main():
    token = os.environ.get("BOT_TOKEN")
    if not token or not ADMIN_CHAT_ID:
        print("Missing BOT_TOKEN or ADMIN_CHAT_ID.", file=sys.stderr)
        sys.exit(1)

    if MODE == "connect":
        if not URL.startswith("https://"):
            print("WEBHOOK_URL must be the https:// address of the Vercel project.", file=sys.stderr)
            sys.exit(1)
        hook = URL if URL.endswith("/api/telegram") else f"{URL}/api/telegram"
        tg.api("setWebhook", {
            "url": hook,
            "secret_token": webhook_secret(token),
            "allowed_updates": ["message", "callback_query"],
            "drop_pending_updates": False,
        })
        msg = f"\U0001F517 Instant mode ON. Button taps and messages now go through {hook}"
    elif MODE == "test":
        msg = self_test(token)
    elif MODE == "disconnect":
        tg.api("deleteWebhook", {"drop_pending_updates": False})
        msg = "\U0001F50C Instant mode OFF. Back to GitHub polling (taps may take hours)."
    else:
        msg = None

    info = tg.api("getWebhookInfo") or {}
    status = (f"Webhook: {info.get('url') or '(none, polling mode)'}\n"
              f"Pending updates: {info.get('pending_update_count', 0)}")
    if info.get("last_error_message"):
        status += f"\nLast error: {info['last_error_message']}"
    if MODE == "connect":
        msg += "\n" + self_test(token)
    print(msg or "")
    print(status)
    tg.send_text(ADMIN_CHAT_ID, f"{msg}\n\n{status}" if msg else status)


if __name__ == "__main__":
    main()
