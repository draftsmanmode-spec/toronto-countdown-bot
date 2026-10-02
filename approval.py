"""
Daily approval flow: nothing reaches your brother until you say so.

Every morning you (ADMIN_CHAT_ID) get ONE candidate with four buttons:

    ✅ Send today   - it goes to your brother right now, and onto the website
    ⏭ Not today    - nothing is sent today; the item rests and may come back
    🚫 Never send   - banned for good (with an undo), and another one is offered
    🔄 Another      - swap it for a different candidate right now

Each card says where the item came from, how many times it has been offered
before and when it was last sent. Anything sent in the last 90 days is never
offered, and anything you passed on rests for a few days first.

At 6pm (Toronto) you get one reminder if you haven't tapped anything. If you
still don't approve, nothing goes out that day.

The pool is built from three files:
    quotes.json                 themed entries (subject + 1-2 quotes + analysis)
    quotes_flat_pending.json    single timeless quotes
    articles.json               fresh lines pulled from articles (articles.py)

State lives in approval_state.json (committed back by the workflow).
quote_state.json keeps the sent history the website renders.

Every item gets a stable id from its content, so editing the order of the
JSON files never mixes up which item was sent or banned.
"""

import hashlib
import json
import os
import random
import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

TZ = ZoneInfo(os.environ.get("BOT_TZ") or "America/Toronto")

QUOTES_PATH = "quotes.json"
TIMELESS_PATH = "quotes_flat_pending.json"
ARTICLES_PATH = "articles.json"
STATE_PATH = "approval_state.json"
HISTORY_PATH = "quote_state.json"

RECENT_SENT_DAYS = 90      # never offer anything sent this recently
OFFER_COOLDOWN_DAYS = 5    # something you passed on rests this long
FRESH_ARTICLE_DAYS = 14    # an article counts as "latest" for this long
LOW_POOL_WARNING = 14      # warn when fewer than this many items are ready
MORNING_HOUR = 6           # local hour from which the daily card may go out
REMINDER_HOUR = 17         # local hour from which the reminder may go out
REMINDER_LATEST_HOUR = 22  # ...and until which (a late backup tick shouldn't nag at midnight)
KEEP_DAYS = 60             # day records older than this are pruned

# progressively looser rules, only used if the strict ones leave nothing
RELAX_LEVELS = [
    (RECENT_SENT_DAYS, OFFER_COOLDOWN_DAYS),
    (RECENT_SENT_DAYS, 0),
    (30, 0),
    (7, 0),
]

ACTIONS = ("ok", "skip", "ban", "next", "unban")


# ---------- small helpers ----------

def now_local() -> datetime:
    return datetime.now(TZ)


