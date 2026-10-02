"""
Shared Telegram helper functions.

Every call goes through api() so errors are reported the same way and a
429 "slow down" from Telegram is retried once after the delay it asks for,
instead of failing the whole run.
"""

import os
import time

import requests

BOT_TOKEN = os.environ.get("BOT_TOKEN")
API_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"

TELEGRAM_LIMIT = 4096


class TelegramError(RuntimeError):
    pass


def api(method: str, payload: dict | None = None, timeout: int = 30) -> dict | list | bool:
    """POST to the Bot API and return `result`, raising TelegramError on failure."""
    for attempt in range(2):
        resp = requests.post(f"{API_BASE}/{method}", json=payload or {}, timeout=timeout)
        try:
            data = resp.json()
        except ValueError:
            resp.raise_for_status()
            raise TelegramError(f"{method}: non-JSON response ({resp.status_code})")

        if data.get("ok"):
            return data.get("result")

        retry_after = (data.get("parameters") or {}).get("retry_after")
        if resp.status_code == 429 and retry_after and attempt == 0:
            time.sleep(min(int(retry_after), 30))
            continue
        raise TelegramError(f"{method}: {data.get('description') or resp.status_code}")
    raise TelegramError(f"{method}: gave up after retry")


def clip(text: str, limit: int = TELEGRAM_LIMIT) -> str:
    return text if len(text) <= limit else text[: limit - 2].rstrip() + " …"


def send_text(chat_id: str, text: str, reply_markup: dict | None = None,
              reply_to: int | None = None) -> dict:
    payload = {"chat_id": chat_id, "text": clip(text), "disable_web_page_preview": True}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    if reply_to:
        payload["reply_parameters"] = {"message_id": reply_to, "allow_sending_without_reply": True}
    return api("sendMessage", payload)


def edit_text(chat_id: str, message_id: int, text: str, reply_markup: dict | None = None) -> None:
    payload = {"chat_id": chat_id, "message_id": message_id, "text": clip(text),
               "disable_web_page_preview": True}
    # an omitted reply_markup removes the buttons, which is what we want by default
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        api("editMessageText", payload)
    except TelegramError as exc:
        if "message is not modified" not in str(exc):
            raise


def remove_buttons(chat_id: str, message_id: int) -> None:
    try:
        api("editMessageReplyMarkup", {"chat_id": chat_id, "message_id": message_id})
    except TelegramError as exc:
        # already gone, too old to edit, or deleted - none of these matter
        print(f"(could not remove buttons from {message_id}: {exc})")


def answer_callback(callback_id: str, text: str = "") -> None:
    """Stop the button's loading spinner. Fails harmlessly if already answered."""
    try:
        api("answerCallbackQuery", {"callback_query_id": callback_id, "text": text[:190]})
    except TelegramError as exc:
        print(f"(callback already answered or expired: {exc})")


def get_updates(offset: int, timeout: int = 0) -> list:
    """timeout > 0 long-polls: Telegram holds the request until something arrives."""
    return api("getUpdates", {
        "offset": offset,
        "timeout": timeout,
        "allowed_updates": ["message", "callback_query"],
    }, timeout=timeout + 15)


def get_webhook_url() -> str:
    info = api("getWebhookInfo")
    return (info or {}).get("url") or ""


def describe_message(message: dict) -> str:
    """One readable summary of any incoming message, including non-text ones."""
    if message.get("text"):
        return message["text"]

    caption = message.get("caption")
    suffix = f"\n\n“{caption}”" if caption else ""
    kinds = [
        ("photo", "📷 a photo"),
        ("video", "🎬 a video"),
        ("video_note", "🎥 a video message"),
        ("voice", "🎤 a voice message"),
        ("audio", "🎵 an audio file"),
        ("document", "📎 a file"),
        ("sticker", "a sticker"),
        ("animation", "a GIF"),
        ("location", "📍 a location"),
        ("contact", "👤 a contact"),
        ("poll", "📊 a poll"),
    ]
    for key, label in kinds:
        if key in message:
            if key == "sticker":
                emoji = (message["sticker"] or {}).get("emoji") or ""
                label = f"{emoji} a sticker".strip()
            if key == "voice":
                secs = (message["voice"] or {}).get("duration")
                label += f" ({secs}s)" if secs else ""
            return f"[sent {label}]{suffix}"
    return "[sent something the bot can't display]" + suffix
