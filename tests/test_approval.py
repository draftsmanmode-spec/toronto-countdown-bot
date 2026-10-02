import json
import random

import approval
from conftest import ADMIN, BROTHER, at, tap


def engine(tg, now, enrich=None, seed=7):
    return approval.Engine(tg, ADMIN, BROTHER, enrich=enrich, now=now, rng=random.Random(seed))


def run_day(tg, day, hour=8, enrich=None, seed=7):
    """Morning tick on `day`, saved. Returns (engine, card)."""
    e = engine(tg, at(day, hour), enrich, seed)
    e.tick()
    e.save()
    return e, tg.cards()[-1]


def tap_and_save(tg, day, card, action, hour=9, seed=7):
    e = engine(tg, at(day, hour), seed=seed)
    result = e.handle_callback(tap(card, action))
    e.save()
    return e, result


# ---------- picking rules ----------

def test_old_themes_count_as_sent_lately(repo, tg):
    e = engine(tg, at("2026-10-02", 8))
    themes = [i for i in e.pool.values() if i["kind"] == "theme"]
    assert len(themes) == 13
    # every theme went out in the last six weeks, so none may be offered
    assert all(e.state["items"][t["id"]]["sent"] for t in themes)
    ready = approval.eligible(e.pool, e.state, e.today)
    assert ready and not any(i["kind"] == "theme" for i in ready)


def test_pool_has_no_duplicate_quotes(repo, tg):
    e = engine(tg, at("2026-10-02", 8))
    texts = [approval.norm_text(q["text"]) for i in e.pool.values() for q in i["quotes"]]
    assert len(texts) == len(set(texts))


def test_thirty_approved_days_never_repeat(repo, tg):
    sent = []
    for n in range(30):
        day = f"2026-10-{n + 2:02d}" if n < 30 else None
        _, card = run_day(tg, day, seed=n)
        _, result = tap_and_save(tg, day, card, "ok", seed=n)
        assert result == "sent"
        state = json.loads((repo / "approval_state.json").read_text())
        sent.append(state["days"][day]["sent_id"])
    assert len(sent) == len(set(sent)), "an item was sent twice within 30 days"
    assert len(tg.to(BROTHER)) == 30


def test_banned_item_is_never_offered_again(repo, tg):
    _, card = run_day(tg, "2026-10-02")
    banned_id = card["markup"]["inline_keyboard"][0][0]["callback_data"].split("|")[1]
    tap_and_save(tg, "2026-10-02", card, "ban")
    e = engine(tg, at("2026-10-03", 8))
    for _ in range(50):
        item, _ = approval.pick(e.pool, e.state, e.today, rng=random.Random(_))
        assert item["id"] != banned_id


def test_skipped_item_rests_before_coming_back(repo, tg):
    _, card = run_day(tg, "2026-10-02")
    item_id = card["markup"]["inline_keyboard"][0][0]["callback_data"].split("|")[1]
    tap_and_save(tg, "2026-10-02", card, "skip")
    e = engine(tg, at("2026-10-04", 8))
    assert item_id not in {i["id"] for i in approval.eligible(e.pool, e.state, e.today)}
    e = engine(tg, at("2026-10-08", 8))
    assert item_id in {i["id"] for i in approval.eligible(e.pool, e.state, e.today)}


def test_fresh_article_is_preferred_then_alternates(repo, tg):
    (repo / "articles.json").write_text(json.dumps({"items": [{
        "id": "a-0000000001", "url": "https://fs.blog/x", "title": "On Patience",
        "source": "Farnam Street", "published": "2026-09-30", "fetched": "2026-10-01",
        "subject": "Patience", "subject_uk": "Терпіння",
        "quotes": [{"text": "Patience is the art of letting compounding do its quiet work.",
                    "text_uk": "Терпіння — це мистецтво дати складним відсоткам тихо працювати.",
                    "author": "Shane Parrish"}],
        "analysis_en": "Two sentences.", "analysis_uk": "Два речення.",
    }]}))
    _, card = run_day(tg, "2026-10-02")
    assert "Fresh article · Farnam Street" in card["text"]
    assert "🔗 https://fs.blog/x" in card["text"]
    tap_and_save(tg, "2026-10-02", card, "ok")
    # the day after an article goes out, the timeless library gets its turn
    _, card2 = run_day(tg, "2026-10-03")
    assert "Timeless" in card2["text"]


# ---------- the card ----------

