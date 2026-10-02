"""GitHub-only mode: ticks pull waiting taps, and listen after sending a card."""

import json

import bot_brain
from bot_brain import Brain, drain, run_tick
from conftest import ADMIN, BROTHER, at


def brain(tg, hour=8):
    return Brain(tg=tg, admin=ADMIN, customer=BROTHER, enrich=None, now=at("2026-10-02", hour))


def tap_update(update_id, card, action):
    data = next(b["callback_data"] for row in card["markup"]["inline_keyboard"]
                for b in row if b["callback_data"].startswith(action + "|"))
    return {"update_id": update_id, "callback_query": {
        "id": f"cq{update_id}", "data": data,
        "message": {"message_id": card["message_id"], "chat": {"id": int(ADMIN)}, "text": card["text"]}}}


def test_webhook_mode_skips_polling(repo, tg):
    tg.webhook = "https://quote-relay.example/api/telegram"
    assert drain(brain(tg)) == -1
    assert getattr(tg, "polls", []) == []


def test_tick_listens_and_stops_once_sent(repo, tg, monkeypatch):
    monkeypatch.setattr(bot_brain, "LISTEN_SECONDS", 60)
    b = brain(tg)

    # the card goes out on the tick; the "user" taps ✅ during the listen window
    def updates(offset, timeout=0):
        tg.polls = getattr(tg, "polls", []) + [(offset, timeout)]
        cards = tg.cards()
        if cards and not tg.to(BROTHER) and offset <= 50:
            return [tap_update(50, cards[-1], "ok")]
        return []

    tg.get_updates = updates
    run_tick(b)
    assert b.finish()
    assert len(tg.to(BROTHER)) == 1, "tap during the listen window should send at once"
    assert any(t > 0 for _, t in tg.polls), "should have long-polled"
    assert json.loads((repo / "state.json").read_text())["last_update_id"] == 51


def test_waiting_taps_are_processed_before_the_tick(repo, tg, monkeypatch):
    monkeypatch.setattr(bot_brain, "LISTEN_SECONDS", 0)
    b = brain(tg)
    run_tick(b)            # card offered; no taps yet
    b.finish()
    card = tg.cards()[-1]
    tg.batches = [[tap_update(7, card, "skip")]]
    b2 = brain(tg, hour=18)
    run_tick(b2)           # the skip is applied first, so no 6pm reminder follows
    b2.finish()
    assert not any("Still waiting" in m["text"] for m in tg.sent)
    state = json.loads((repo / "approval_state.json").read_text())
    assert state["days"]["2026-10-02"]["status"] == "skipped"


def test_listen_window_ends_without_a_tap(repo, tg, monkeypatch):
    monkeypatch.setattr(bot_brain, "LISTEN_SECONDS", 0)
    b = brain(tg)
    run_tick(b)
    assert b.finish()
    assert tg.to(BROTHER) == []
