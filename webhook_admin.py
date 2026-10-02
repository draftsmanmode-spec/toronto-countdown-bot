"""
Connects or disconnects the Telegram webhook (run from Actions →
"Telegram webhook").

  connect     point Telegram at the Vercel relay (WEBHOOK_URL), so button
              taps and messages reach GitHub in seconds
  disconnect  remove it; poll_messages.py takes over again (slow, but needs
              nothing outside GitHub)
  status      just report what's set

The secret Telegram sends with every webhook call is derived from
BOT_TOKEN, so the Vercel side can check it without a second secret to
manage. See webhook_secret() in vercel/api/telegram.py - they must match.
"""

import hashlib
import os
import sys

import telegram_utils as tg

MODE = (os.environ.get("WEBHOOK_MODE") or "status").strip().lower()
URL = (os.environ.get("WEBHOOK_URL") or "").strip().rstrip("/")
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID")


def webhook_secret(bot_token: str) -> str:
    return hashlib.sha256(f"tg-webhook:{bot_token}".encode()).hexdigest()[:48]


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
    print(status)
    tg.send_text(ADMIN_CHAT_ID, f"{msg}\n\n{status}" if msg else status)


if __name__ == "__main__":
    main()
