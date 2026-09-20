"""
Swaps the item scheduled for one specific date - this is how you say
"different quote" after seeing the preview.

Triggered from the Actions tab ("Reroll scheduled item") with two inputs:
  date  - YYYY-MM-DD, must be today or later
  kind  - quotes | habits

Reads them from env (REROLL_DATE / REROLL_KIND), picks a replacement that
hasn't been sent or queued, saves it, and confirms to you on Telegram with
the before/after.

Refuses to touch past dates - those have already been sent.
"""

import os
import sys
from datetime import date

from telegram_utils import send_text
from render import short_label
import schedule_utils as su

ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID")
REROLL_DATE = (os.environ.get("REROLL_DATE") or "").strip()
REROLL_KIND = (os.environ.get("REROLL_KIND") or "quotes").strip().lower()


def fail(msg):
    print(msg, file=sys.stderr)
    if os.environ.get("BOT_TOKEN") and ADMIN_CHAT_ID:
        try:
            send_text(ADMIN_CHAT_ID, f"❌ Reroll failed: {msg}")
        except Exception as exc:  # noqa: BLE001 - reporting must never mask the error
            print(f"(could not notify admin: {exc})", file=sys.stderr)
    sys.exit(1)


def main():
    if not os.environ.get("BOT_TOKEN") or not ADMIN_CHAT_ID:
        print("Missing BOT_TOKEN or ADMIN_CHAT_ID.", file=sys.stderr)
        sys.exit(1)

    if REROLL_KIND not in ("quotes", "habits"):
        fail(f"kind must be 'quotes' or 'habits', got '{REROLL_KIND}'")

    try:
        target = date.fromisoformat(REROLL_DATE)
    except ValueError:
        fail(f"date must be YYYY-MM-DD, got '{REROLL_DATE}'")

    if target < date.today():
        fail(f"{REROLL_DATE} is in the past - that one has already been sent.")

    sched = su.load_schedule()
    library = su.load_library(REROLL_KIND)
    key = target.isoformat()

    old_idx = sched[REROLL_KIND].get(key)
    if old_idx is None:
        fail(
            f"nothing is scheduled for {key} in {REROLL_KIND}. "
            "Run \"Generate schedule\" first, or check the date."
        )

    old_label = short_label(library[old_idx], REROLL_KIND)

    # block the current pick so the reroll actually changes something
    new_idx = su.pick_index(REROLL_KIND, sched, extra_blocked=(old_idx,))
    sched[REROLL_KIND][key] = new_idx
    su.save_schedule(sched)

    new_label = short_label(library[new_idx], REROLL_KIND)
    kind_word = "quote" if REROLL_KIND == "quotes" else "habit"
    msg = (
        f"\U0001F504 Rerolled the {kind_word} for {key}\n\n"
        f"Was: {old_label}\n\n"
        f"Now: {new_label}"
    )
    send_text(ADMIN_CHAT_ID, msg)
    print(f"Rerolled {REROLL_KIND} on {key}: index {old_idx} -> {new_idx}")


if __name__ == "__main__":
    main()
