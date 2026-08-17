"""Shared Telegram helper functions (same as the countdown bot's version)."""

import os
import requests

BOT_TOKEN = os.environ.get("BOT_TOKEN")
API_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"


def send_text(chat_id: str, text: str) -> dict:
    resp = requests.post(f"{API_BASE}/sendMessage", json={"chat_id": chat_id, "text": text})
    resp.raise_for_status()
    return resp.json()