def test_card_shows_history_and_buttons(repo, tg):
    _, card = run_day(tg, "2026-10-02")
    assert "Today's pick · Fri, Oct 2" in card["text"]
    assert "First time offered" in card["text"]
    labels = [b["text"] for row in card["markup"]["inline_keyboard"] for b in row]
    assert labels == ["✅ Send today", "⏭ Not today", "🚫 Never send", "🔄 Another"]
    for row in card["markup"]["inline_keyboard"]:
        for b in row:
            assert len(b["callback_data"].encode()) <= 64


def test_offer_count_is_shown_when_offered_again(repo, tg):
    _, card = run_day(tg, "2026-10-02")
    item_id = card["markup"]["inline_keyboard"][0][0]["callback_data"].split("|")[1]
    tap_and_save(tg, "2026-10-02", card, "skip")
    e = engine(tg, at("2026-10-10", 8))
    line = approval.history_line(e.state, item_id)
    assert line.startswith("🔁 Offered 1× before (last Oct 2)")
    assert "Never sent" in line


def test_brother_message_formats(repo, tg):
    e = engine(tg, at("2026-10-02", 8))
    timeless = next(i for i in e.pool.values() if i["kind"] == "timeless")
    text = approval.brother_message(timeless)
    assert text.startswith("💭 Today's quote")
    assert "Цитата дня" in text and "📝" not in text
    theme = next(i for i in e.pool.values() if i["kind"] == "theme")
    text = approval.brother_message(theme)
    assert f"Today's theme: {theme['subject']}" in text and "📝" in text


# ---------- the daily tick ----------

def test_tick_offers_once_then_reminds_once(repo, tg):
    assert engine(tg, at("2026-10-02", 5)).tick() == "too early for today's card"
    run_day(tg, "2026-10-02", hour=8)
    e = engine(tg, at("2026-10-02", 12))
    assert e.tick().startswith("nothing to do")
    e.save()
    e = engine(tg, at("2026-10-02", 18))
    assert e.tick() == "reminded"
    e.save()
    reminder = tg.sent[-1]
    assert "Still waiting" in reminder["text"]
    assert reminder["reply_to"] == tg.cards()[0]["message_id"]
    assert engine(tg, at("2026-10-02", 19)).tick().startswith("nothing to do")
    assert len(tg.cards()) == 1


def test_no_reminder_after_a_decision(repo, tg):
    _, card = run_day(tg, "2026-10-02")
    tap_and_save(tg, "2026-10-02", card, "skip")
    assert engine(tg, at("2026-10-02", 18)).tick() == "nothing to do (today: skipped)"


def test_unanswered_day_expires_and_is_mentioned(repo, tg):
    _, card = run_day(tg, "2026-10-02")
    e, card2 = run_day(tg, "2026-10-03")
    assert card["message_id"] in tg.removed
    assert "Yesterday: no answer" in card2["text"]
    assert e.state["days"]["2026-10-02"]["status"] == "expired"
    assert tg.to(BROTHER) == []


def test_local_date_not_utc(repo, tg):
    # 11:30pm in Toronto is already the next day in UTC; it must still be "today"
    _, card = run_day(tg, "2026-10-02")
    e, result = tap_and_save(tg, "2026-10-02", card, "ok", hour=23)
    assert result == "sent"


# ---------- buttons ----------

def test_send_today_reaches_brother_and_website(repo, tg):
    _, card = run_day(tg, "2026-10-02")
    e, result = tap_and_save(tg, "2026-10-02", card, "ok")
    assert result == "sent" and e.sent_today
    assert len(tg.to(BROTHER)) == 1
    assert "✅ Sent to your brother" in tg.edits[-1]["text"]
    assert tg.edits[-1]["markup"] is None
    history = json.loads((repo / "quote_state.json").read_text())["history"]
    assert history[-1]["date"] == "2026-10-02" and history[-1]["id"]

    import update_site
    update_site.main()
    first_quote = history[-1]["quotes"][0]["text"]
    import html
    assert html.escape(first_quote) in (repo / "docs" / "index.html").read_text()


def test_double_tap_never_sends_twice(repo, tg):
    _, card = run_day(tg, "2026-10-02")
    tap_and_save(tg, "2026-10-02", card, "ok")
    _, result = tap_and_save(tg, "2026-10-02", card, "ok")
    assert result == "already sent"
    assert len(tg.to(BROTHER)) == 1


def test_not_today_sends_nothing(repo, tg):
    _, card = run_day(tg, "2026-10-02")
    e, result = tap_and_save(tg, "2026-10-02", card, "skip")
    assert result == "skipped" and tg.to(BROTHER) == []
    assert "Not today" in tg.edits[-1]["text"]
    _, result = tap_and_save(tg, "2026-10-02", card, "ok")
    assert result == "day is skipped"
    assert tg.to(BROTHER) == []


