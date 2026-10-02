"""
One entry point for everything the bot reacts to, so a button tap behaves
the same whether it arrived instantly (Vercel webhook) or late (poll).

How events get here (see .github/workflows/quote.yml):
  repository_dispatch "tg_state" / "tg_relay"  one Telegram update, forwarded
                                               by the Vercel webhook
  repository_dispatch "daily_tick"             Vercel cron, 8am + 6pm Toronto
  schedule                                     GitHub fallback for the tick
  workflow_dispatch                            run by hand: tick | today

Without the webhook (GitHub-only mode) updates are pulled instead, by
drain(): poll_messages.py calls it, and so does every tick here. After a
tick sends a card or reminder, drain() keeps listening for 15 minutes, so a
tap right after the card arrives is handled within seconds.

What it does with them:
  your brother messages the bot   -> reported to you
  you type plain text             -> relayed to him, with a delivery report
  you tap a button on a card      -> approval.Engine.handle_callback
  /today /stats /schedule /help   -> commands
"""

import json
import os
import sys
import time
import traceback

import approval
import telegram_utils

OFFSET_PATH = "state.json"
LISTEN_SECONDS = 15 * 60
LISTEN_AFTER = {"offered", "reminded", "re-posted"}

HELP_TEXT = (
    "\U0001F916 Bot commands\n\n"
    "/today — show today's pick (or reopen today if you skipped it)\n"
    "/stats — how many quotes are ready, banned, sent\n"
    "/schedule — upcoming weekly habits\n"
    "/help — this list\n\n"
    "Each morning you get one pick with buttons: ✅ Send today · ⏭ Not today · "
    "🚫 Never send · 🔄 Another. Nothing reaches your brother until you tap ✅.\n\n"
    "Anything else you type here is relayed straight to your brother, and you get "
    "a delivery report back."
)


def _enrich(item):
    import articles  # lazy: only needed when a bare quote is offered
    return articles.enrich_item(item)


class Brain:
    def __init__(self, tg=telegram_utils, admin=None, customer=None, enrich=_enrich, now=None):
        self.tg = tg
        self.admin = str(admin if admin is not None else os.environ.get("ADMIN_CHAT_ID", "")).strip()
        self.customer = str(customer if customer is not None else os.environ.get("CUSTOMER_CHAT_ID", "")).strip()
        self.enrich = enrich
        self.now = now
        self._engine = None
        self.failures = 0

    @property
    def engine(self) -> approval.Engine:
        if self._engine is None:
            self._engine = approval.Engine(self.tg, self.admin, self.customer, self.enrich, self.now)
        return self._engine

    # ---------- routing ----------

    def handle_update(self, update: dict) -> str:
        if update.get("callback_query"):
            result = self.engine.handle_callback(update["callback_query"])
        elif update.get("message"):
            result = self.handle_message(update["message"])
        else:
            result = "ignored: unsupported update"
        print(f"update {update.get('update_id')}: {result}")
        return result

    def handle_message(self, message: dict) -> str:
        chat_id = str((message.get("chat") or {}).get("id"))
        if self.customer and chat_id == self.customer:
            summary = telegram_utils.describe_message(message)
            self.tg.send_text(self.admin, f"\U0001F4AC Your brother messaged the bot:\n\n{summary}")
            return "reported brother's message"
        if chat_id != self.admin:
            return f"ignored: unknown chat {chat_id}"

        text = message.get("text") or ""
        if text.startswith("/"):
            return self.handle_command(text)
        if not text:
            self.tg.send_text(self.admin, "ℹ️ Only text messages get relayed. That one wasn't sent on.")
            return "ignored non-text admin message"
        if not self.customer:
            self.tg.send_text(self.admin, "⚠️ CUSTOMER_CHAT_ID isn't set, so there's nobody to relay to.")
            return "no customer"
        try:
            self.tg.send_text(self.customer, text)
        except Exception as exc:  # noqa: BLE001 - a failed relay must never be silent
            self.tg.send_text(self.admin, f"❌ NOT delivered to your brother:\n\n“{text}”\n\nReason: {exc}")
            return "relay failed"
        self.tg.send_text(self.admin, f"✅ Delivered to your brother:\n\n“{text}”")
        return "relayed"

    def handle_command(self, text: str) -> str:
        cmd = text.split()[0].lower().lstrip("/").split("@")[0]
        if cmd == "today":
            return "today: " + self.engine.reopen_today()
        if cmd in ("stats", "pool"):
            self.tg.send_text(self.admin, self.engine.stats_text())
            return "sent stats"
        if cmd in ("schedule", "preview"):
            from send_schedule_preview import build_preview
            self.tg.send_text(self.admin, build_preview())
            return "sent schedule"
        if cmd in ("help", "start"):
            self.tg.send_text(self.admin, HELP_TEXT)
            return "sent help"
        self.tg.send_text(self.admin, f"❓ Unknown command “/{cmd}”. Send /help for the list.")
        return f"unknown command {cmd}"

    def tick(self) -> str:
        result = self.engine.tick()
        print(f"tick: {result}")
        return result

    def decided_today(self) -> bool:
        if self._engine is None:
            return False
        day = self._engine.day()
        return bool(day) and day.get("status") in ("sent", "skipped")

    # ---------- wrap-up ----------

    def finish(self) -> bool:
        """Save state; refresh the website if something was sent. False on failure."""
        if self._engine is None:
            return True
        self._engine.save()
        if not self._engine.sent_today:
            return True
        try:
            import update_site
            update_site.main()
            return True
        except Exception:  # noqa: BLE001 - the send already happened; just report
            traceback.print_exc()
            return False


