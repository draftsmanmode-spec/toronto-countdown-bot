"""
Sends a combined 1-2 quote "theme of the day" to your brother (CUSTOMER_CHAT_ID),
reports a copy to you (ADMIN_CHAT_ID), and logs it to quote_state.json so
update_site.py can show it on the website.

Each entry in quotes.json is a "subject" (theme) with 1-2 quotes and a short
analysis, in English and Ukrainian. Every day, one subject is picked (cycling
through all subjects without repeats until the whole list has been used, then
reshuffling) and its quotes + analysis are sent in English, followed by the
same content in Ukrainian underneath.

Required repo secrets:
  BOT_TOKEN
  ADMIN_CHAT_ID
  CUSTOMER_CHAT_ID
"""

import json
import os
import random
import sys
from datetime import date

from telegram_utils import send_text

ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID")
CUSTOMER_CHAT_ID = os.environ.get("CUSTOMER_CHAT_ID", "").strip()

QUOTES_PATH = "quotes.json"
STATE_PATH = "quote_state.json"


def load_subjects():
    with open(QUOTES_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_state():
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {"used_indices": [], "history": []}


def save_state(state):
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def pick_subject(subjects, state):
    used = set(state.get("used_indices", []))
    available = [i for i in range(len(subjects)) if i not in used]
    if not available:
        used = set()
        available = list(range(len(subjects)))
    idx = random.choice(available)
    used.add(idx)
    state["used_indices"] = sorted(used)
    return subjects[idx]


def build_message(subject: dict) -> str:
    lines = [f"\U0001F4AD Today's theme: {subject['subject']}", ""]
    for q in subject["quotes"]:
        lines.append(f"“{q['text']}”")
        lines.append(f"— {q['author']}")
        lines.append("")
    lines.append(f"\U0001F4DD {subject['analysis_en']}")
    lines.append("")
    lines.append("─" * 12)
    lines.append("")
    lines.append(f"\U0001F4AD Тема дня: {subject['subject_uk']}")
    lines.append("")
    for q in subject["quotes"]:
        lines.append(f"«{q['text_uk']}»")
        lines.append(f"— {q['author']}")
        lines.append("")
    lines.append(f"\U0001F4DD {subject['analysis_uk']}")
    return "\n".join(lines)


def main():
    if not os.environ.get("BOT_TOKEN") or not ADMIN_CHAT_ID:
        print("Missing BOT_TOKEN or ADMIN_CHAT_ID.", file=sys.stderr)
        sys.exit(1)

    subjects = load_subjects()
    state = load_state()
    subject = pick_subject(subjects, state)
    message = build_message(subject)

    today = date.today().isoformat()
    state.setdefault("history", []).append({
        "date": today,
        "subject": subject["subject"],
        "subject_uk": subject["subject_uk"],
        "quotes": subject["quotes"],
        "analysis_en": subject["analysis_en"],
        "analysis_uk": subject["analysis_uk"],
    })
    save_state(state)

    if CUSTOMER_CHAT_ID:
        send_text(CUSTOMER_CHAT_ID, message)
        print("Sent to customer.")
        send_text(ADMIN_CHAT_ID, "\U0001F4E4 Sent to your brother just now:\n\n" + message)
        print("Sent report to admin.")
    else:
        send_text(ADMIN_CHAT_ID, "⚠️ CUSTOMER_CHAT_ID not set - sent to you only:\n\n" + message)
        print("Sent to admin only (no customer chat id set).")


if __name__ == "__main__":
    main()
