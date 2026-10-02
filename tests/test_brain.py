from bot_brain import Brain
from conftest import ADMIN, BROTHER, at


def brain(tg, hour=9):
    return Brain(tg=tg, admin=ADMIN, customer=BROTHER, enrich=None, now=at("2026-10-02", hour))


def msg(chat, text=None, **extra):
    m = {"message_id": 5, "chat": {"id": int(chat)}, **extra}
    if text is not None:
        m["text"] = text
    return {"update_id": 1, "message": m}


def test_brother_message_is_reported(repo, tg):
    assert brain(tg).handle_update(msg(BROTHER, "привіт")) == "reported brother's message"
    assert "Your brother messaged the bot" in tg.to(ADMIN)[0]["text"]
    assert "привіт" in tg.to(ADMIN)[0]["text"]


def test_brother_photo_is_described(repo, tg):
    brain(tg).handle_update(msg(BROTHER, photo=[{}], caption="look"))
    assert "a photo" in tg.to(ADMIN)[0]["text"] and "look" in tg.to(ADMIN)[0]["text"]


def test_admin_text_is_relayed_with_report(repo, tg):
    assert brain(tg).handle_update(msg(ADMIN, "Call mom today")) == "relayed"
    assert tg.to(BROTHER)[0]["text"] == "Call mom today"
    assert tg.to(ADMIN)[0]["text"].startswith("✅ Delivered")


def test_failed_relay_is_reported(repo, tg):
    def boom(chat_id, text, **kw):
        if str(chat_id) == BROTHER:
            raise RuntimeError("chat not found")
        return tg.__class__.send_text(tg, chat_id, text, **kw)

    tg.send_text = boom
    assert brain(tg).handle_update(msg(ADMIN, "hi")) == "relay failed"
    assert "NOT delivered" in tg.sent[-1]["text"]


def test_strangers_are_ignored(repo, tg):
    assert brain(tg).handle_update(msg("999", "spam")).startswith("ignored")
    assert tg.sent == []


def test_commands(repo, tg):
    b = brain(tg)
    assert b.handle_update(msg(ADMIN, "/help")) == "sent help"
    assert b.handle_update(msg(ADMIN, "/stats")) == "sent stats"
    assert "Quote pool" in tg.sent[-1]["text"]
    assert b.handle_update(msg(ADMIN, "/schedule")) == "sent schedule"
    assert "HABITS" in tg.sent[-1]["text"]
    assert b.handle_update(msg(ADMIN, "/nope")) == "unknown command nope"
    assert b.handle_update(msg(ADMIN, "/today")) == "today: offered"
    assert tg.to(BROTHER) == []
    assert b.finish()


def test_tap_through_brain_sends_and_updates_site(repo, tg):
    b = brain(tg, hour=8)
    b.tick()
    assert b.finish()
    card = tg.cards()[-1]
    data = card["markup"]["inline_keyboard"][0][0]["callback_data"]
    b2 = brain(tg, hour=9)
    result = b2.handle_update({"update_id": 2, "callback_query": {
        "id": "x", "data": data,
        "message": {"message_id": card["message_id"], "chat": {"id": int(ADMIN)}, "text": card["text"]},
    }})
    assert result == "sent"
    assert b2.finish()
    assert len(tg.to(BROTHER)) == 1


def test_relay_does_not_touch_state(repo, tg):
    b = brain(tg)
    b.handle_update(msg(ADMIN, "hello"))
    assert b.finish()
    assert not (repo / "approval_state.json").exists()


def test_forwarded_updates_need_the_right_secret(repo, tg, monkeypatch):
    import bot_brain
    from webhook_admin import webhook_secret
    monkeypatch.setenv("BOT_TOKEN", "123:abc")
    update = {"update_id": 4, "message": {"chat": {"id": int(ADMIN)}, "text": "hi"}}
    assert bot_brain.dispatched_update({"update": update, "secret": "forged"}) is None
    assert bot_brain.dispatched_update({"update": update}) is None
    good = {"update": update, "secret": webhook_secret("123:abc")}
    assert bot_brain.dispatched_update(good) == update


def test_ping_reports_the_mode(repo, tg):
    b = brain(tg)
    b.via_webhook = True
    assert b.handle_update(msg(ADMIN, "/ping")) == "pong"
    assert "instant mode" in tg.sent[-1]["text"]
