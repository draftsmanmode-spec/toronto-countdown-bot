"""
Telegram webhook -> GitHub, in under a second.

Telegram POSTs every message and button tap here. This function:
  1. checks the secret header (derived from BOT_TOKEN, same as webhook_admin.py)
  2. answers a button tap immediately, so the spinner stops and you see
     "Sending…" right away
  3. forwards the update to GitHub as a repository_dispatch event; the
     "Quote bot" workflow does the real work there, where the state lives

If GitHub can't be reached (most likely an expired GH_TOKEN), you get a
Telegram message saying so instead of silence.

Vercel environment variables:
  BOT_TOKEN       same value as the GitHub secret
  GH_TOKEN        fine-grained GitHub token: this repo only, Contents read/write
  ADMIN_CHAT_ID   same value as the GitHub secret (used for failure alerts)
  GH_REPO         optional, defaults to draftsmanmode-spec/toronto-countdown-bot

GET returns a small health check (no secrets).
Standard library only, so there's nothing to install.
"""

import hashlib
import json
import os
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
GH_TOKEN = os.environ.get("GH_TOKEN", "")
GH_REPO = os.environ.get("GH_REPO") or "draftsmanmode-spec/toronto-countdown-bot"
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID", "")

TOASTS = {
    "ok": "✅ Sending to your brother…",
    "skip": "⏭ Skipping today…",
    "ban": "🚫 Banning it…",
    "next": "🔄 Finding another…",
    "unban": "↩️ Undoing…",
}


def webhook_secret() -> str:
    return hashlib.sha256(f"tg-webhook:{BOT_TOKEN}".encode()).hexdigest()[:48] if BOT_TOKEN else ""


def post_json(url: str, payload: dict, headers: dict | None = None, timeout: int = 8):
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", **(headers or {})},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode(errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode(errors="replace")
    except Exception as exc:  # noqa: BLE001 - network trouble is reported, not raised
        return 0, str(exc)


def telegram(method: str, payload: dict):
    return post_json(f"https://api.telegram.org/bot{BOT_TOKEN}/{method}", payload)


def dispatch(event_type: str, client_payload: dict):
    if not GH_TOKEN:
        return False, "GH_TOKEN is not set in Vercel"
    status, body = post_json(
        f"https://api.github.com/repos/{GH_REPO}/dispatches",
        {"event_type": event_type, "client_payload": client_payload},
        {
            "Authorization": f"Bearer {GH_TOKEN}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "quote-relay",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    if status == 204:
        return True, "ok"
    return False, f"GitHub said {status}: {body[:120]}"


def alert(text: str) -> None:
    if ADMIN_CHAT_ID and BOT_TOKEN:
        telegram("sendMessage", {"chat_id": ADMIN_CHAT_ID, "text": text})


class handler(BaseHTTPRequestHandler):
    def _reply(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._reply(200, {
            "ok": bool(BOT_TOKEN and GH_TOKEN),
            "bot_token_set": bool(BOT_TOKEN),
            "gh_token_set": bool(GH_TOKEN),
            "admin_chat_set": bool(ADMIN_CHAT_ID),
            "repo": GH_REPO,
        })

    def do_POST(self):
        if not BOT_TOKEN:
            return self._reply(503, {"ok": False, "error": "BOT_TOKEN not configured"})
        if self.headers.get("X-Telegram-Bot-Api-Secret-Token", "") != webhook_secret():
            return self._reply(401, {"ok": False})

        try:
            length = int(self.headers.get("Content-Length") or 0)
            update = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            return self._reply(200, {"ok": True, "ignored": "bad json"})

        cq = update.get("callback_query")
        if cq:
            action = (cq.get("data") or "").split("|")[0]
            telegram("answerCallbackQuery", {
                "callback_query_id": cq.get("id"),
                "text": TOASTS.get(action, "⏳ On it…"),
            })

        text = ((update.get("message") or {}).get("text") or "")
        # button taps and commands touch shared state, so GitHub runs them one
        # at a time; plain relays don't, so they run in parallel
        event = "tg_state" if (cq or text.startswith("/")) else "tg_relay"
        ok, detail = dispatch(event, {"update": update})
        if not ok:
            alert(
                f"⚠️ The bot couldn't reach GitHub ({detail}), so that "
                f"{'tap' if cq else 'message'} wasn't processed.\n"
                "If it says 401, the GitHub token in Vercel has expired: make a new one "
                "and paste it into Vercel → quote-relay → Settings → Environment Variables → GH_TOKEN."
            )
        # always 200: a retry storm from Telegram wouldn't fix a GitHub problem
        return self._reply(200, {"ok": ok})
