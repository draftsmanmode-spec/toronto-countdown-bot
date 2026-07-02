"""
Sends a daily "days until the flight" message + countdown screenshot to your
brother via Telegram.

Setup (one time):
1. Create a bot with @BotFather on Telegram -> get BOT_TOKEN
2. Message your new bot from your brother's account (he sends it /start)
3. Get his CHAT_ID by visiting:
   https://api.telegram.org/bot<BOT_TOKEN>/getUpdates
   (look for "chat":{"id": ...} in the response after he messages the bot)
4. Enable GitHub Pages for this repo (Settings -> Pages -> Deploy from
   branch -> main -> /docs) and copy the URL it gives you into a PAGES_URL
   secret. This is the link that gets included in the message.
5. Set BOT_TOKEN, CHAT_ID and PAGES_URL as repo secrets
   (Settings -> Secrets and variables -> Actions)

Run manually to test:
   BOT_TOKEN=xxx CHAT_ID=xxx PAGES_URL=xxx python3 send_countdown.py
"""

import os
import sys
from datetime import date
import requests

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
PAGES_URL = os.environ.get("PAGES_URL", "").strip()

FLIGHT_DATE = date(2026, 8, 9)  # August 9, 2026
PHOTO_PATH = "countdown.png"


def days_left() -> int:
    today = date.today()
    return (FLIGHT_DATE - today).days


def build_caption(days: int) -> str:
    if days > 1:
        text = f"{days} days till Toronto \U0001F1E8\U0001F1E6✈️\n\nKoeln → Toronto. Getting closer!"
    elif days == 1:
        text = "1 day left. TOMORROW. \U0001F1E8\U0001F1E6✈️"
    elif days == 0:
        text = "TODAY'S THE DAY. See you soon! \U0001F1E8\U0001F1E6✈️\U0001F389"
    else:
        text = "He's already in Toronto \U0001F1E8\U0001F1E6 (or this date needs updating)"

    if PAGES_URL:
        text += f"\n\n\U0001F517 {PAGES_URL}"
    return text


def send_photo(caption: str) -> None:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    with open(PHOTO_PATH, "rb") as f:
        resp = requests.post(
            url,
            data={"chat_id": CHAT_ID, "caption": caption},
            files={"photo": f},
        )
    resp.raise_for_status()
    print("Sent photo with caption:", caption)


def send_text(caption: str) -> None:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    resp = requests.post(url, json={"chat_id": CHAT_ID, "text": caption})
    resp.raise_for_status()
    print("Sent text (no photo found):", caption)


if __name__ == "__main__":
    if not BOT_TOKEN or not CHAT_ID:
        print("Missing BOT_TOKEN or CHAT_ID environment variables.", file=sys.stderr)
        sys.exit(1)

    msg = build_caption(days_left())
    if os.path.exists(PHOTO_PATH):
        send_photo(msg)
    else:
        send_text(msg)
