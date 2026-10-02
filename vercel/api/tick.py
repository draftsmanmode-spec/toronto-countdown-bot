"""
Vercel cron -> GitHub "daily_tick" (see vercel.json for the times).

Fires twice a day: about 8am Toronto (morning card) and about 6pm
(reminder if you haven't tapped anything). GitHub decides which one is due
from the local time and today's state, so the same tick is safe to run
twice. That's why the GitHub fallback cron in quote.yml can't double-send.

Vercel sends `Authorization: Bearer $CRON_SECRET` on cron calls; anything
else is rejected.

Vercel environment variables: GH_TOKEN, CRON_SECRET, plus BOT_TOKEN and
ADMIN_CHAT_ID for failure alerts. GH_REPO optional.
"""

import json
import os
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler

GH_TOKEN = os.environ.get("GH_TOKEN", "")
GH_REPO = os.environ.get("GH_REPO") or "draftsmanmode-spec/toronto-countdown-bot"
CRON_SECRET = os.environ.get("CRON_SECRET", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID", "")


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
    except Exception as exc:  # noqa: BLE001
        return 0, str(exc)


class handler(BaseHTTPRequestHandler):
    def _reply(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not CRON_SECRET or self.headers.get("Authorization", "") != f"Bearer {CRON_SECRET}":
            return self._reply(401, {"ok": False})
        if not GH_TOKEN:
            return self._reply(503, {"ok": False, "error": "GH_TOKEN not configured"})

        status, body = post_json(
            f"https://api.github.com/repos/{GH_REPO}/dispatches",
            {"event_type": "daily_tick", "client_payload": {"source": "vercel-cron"}},
            {
                "Authorization": f"Bearer {GH_TOKEN}",
                "Accept": "application/vnd.github+json",
                "User-Agent": "quote-relay",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        if status == 204:
            return self._reply(200, {"ok": True})

        if BOT_TOKEN and ADMIN_CHAT_ID:
            post_json(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", {
                "chat_id": ADMIN_CHAT_ID,
                "text": (f"⚠️ Daily quote tick couldn't reach GitHub ({status}). The GitHub "
                         "backup schedule will still run, just a few hours late. If this says "
                         "401, renew GH_TOKEN in Vercel."),
            })
        return self._reply(502, {"ok": False, "status": status})