# ---------- pulling updates (GitHub-only mode) ----------

def load_offset() -> int:
    if os.path.exists(OFFSET_PATH):
        with open(OFFSET_PATH) as f:
            return json.load(f).get("last_update_id", 0)
    return 0


def save_offset(update_id: int) -> None:
    with open(OFFSET_PATH, "w") as f:
        json.dump({"last_update_id": update_id}, f)


def drain(brain: Brain, listen_seconds: int = 0) -> int:
    """
    Feed waiting Telegram updates through `brain`. With listen_seconds, keep
    long-polling until today's card is decided or the time is up.
    Returns how many updates were handled, or -1 if the webhook is connected
    (Telegram then refuses getUpdates, and Vercel delivers instead).
    """
    if brain.tg.get_webhook_url():
        return -1
    deadline = time.monotonic() + listen_seconds
    offset = start = load_offset()
    handled = 0
    while True:
        remaining = deadline - time.monotonic()
        updates = brain.tg.get_updates(offset, timeout=int(min(25, max(0, remaining))))
        for update in updates:
            offset = max(offset, update["update_id"] + 1)
            handled += 1
            try:
                brain.handle_update(update)
            except Exception as exc:  # noqa: BLE001 - one bad update must not block the rest
                brain.failures += 1
                print(f"update {update.get('update_id')} failed: {exc}", file=sys.stderr)
        if offset != start:
            save_offset(offset)
            start = offset
        if remaining <= 0 or brain.decided_today():
            return handled
        if not updates:
            time.sleep(1)  # long-polling normally blocks; never spin if it returns early


def run_tick(brain: Brain, reopen: bool = False) -> None:
    pulled = drain(brain)  # taps that arrived since the last run come first
    result = ("today: " + brain.engine.reopen_today()) if reopen else brain.tick()
    if pulled >= 0 and result.removeprefix("today: ") in LISTEN_AFTER:
        print(f"Listening for taps for up to {LISTEN_SECONDS // 60} minutes...")
        drain(brain, LISTEN_SECONDS)


def main():
    if not os.environ.get("BOT_TOKEN") or not os.environ.get("ADMIN_CHAT_ID"):
        print("Missing BOT_TOKEN or ADMIN_CHAT_ID.", file=sys.stderr)
        sys.exit(1)

    event = os.environ.get("GITHUB_EVENT_NAME", "workflow_dispatch")
    payload = {}
    path = os.environ.get("GITHUB_EVENT_PATH")
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            payload = json.load(f)
    task = (os.environ.get("TASK") or "tick").strip().lower()

    brain = Brain()
    ok = True
    try:
        if event == "repository_dispatch":
            action = payload.get("action")
            if action in ("tg_state", "tg_relay"):
                brain.handle_update((payload.get("client_payload") or {}).get("update") or {})
            elif action == "daily_tick":
                run_tick(brain)
            else:
                print(f"Ignoring dispatch action {action!r}")
        elif event == "workflow_dispatch" and task == "today":
            run_tick(brain, reopen=True)
        elif event == "workflow_dispatch" and task == "articles":
            print("Article refresh ran in the previous step; nothing else to do.")
        else:
            run_tick(brain)
    except Exception as exc:  # noqa: BLE001
        ok = False
        traceback.print_exc()
        try:
            brain.tg.send_text(brain.admin, f"❌ Quote bot hit an error: {exc}\n"
                                            "Details are in GitHub → Actions → Quote bot.")
        except Exception:  # noqa: BLE001
            pass
    finally:
        ok = brain.finish() and ok and not brain.failures

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
