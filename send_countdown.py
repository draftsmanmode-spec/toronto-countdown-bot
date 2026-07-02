"""
Sends a daily "days until the flight" message to your brother via Telegram.

Setup (one time):
1. Create a bot with @BotFather on Telegram -> get BOT_TOKEN
2. Message your new bot from your brother's account (he sends it /start)
3. Get his CHAT_ID by visiting:
   https://api.telegram.org/bot<BOT_TOKEN>/getUpdates
   (look for "chat":{"id": ...} in the response after he messages the bot)
4. Set BOT_TOKEN and CHAT_ID as environment variables (see GitHub Actions
   workflow in this folder for how to store them as secrets)

Run manually to test:
   BOT_TOKEN=xxx CHAT_ID=xxx python3 send_countdown.py
"""

import os
import sys
from datetime import date
import requests

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

FLIGHT_DATE = date(2026, 8, 9)  # August 9, 2026


def days_left() -> int:
    today = date.today()
    return (FLIGHT_DATE - today).days


def build_message(days: int) -> str:
    if days > 1:
        return f"{days} days till Toronto \U0001F1E8\U0001F1E6✈️\n\nKöln → Toronto. Getting closer!"
    elif days == 1:
        return "1 day left. TOMORROW. \U0001F1E8\U0001F1E6✈️"
    elif days == 0:
        return "TODAY'S THE DAY. See you soon! \U0001F1E8\U0001F1E6✈️\U0001F389"
    else:
        return "He's already in Toronto \U0001F1E8\U0001F1E6 (or this date needs updating)"


def send_message(text: str) -> None:
    if not BOT_TOKEN or not CHAT_ID:
        print("Missing BOT_TOKEN or CHAT_ID environment variables.", file=sys.stderr)
        sys.exit(1)

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    resp = requests.post(url, json={"chat_id": CHAT_ID, "text": text})
    resp.raise_for_status()
    print("Sent:", text)


if __name__ == "__main__":
    msg = build_message(days_left())
    send_message(msg)