def test_another_swaps_and_old_card_goes_stale(repo, tg):
    _, card = run_day(tg, "2026-10-02")
    _, result = tap_and_save(tg, "2026-10-02", card, "next")
    assert result == "offered another"
    card2 = tg.cards()[-1]
    assert card2["message_id"] != card["message_id"]
    assert card2["text"].split("━")[-1] != card["text"].split("━")[-1]
    _, result = tap_and_save(tg, "2026-10-02", card, "ok")
    assert result == "stale card" and tg.to(BROTHER) == []
    _, result = tap_and_save(tg, "2026-10-02", card2, "ok")
    assert result == "sent"


def test_ban_offers_replacement_and_undo_restores(repo, tg):
    _, card = run_day(tg, "2026-10-02")
    item_id = card["markup"]["inline_keyboard"][0][0]["callback_data"].split("|")[1]
    e, result = tap_and_save(tg, "2026-10-02", card, "ban")
    assert result == "banned + offered another"
    assert e.state["items"][item_id]["never"] is True
    banned_edit = tg.edits[-1]
    assert "Never again" in banned_edit["text"]
    undo = {"message_id": card["message_id"], "text": banned_edit["text"],
            "markup": banned_edit["markup"]}
    e, result = tap_and_save(tg, "2026-10-02", undo, "unban")
    assert result == "unbanned" and e.state["items"][item_id]["never"] is False
    assert "Never again" not in tg.edits[-1]["text"]


def test_yesterdays_card_has_expired(repo, tg):
    _, card = run_day(tg, "2026-10-02")
    _, result = tap_and_save(tg, "2026-10-03", card, "ok")
    assert result == "expired card" and tg.to(BROTHER) == []


def test_buttons_only_work_for_admin(repo, tg):
    _, card = run_day(tg, "2026-10-02")
    e = engine(tg, at("2026-10-02", 9))
    assert e.handle_callback(tap(card, "ok", chat=BROTHER)).startswith("ignored")
    assert tg.to(BROTHER) == []


# ---------- /today ----------

def test_today_reopens_a_skipped_day(repo, tg):
    _, card = run_day(tg, "2026-10-02")
    tap_and_save(tg, "2026-10-02", card, "skip")
    e = engine(tg, at("2026-10-02", 14))
    assert e.reopen_today() == "offered"
    e.save()
    assert "Reopened today" in tg.cards()[-1]["text"]
    _, result = tap_and_save(tg, "2026-10-02", tg.cards()[-1], "ok")
    assert result == "sent"


def test_today_reposts_open_card_without_counting_an_offer(repo, tg):
    _, card = run_day(tg, "2026-10-02")
    item_id = card["markup"]["inline_keyboard"][0][0]["callback_data"].split("|")[1]
    e = engine(tg, at("2026-10-02", 10))
    assert e.reopen_today() == "re-posted"
    assert e.state["items"][item_id]["offered"] == ["2026-10-02"]
    assert card["message_id"] in tg.removed


# ---------- enrichment ----------

def test_bare_quote_gets_enriched_once_and_cached(repo, tg):
    calls = []

    def fake_enrich(item):
        calls.append(item["id"])
        return {"subject": "Inner Calm", "subject_uk": "Внутрішній спокій",
                "analysis_en": "Two plain sentences.", "analysis_uk": "Два прості речення."}

    e, card = run_day(tg, "2026-10-02", enrich=fake_enrich)
    assert calls and "Today's theme: Inner Calm" in card["text"]
    assert calls[0] in e.state["enriched"]
    e2 = engine(tg, at("2026-10-02", 9))
    assert e2.pool[calls[0]]["subject"] == "Inner Calm"


def test_enrichment_failure_still_offers(repo, tg):
    def broken(item):
        raise RuntimeError("groq down")

    _, card = run_day(tg, "2026-10-02", enrich=broken)
    assert "Today's quote" in card["text"]


def test_stats_count_sends_from_before_approvals(repo, tg):
    e = engine(tg, at("2026-10-02", 8))
    text = e.stats_text()
    assert "Library: 13 themes · 119 timeless quotes" in text
    sent_line = next(l for l in text.splitlines() if l.startswith("Sent in the last 30 days"))
    assert int(sent_line.split(": ")[1]) >= 25


def test_no_reminder_late_at_night(repo, tg):
    run_day(tg, "2026-10-02")
    assert engine(tg, at("2026-10-02", 23)).tick().startswith("nothing to do")
