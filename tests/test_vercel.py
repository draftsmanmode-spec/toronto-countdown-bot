"""Runs the Vercel handlers on a local HTTP server with GitHub/Telegram calls faked."""

import importlib.util
import json
import threading
import urllib.error
import urllib.request
from http.server import HTTPServer
from pathlib import Path

import pytest

VERCEL = Path(__file__).resolve().parent.parent / "vercel" / "api"


def load(name, monkeypatch, **env):
    for key in ("BOT_TOKEN", "GH_TOKEN", "ADMIN_CHAT_ID", "CRON_SECRET", "GH_REPO"):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    spec = importlib.util.spec_from_file_location(f"vercel_{name}", VERCEL / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    calls = []

    def fake_post(url, payload, headers=None, timeout=8):
        calls.append((url, payload))
        if "api.github.com" in url:
            return mod.FAKE_GH_STATUS, ""
        return 200, "{}"

    mod.FAKE_GH_STATUS = 204
    monkeypatch.setattr(mod, "post_json", fake_post)
    return mod, calls


@pytest.fixture
def serve():
    servers = []

    def start(mod):
        srv = HTTPServer(("127.0.0.1", 0), mod.handler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        servers.append(srv)
        return f"http://127.0.0.1:{srv.server_port}"

    yield start
    for s in servers:
        s.shutdown()


def request(url, body=None, headers=None, method=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"{}")


TAP = {"update_id": 9, "callback_query": {"id": "cq", "data": "ok|q-1234567890|20261002",
                                          "message": {"message_id": 1, "chat": {"id": 111}}}}


def test_webhook_rejects_wrong_secret(monkeypatch, serve):
    mod, calls = load("telegram", monkeypatch, BOT_TOKEN="123:abc", GH_TOKEN="gh")
    base = serve(mod)
    status, _ = request(base, TAP, {"X-Telegram-Bot-Api-Secret-Token": "nope"})
    assert status == 401 and calls == []


def test_webhook_answers_tap_and_dispatches(monkeypatch, serve):
    mod, calls = load("telegram", monkeypatch, BOT_TOKEN="123:abc", GH_TOKEN="gh", ADMIN_CHAT_ID="111")
    base = serve(mod)
    status, body = request(base, TAP, {"X-Telegram-Bot-Api-Secret-Token": mod.webhook_secret()})
    assert status == 200 and body["ok"] is True
    assert "answerCallbackQuery" in calls[0][0] and "Sending" in calls[0][1]["text"]
    assert calls[1][0].endswith("/dispatches")
    assert calls[1][1]["event_type"] == "tg_state"
    assert calls[1][1]["client_payload"]["update"]["update_id"] == 9


def test_plain_message_is_a_parallel_relay(monkeypatch, serve):
    mod, calls = load("telegram", monkeypatch, BOT_TOKEN="123:abc", GH_TOKEN="gh")
    base = serve(mod)
    update = {"update_id": 3, "message": {"chat": {"id": 222}, "text": "hey"}}
    request(base, update, {"X-Telegram-Bot-Api-Secret-Token": mod.webhook_secret()})
    assert calls[0][1]["event_type"] == "tg_relay"


def test_github_failure_alerts_admin(monkeypatch, serve):
    mod, calls = load("telegram", monkeypatch, BOT_TOKEN="123:abc", GH_TOKEN="gh", ADMIN_CHAT_ID="111")
    mod.FAKE_GH_STATUS = 401
    base = serve(mod)
    status, body = request(base, TAP, {"X-Telegram-Bot-Api-Secret-Token": mod.webhook_secret()})
    assert status == 200 and body["ok"] is False
    alert = calls[-1]
    assert "sendMessage" in alert[0] and "401" in alert[1]["text"]


def test_webhook_secret_matches_github_side(monkeypatch):
    mod, _ = load("telegram", monkeypatch, BOT_TOKEN="123:abc")
    import webhook_admin
    assert mod.webhook_secret() == webhook_admin.webhook_secret("123:abc")


def test_health_check_reveals_no_secrets(monkeypatch, serve):
    mod, _ = load("telegram", monkeypatch, BOT_TOKEN="123:abc")
    status, body = request(serve(mod))
    assert status == 200 and body["bot_token_set"] is True and body["gh_token_set"] is False
    assert "123:abc" not in json.dumps(body)


def test_tick_requires_cron_secret(monkeypatch, serve):
    mod, calls = load("tick", monkeypatch, GH_TOKEN="gh", CRON_SECRET="s3")
    base = serve(mod)
    assert request(base)[0] == 401
    status, _ = request(base, headers={"Authorization": "Bearer s3"})
    assert status == 200
    assert calls[0][1]["event_type"] == "daily_tick"
