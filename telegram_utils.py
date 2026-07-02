"""
Small shared helpers for talking to the Telegram Bot API.
Used by both send_countdown.py and poll_messages.py.
"""

import os
import requests

BOT_TOKEN = os.environ.get("BOT_TOKEN")
API_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"


def send_text(chat_id: str, text: str) -> dict:
    resp = requests.post(f"{API_BASE}/sendMessage", json={"chat_id": chat_id, "text": text})
    resp.raise_for_status()
    return resp.json()


def send_photo(chat_id: str, photo_path: str, caption: str) -> dict:
    with open(photo_path, "rb") as f:
        resp = requests.post(
            f"{API_BASE}/sendPhoto",
            data={"chat_id": chat_id, "caption": caption},
            files={"photo": f},
        )
    resp.raise_for_status()
    return resp.json()


def get_updates(offset: int) -> list:
    resp = requests.get(f"{API_BASE}/getUpdates", params={"offset": offset, "timeout": 0})
    resp.raise_for_status()
    return resp.json().get("result", [])


def describe_message(message: dict) -> str:
    """Turn a Telegram message object into a short human-readable summary."""
    if "text" in message:
        return f'"{message["text"]}"'
    if "photo" in message:
        return "[sent a photo]"
    if "sticker" in message:
        emoji = message["sticker"].get("emoji", "")
        return f"[sent a sticker {emoji}]"
    if "voice" in message:
        return "[sent a voice message]"
    if "video" in message:
        return "[sent a video]"
    if "document" in message:
        return "[sent a file]"
    if "video_note" in message:
        return "[sent a video note]"
    return "[sent something the bot doesn't recognize]"
