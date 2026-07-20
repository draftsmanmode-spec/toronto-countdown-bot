"""
Sends the daily countdown photo to your brother (CUSTOMER_CHAT_ID), then
sends you (ADMIN_CHAT_ID) a copy of exactly what he received, so you always
know what went out.

Required repo secrets:
  BOT_TOKEN         - from @BotFather
  ADMIN_CHAT_ID     - your chat ID (you, the controller)
  CUSTOMER_CHAT_ID  - your brother's chat ID (set this once he has messaged
                      the bot at least once; until then the script sends
                      only to you with a warning)
  PAGES_URL         - the live link to docs/index.html (GitHub Pages)

Honest limitation: Telegram's Bot API does not expose read receipts to
bots. "Sent successfully" is the most this script (or any bot) can ever
confirm — there is no way to know if he actually opened/read the message.
"""

import os
import sys
from datetime import date

from telegram_utils import send_text, send_photo

ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID")
CUSTOMER_CHAT_ID = os.environ.get("CUSTOMER_CHAT_ID", "").strip()
PAGES_URL = os.environ.get("PAGES_URL", "").strip()

FLIGHT_DATE = date(2026, 8, 11)
PHOTO_PATH = "countdown.png"


def days_left() -> int:
    return (FLIGHT_DATE - date.today()).days


def build_caption(days: int) -> str:
    if days > 1:
        text = f"{days} days till Toronto \U0001F1E8\U0001F1E6\u2708\uFE0F\n\nFrankfurt \u2192 Toronto, nonstop, lands 17:55. Getting closer!"
    elif days == 1:
        text = "1 day left. TOMORROW. \U0001F1E8\U0001F1E6\u2708\uFE0F"
    elif days == 0:
        text = "TODAY'S THE DAY. See you soon! \U0001F1E8\U0001F1E6\u2708\uFE0F\U0001F389"
    else:
        text = "He's already in Toronto \U0001F1E8\U0001F1E6 (or this date needs updating)"
    if PAGES_URL:
        text += f"\n\n\U0001F517 {PAGES_URL}"
    return text


def main():
    if not os.environ.get("BOT_TOKEN") or not ADMIN_CHAT_ID:
        print("Missing BOT_TOKEN or ADMIN_CHAT_ID.", file=sys.stderr)
        sys.exit(1)

    caption = build_caption(days_left())
    has_photo = os.path.exists(PHOTO_PATH)

    if not CUSTOMER_CHAT_ID:
        # No customer set up yet -> just tell the admin, don't send anywhere else
        warn = "\u26A0\uFE0F CUSTOMER_CHAT_ID isn't set yet, so today's countdown only went to you.\n\n" + caption
        if has_photo:
            send_photo(ADMIN_CHAT_ID, PHOTO_PATH, warn)
        else:
            send_text(ADMIN_CHAT_ID, warn)
        print("Sent to admin only (no customer chat id set).")
        return

    # 1. Send to the customer (your brother)
    if has_photo:
        send_photo(CUSTOMER_CHAT_ID, PHOTO_PATH, caption)
    else:
        send_text(CUSTOMER_CHAT_ID, caption)
    print("Sent to customer.")

    # 2. Report the same thing to the admin (you), so you know it went out
    report = "\U0001F4E4 Sent to your brother just now:\n\n" + caption
    if has_photo:
        send_photo(ADMIN_CHAT_ID, PHOTO_PATH, report)
    else:
        send_text(ADMIN_CHAT_ID, report)
    print("Sent report to admin.")


if __name__ == "__main__":
    main()