def load_json(path, default):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def norm_text(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"[“”«»\"'’‘`]", "", s)
    s = re.sub(r"[^\w\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def short_hash(s: str) -> str:
    return hashlib.sha1(norm_text(s).encode("utf-8")).hexdigest()[:10]


def fmt_day(d: date) -> str:
    return f"{d.strftime('%b')} {d.day}"


def parse_day(s: str):
    try:
        return date.fromisoformat(s)
    except (TypeError, ValueError):
        return None


# ---------- the pool ----------

def _quote(q: dict) -> dict:
    return {
        "text": (q.get("text") or "").strip(),
        "text_uk": (q.get("text_uk") or "").strip(),
        "author": (q.get("author") or "").strip(),
    }


def build_pool(enriched: dict | None = None) -> dict:
    """{id: item}. Items share one shape so rendering never needs to care."""
    enriched = enriched or {}
    pool = {}
    theme_texts = set()

    for entry in load_json(QUOTES_PATH, []):
        subject = entry.get("subject") or ""
        quotes = [_quote(q) for q in entry.get("quotes") or [] if q.get("text")]
        if not subject and not quotes:
            continue
        item_id = "t-" + short_hash(subject or quotes[0]["text"])
        theme_texts.update(norm_text(q["text"]) for q in quotes)
        pool[item_id] = {
            "id": item_id,
            "kind": "theme",
            "subject": subject,
            "subject_uk": entry.get("subject_uk") or "",
            "quotes": quotes,
            "analysis_en": entry.get("analysis_en") or "",
            "analysis_uk": entry.get("analysis_uk") or "",
        }

    for entry in load_json(TIMELESS_PATH, []):
        q = _quote(entry)
        if not q["text"] or norm_text(q["text"]) in theme_texts:
            continue
        item_id = "q-" + short_hash(q["text"])
        if item_id in pool:
            continue
        item = {
            "id": item_id,
            "kind": "timeless",
            "subject": "",
            "subject_uk": "",
            "quotes": [q],
            "analysis_en": "",
            "analysis_uk": "",
        }
        extra = enriched.get(item_id) or {}
        for key in ("subject", "subject_uk", "analysis_en", "analysis_uk"):
            if extra.get(key):
                item[key] = extra[key]
        pool[item_id] = item

    for entry in load_json(ARTICLES_PATH, {}).get("items", []):
        if not entry.get("id") or not entry.get("quotes"):
            continue
        pool[entry["id"]] = {
            "id": entry["id"],
            "kind": "article",
            "subject": entry.get("subject") or "",
            "subject_uk": entry.get("subject_uk") or "",
            "quotes": [_quote(q) for q in entry["quotes"]],
            "analysis_en": entry.get("analysis_en") or "",
            "analysis_uk": entry.get("analysis_uk") or "",
            "source": entry.get("source") or "",
            "title": entry.get("title") or "",
            "url": entry.get("url") or "",
            "published": entry.get("published") or entry.get("fetched") or "",
        }

    return pool


def label(item: dict) -> str:
    if item.get("subject"):
        return item["subject"]
    q = (item.get("quotes") or [{}])[0]
    text = q.get("text") or "(empty)"
    text = text if len(text) <= 70 else text[:67].rstrip() + "…"
    return f"“{text}”" + (f" — {q['author']}" if q.get("author") else "")


def is_fresh_article(item: dict, today: date) -> bool:
    if item.get("kind") != "article":
        return False
    published = parse_day((item.get("published") or "")[:10])
    return published is not None and (today - published).days <= FRESH_ARTICLE_DAYS


# ---------- state ----------

def load_state() -> dict:
    state = load_json(STATE_PATH, {})
    state.setdefault("items", {})
    state.setdefault("days", {})
    state.setdefault("enriched", {})
    return state


def save_state(state: dict) -> None:
    save_json(STATE_PATH, state)


def item_stats(state: dict, item_id: str) -> dict:
    st = state["items"].setdefault(item_id, {})
    st.setdefault("offered", [])
    st.setdefault("sent", [])
    st.setdefault("never", False)
    return st


def seed_from_history(state: dict, pool: dict) -> int:
    """
    Teach the state about everything sent before approvals existed, so old
    themes count as "sent lately". Matches by subject or quote text. Safe to
    run repeatedly; it only ever adds missing dates.
    """
    by_subject = {norm_text(i["subject"]): i["id"] for i in pool.values() if i.get("subject")}
    by_text = {}
    for item in pool.values():
        for q in item["quotes"]:
            by_text.setdefault(norm_text(q["text"]), item["id"])

    added = 0
    for entry in load_json(HISTORY_PATH, {}).get("history", []):
        day = entry.get("date")
        item_id = entry.get("id")
        if not item_id and entry.get("subject"):
            item_id = by_subject.get(norm_text(entry["subject"]))
        if not item_id:
            texts = [q.get("text", "") for q in entry.get("quotes") or [] if isinstance(q, dict)]
            texts.append(entry.get("text", ""))
            item_id = next((by_text[norm_text(t)] for t in texts if norm_text(t) in by_text), None)
        if not item_id or not parse_day(day):
            continue
        st = item_stats(state, item_id)
        if day not in st["sent"]:
            st["sent"].append(day)
            st["sent"].sort()
            added += 1
    return added


def prune(state: dict, today: date) -> None:
    cutoff = (today - timedelta(days=KEEP_DAYS)).isoformat()
    state["days"] = {d: v for d, v in state["days"].items() if d >= cutoff}


def last_sent_kind(state: dict) -> str | None:
    for day in sorted(state["days"], reverse=True):
        kind = state["days"][day].get("sent_kind")
        if kind:
            return kind
    return None


# ---------- picking ----------

def _days_since(dates: list, today: date):
    parsed = [d for d in (parse_day(x) for x in dates) if d and d <= today]
    return (today - max(parsed)).days if parsed else None


def eligible(pool: dict, state: dict, today: date, exclude=(), level: int = 0) -> list:
    recent_days, cooldown = RELAX_LEVELS[level]
    out = []
    for item in pool.values():
        if item["id"] in exclude:
            continue
        st = state["items"].get(item["id"], {})
        if st.get("never"):
            continue
        since_sent = _days_since(st.get("sent", []), today)
        if since_sent is not None and since_sent < recent_days:
            continue
        since_offer = _days_since(st.get("offered", []), today)
        if cooldown and since_offer is not None and since_offer < cooldown:
            continue
        out.append(item)
    return out


def pick(pool: dict, state: dict, today: date, exclude=(), prefer: str | None = None,
         rng: random.Random | None = None):
    """
    Returns (item or None, info). Alternates between fresh articles and the
    timeless library; within a group, never-sent and least-offered come first.
    """
    rng = rng or random.Random()
    cands, level = [], 0
    for level in range(len(RELAX_LEVELS)):
        cands = eligible(pool, state, today, exclude, level)
        if cands:
            break

    fresh = [c for c in cands if is_fresh_article(c, today)]
    rest = [c for c in cands if not is_fresh_article(c, today)]
    info = {"level": level, "ready": len(eligible(pool, state, today, exclude, 0)),
            "fresh": len(fresh)}
    if not cands:
        return None, info

    if prefer is None:
        prefer = "timeless" if last_sent_kind(state) == "article" else "article"

    def times(item, key):
        return len(state["items"].get(item["id"], {}).get(key, []))

    # newest first among the least-offered
    fresh.sort(key=lambda i: (times(i, "offered"), _neg_date(i.get("published"))))
    rng.shuffle(rest)
    rest.sort(key=lambda i: (times(i, "sent"), times(i, "offered")))

    groups = [fresh, rest] if prefer == "article" else [rest, fresh]
    for group in groups:
        if group:
            return group[0], info
    return None, info


def _neg_date(value) -> int:
    d = parse_day((value or "")[:10])
    return -(d.toordinal() if d else 0)


# ---------- rendering ----------

def brother_message(item: dict) -> str:
    """Exactly what your brother receives: English, then Ukrainian."""
    lines = []
    subject = item.get("subject")
    lines += [f"\U0001F4AD Today's theme: {subject}" if subject else "\U0001F4AD Today's quote", ""]
    for q in item["quotes"]:
        lines.append(f"“{q['text']}”")
        if q.get("author"):
            lines.append(f"— {q['author']}")
        lines.append("")
    if item.get("kind") == "article" and item.get("title"):
        lines += [f"\U0001F4F0 {item.get('source') or 'Article'}: {item['title']}", ""]
    if item.get("analysis_en"):
        lines += [f"\U0001F4DD {item['analysis_en']}", ""]

    lines += ["─" * 12, ""]

    subject_uk = item.get("subject_uk") or subject
    lines += [f"\U0001F4AD Тема дня: {subject_uk}" if subject_uk else "\U0001F4AD Цитата дня", ""]
    for q in item["quotes"]:
        lines.append(f"«{q.get('text_uk') or q['text']}»")
        if q.get("author"):
            lines.append(f"— {q['author']}")
        lines.append("")
    if item.get("analysis_uk"):
        lines += [f"\U0001F4DD {item['analysis_uk']}", ""]
    if item.get("url"):
        lines += [f"\U0001F517 {item['url']}"]

    return "\n".join(lines).strip()


def source_line(item: dict, today: date) -> str:
    if item["kind"] == "article":
        when = parse_day((item.get("published") or "")[:10])
        fresh = "Fresh article" if is_fresh_article(item, today) else "Article"
        bits = [f"\U0001F4F0 {fresh} · {item.get('source') or 'web'}"]
        if when:
            bits.append(fmt_day(when))
        return " · ".join(bits)
    author = (item["quotes"][0].get("author") if item["quotes"] else "") or ""
    kind = "Timeless theme" if item["kind"] == "theme" else "Timeless library"
    return f"\U0001F3DB {kind}" + (f" · {author}" if author else "")


def history_line(state: dict, item_id: str) -> str:
    st = state["items"].get(item_id, {})
    offered = [d for d in st.get("offered", [])]
    sent = [d for d in st.get("sent", [])]
    if offered:
        last = parse_day(max(offered))
        offer_txt = f"\U0001F501 Offered {len(offered)}× before (last {fmt_day(last)})"
    else:
        offer_txt = "\U0001F501 First time offered"
    if sent:
        last = parse_day(max(sent))
        sent_txt = f"\U0001F4E4 Sent {len(sent)}× (last {fmt_day(last)})"
    else:
        sent_txt = "\U0001F4E4 Never sent"
    return f"{offer_txt} · {sent_txt}"


def admin_card(item: dict, state: dict, today: date, info: dict, notes=()) -> str:
    head = [
        f"\U0001F5F3 Today's pick · {today.strftime('%a')}, {fmt_day(today)}",
        source_line(item, today),
        history_line(state, item["id"]),
        f"\U0001F9EE Pool: {info['ready']} ready · {info['fresh']} fresh article"
        + ("" if info["fresh"] == 1 else "s"),
    ]
    if info["level"] > 0:
        head.append("⚠️ Pool is running dry: I loosened the no-repeat rules to find this one.")
    elif info["ready"] < LOW_POOL_WARNING:
        head.append(f"⚠️ Only {info['ready']} items left that haven't been sent lately.")
    head += list(notes)
    return "\n".join(head) + "\n━━━━━━━━━━━━\n" + brother_message(item)


def keyboard(item_id: str, today: date) -> dict:
    stamp = today.strftime("%Y%m%d")

    def btn(text, action):
        return {"text": text, "callback_data": f"{action}|{item_id}|{stamp}"}

    return {"inline_keyboard": [
        [btn("✅ Send today", "ok"), btn("⏭ Not today", "skip")],
        [btn("🚫 Never send", "ban"), btn("🔄 Another", "next")],
    ]}


def undo_keyboard(item_id: str, today: date) -> dict:
    stamp = today.strftime("%Y%m%d")
    return {"inline_keyboard": [[
        {"text": "↩️ Undo ban", "callback_data": f"unban|{item_id}|{stamp}"},
    ]]}


# ---------- the engine ----------

class Engine:
    """
    Wraps state + pool + Telegram so every entry point (morning tick, button
    tap, /today) goes through the same rules. `tg` is telegram_utils, or a
    fake in tests. `enrich` adds a subject/analysis to bare timeless quotes
    (articles.enrich_item), and may be None.
    """

    def __init__(self, tg, admin_id, customer_id="", enrich=None, now=None, rng=None):
        self.tg = tg
        self.admin = str(admin_id)
        self.customer = str(customer_id or "").strip()
        self.enrich = enrich
        self.now = now or now_local()
        self.today = self.now.date()
        self.rng = rng or random.Random()
        self.state = load_state()
        self.pool = build_pool(self.state["enriched"])
        seed_from_history(self.state, self.pool)
        self.sent_today = False

    def save(self):
        prune(self.state, self.today)
        save_state(self.state)

    # --- day records ---

    def day(self, create=False) -> dict | None:
        key = self.today.isoformat()
        if create and key not in self.state["days"]:
            self.state["days"][key] = {"status": "pending", "offers": [], "reminded": False}
        return self.state["days"].get(key)

    def active_offer(self) -> dict | None:
        day = self.day()
        return day["offers"][-1] if day and day.get("offers") else None

    def expire_old_days(self) -> list:
        expired = []
        for key, day in self.state["days"].items():
            if key < self.today.isoformat() and day.get("status") == "pending":
                day["status"] = "expired"
                expired.append(key)
                for offer in day.get("offers", [])[-1:]:
                    if offer.get("message_id"):
                        self.tg.remove_buttons(self.admin, offer["message_id"])
        return expired

    # --- offering ---

    def _enrich(self, item: dict) -> dict:
        if item["kind"] != "timeless" or item.get("analysis_en") or not self.enrich:
            return item
        try:
            extra = self.enrich(item)
        except Exception as exc:  # noqa: BLE001 - a plain quote is still a fine offer
            print(f"(enrichment failed for {item['id']}: {exc})")
            return item
        if extra:
            self.state["enriched"][item["id"]] = extra
            item = {**item, **{k: v for k, v in extra.items() if v}}
            self.pool[item["id"]] = item
        return item

    def offer(self, prefer=None, notes=(), exclude=()):
        day = self.day(create=True)
        shown = {o["id"] for o in day["offers"]} | set(exclude)
        item, info = pick(self.pool, self.state, self.today, shown, prefer, self.rng)
        if not item:
            self.tg.send_text(
                self.admin,
                "\U0001F615 Nothing left to offer today. Everything was sent in the last "
                f"{RECENT_SENT_DAYS} days, banned, or already shown. Add quotes to "
                "quotes_flat_pending.json, or wait for new articles.",
            )
            return None
        item = self._enrich(item)
        card = admin_card(item, self.state, self.today, info, notes)
        msg = self.tg.send_text(self.admin, card, reply_markup=keyboard(item["id"], self.today))
        day["offers"].append({
            "id": item["id"],
            "message_id": (msg or {}).get("message_id"),
            "at": self.now.isoformat(timespec="minutes"),
        })
        day["status"] = "pending"
        item_stats(self.state, item["id"])["offered"].append(self.today.isoformat())
        return item

    # --- the daily tick (morning card + evening reminder) ---

    def tick(self) -> str:
        expired = self.expire_old_days()
        day = self.day()
        if not day or not day.get("offers"):
            if self.now.hour < MORNING_HOUR:
                return "too early for today's card"
            yesterday = (self.today - timedelta(days=1)).isoformat()
            notes = ["⌛ Yesterday: no answer, so nothing was sent."] if yesterday in expired else []
            return "offered" if self.offer(notes=notes) else "pool empty"

        if (day["status"] == "pending" and not day.get("reminded")
                and REMINDER_HOUR <= self.now.hour < REMINDER_LATEST_HOUR):
            offer = self.active_offer()
            self.tg.send_text(
                self.admin,
                "⏰ Still waiting on today's pick ↑\n"
                "Nothing goes to your brother until you tap ✅ Send today.",
                reply_to=offer.get("message_id") if offer else None,
            )
            day["reminded"] = True
            return "reminded"
        return f"nothing to do (today: {day['status']})"

    # --- button taps ---

    def handle_callback(self, cq: dict) -> str:
        data = cq.get("data") or ""
        msg = cq.get("message") or {}
        message_id = msg.get("message_id")
        old_text = msg.get("text") or ""
        answer = lambda text: self.tg.answer_callback(cq.get("id", ""), text)  # noqa: E731

        if str((msg.get("chat") or {}).get("id")) != self.admin:
            answer("Not allowed.")
            return "ignored: not the admin chat"

        parts = data.split("|")
        if len(parts) != 3 or parts[0] not in ACTIONS:
            answer("Unknown button.")
            return f"ignored: bad callback {data!r}"
        action, item_id, stamp = parts
        tapped_day = datetime.strptime(stamp, "%Y%m%d").date() if stamp.isdigit() else None
        item = self.pool.get(item_id)

        # banning works on any card, old or new
        if action == "ban":
            item_stats(self.state, item_id)["never"] = True
            self.tg.edit_text(self.admin, message_id,
                              _with_status(old_text, "\U0001F6AB Never again. Removed from the pool."),
                              reply_markup=undo_keyboard(item_id, self.today))
            answer("Banned.")
            active = self.active_offer()
            day = self.day()
            if (tapped_day == self.today and day and day["status"] == "pending"
                    and active and active["id"] == item_id):
                self.offer(notes=["\U0001F6AB Replacing the one you just banned."])
                return "banned + offered another"
            return "banned"

        if action == "unban":
            item_stats(self.state, item_id)["never"] = False
            self.tg.edit_text(self.admin, message_id,
                              _with_status(_strip_status(old_text), "↩️ Ban undone. It's back in the pool."))
            answer("Ban undone.")
            return "unbanned"

        if tapped_day != self.today:
            answer(f"⌛ That pick was for {fmt_day(tapped_day) if tapped_day else 'another day'}. It has expired.")
            self.tg.remove_buttons(self.admin, message_id)
            return "expired card"

        day = self.day()
        active = self.active_offer()
        if not day or not active:
            answer("⌛ That card has expired.")
            self.tg.remove_buttons(self.admin, message_id)
            return "no offer today"
        if day["status"] == "sent":
            answer("✅ Already sent today.")
            self.tg.remove_buttons(self.admin, message_id)
            return "already sent"
        if active["id"] != item_id:
            answer("That one was already swapped out.")
            self.tg.remove_buttons(self.admin, message_id)
            return "stale card"
        if day["status"] != "pending":
            answer("Today was skipped. Send /today to reopen it.")
            self.tg.remove_buttons(self.admin, message_id)
            return f"day is {day['status']}"

        if action == "ok":
            if not item:
                answer("That item no longer exists in the library.")
                return "missing item"
            return self._send_to_brother(item, message_id, old_text, answer)

        if action == "skip":
            day["status"] = "skipped"
            self.tg.edit_text(self.admin, message_id, _with_status(
                old_text,
                "⏭ Not today. Nothing was sent. Tomorrow's pick comes in the morning.\n"
                "Changed your mind? Send /today."))
            answer("Skipped for today.")
            return "skipped"

        if action == "next":
            self.tg.edit_text(self.admin, message_id, _with_status(old_text, "\U0001F504 Swapped for another ↓"))
            answer("Finding another…")
            prefer = "timeless" if (item or {}).get("kind") == "article" else "article"
            return "offered another" if self.offer(prefer=prefer) else "pool empty"

        return "unhandled"

    def _send_to_brother(self, item, message_id, old_text, answer) -> str:
        text = brother_message(item)
        at = now_local().strftime("%H:%M")
        if self.customer:
            self.tg.send_text(self.customer, text)
            status = f"✅ Sent to your brother at {at}."
        else:
            status = "⚠️ CUSTOMER_CHAT_ID isn't set, so this went nowhere. Add the secret."
        day = self.day()
        day["status"] = "sent"
        day["sent_id"] = item["id"]
        day["sent_kind"] = "article" if item["kind"] == "article" else "timeless"
        item_stats(self.state, item["id"])["sent"].append(self.today.isoformat())
        append_history(item, self.today)
        self.sent_today = True
        self.tg.edit_text(self.admin, message_id, _with_status(old_text, status))
        answer("Sent." if self.customer else "Not sent: no brother chat id.")
        return "sent"

    # --- /today ---

    def reopen_today(self) -> str:
        day = self.day()
        if day and day["status"] == "sent":
            item = self.pool.get(day.get("sent_id"), {})
            self.tg.send_text(self.admin, f"✅ Already sent today: {label(item) if item else day.get('sent_id')}")
            return "already sent"
        if day and day["status"] == "pending" and day.get("offers"):
            # re-post the open card at the bottom of the chat instead of re-picking
            offer = day["offers"][-1]
            item = self.pool.get(offer["id"])
            if item:
                if offer.get("message_id"):
                    self.tg.remove_buttons(self.admin, offer["message_id"])
                _, info = pick(self.pool, self.state, self.today, {offer["id"]}, None, self.rng)
                card = admin_card(item, self.state, self.today, info, ["\U0001F4CC Re-posted."])
                msg = self.tg.send_text(self.admin, card, reply_markup=keyboard(item["id"], self.today))
                offer["message_id"] = (msg or {}).get("message_id")
                return "re-posted"
        if day:
            day["status"] = "pending"
            day["reminded"] = True  # you're clearly around; no 6pm nag needed
        return "offered" if self.offer(notes=["\U0001F513 Reopened today."]) else "pool empty"

    # --- /stats ---

    def stats_text(self) -> str:
        items = self.state["items"]
        banned = sum(1 for s in items.values() if s.get("never"))
        kinds = {}
        for item in self.pool.values():
            kinds[item["kind"]] = kinds.get(item["kind"], 0) + 1
        ready = eligible(self.pool, self.state, self.today, (), 0)
        fresh = [i for i in ready if is_fresh_article(i, self.today)]
        never_sent = [i for i in ready if not items.get(i["id"], {}).get("sent")]
        month_ago = (self.today - timedelta(days=30)).isoformat()
        sent_30 = sum(1 for s in items.values() for d in s.get("sent", []) if d >= month_ago)
        day = self.day()
        lines = [
            "\U0001F4CA Quote pool",
            "",
            f"Library: {kinds.get('theme', 0)} themes · {kinds.get('timeless', 0)} timeless quotes · "
            f"{kinds.get('article', 0)} article lines",
            f"Ready to offer: {len(ready)} ({len(never_sent)} never sent, {len(fresh)} fresh articles)",
            f"Banned: {banned}",
            f"Sent in the last 30 days: {sent_30}",
            f"Today: {day['status'] if day else 'no card yet'}",
        ]
        articles = load_json(ARTICLES_PATH, {})
        if articles.get("fetched_at"):
            feeds = articles.get("feeds", {})
            ok = sum(1 for f in feeds.values() if f.get("ok"))
            lines.append(f"Articles last checked: {articles['fetched_at'][:16].replace('T', ' ')} "
                         f"({ok}/{len(feeds)} feeds OK)")
        if not os.environ.get("GROQ_API_KEY"):
            lines.append("⚠️ GROQ_API_KEY isn't set, so no new article lines are coming in.")
        return "\n".join(lines)


def _with_status(text: str, status: str) -> str:
    return f"{text}\n\n{status}"


def _strip_status(text: str) -> str:
    return text.rsplit("\n\n\U0001F6AB Never again.", 1)[0]


def append_history(item: dict, today: date) -> None:
    """Log the send where the website (update_site.py) reads it."""
    state = load_json(HISTORY_PATH, {"used_indices": [], "history": []})
    entry = {
        "date": today.isoformat(),
        "id": item["id"],
        "kind": item["kind"],
        "subject": item.get("subject") or "",
        "subject_uk": item.get("subject_uk") or "",
        "quotes": item["quotes"],
        "analysis_en": item.get("analysis_en") or "",
        "analysis_uk": item.get("analysis_uk") or "",
    }
    if item.get("url"):
        entry["url"] = item["url"]
    history = state.setdefault("history", [])
    if history and history[-1].get("date") == entry["date"]:
        history[-1] = entry
    else:
        history.append(entry)
    save_json(HISTORY_PATH, state)
