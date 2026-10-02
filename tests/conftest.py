import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

TZ = ZoneInfo("America/Toronto")
ADMIN = "111"
BROTHER = "222"


class FakeTG:
    """Records every Telegram call instead of making it."""

    def __init__(self):
        self.sent, self.edits, self.removed, self.answers = [], [], [], []
        self._next_id = 1000

    def send_text(self, chat_id, text, reply_markup=None, reply_to=None):
        self._next_id += 1
        self.sent.append({"chat": str(chat_id), "text": text, "markup": reply_markup,
                          "reply_to": reply_to, "message_id": self._next_id})
        return {"message_id": self._next_id}

    def edit_text(self, chat_id, message_id, text, reply_markup=None):
        self.edits.append({"chat": str(chat_id), "message_id": message_id, "text": text,
                           "markup": reply_markup})

    def remove_buttons(self, chat_id, message_id):
        self.removed.append(message_id)

    def answer_callback(self, callback_id, text=""):
        self.answers.append(text)

    # helpers for assertions
    def to(self, chat):
        return [m for m in self.sent if m["chat"] == chat]

    def cards(self):
        return [m for m in self.sent if m["markup"] and m["chat"] == ADMIN
                and "ok|" in str(m["markup"])]


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A scratch copy of the bot's data files, with the cwd pointed at it."""
    for name in ("quotes.json", "quotes_flat_pending.json", "quote_state.json",
                 "habits.json", "schedule.json", "weekly_habit_state.json"):
        shutil.copy(ROOT / name, tmp_path / name)
    (tmp_path / "docs").mkdir()
    shutil.copy(ROOT / "docs" / "index.html", tmp_path / "docs" / "index.html")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    return tmp_path


@pytest.fixture
def tg():
    return FakeTG()


def at(day: str, hour: int, minute: int = 0) -> datetime:
    y, m, d = (int(x) for x in day.split("-"))
    return datetime(y, m, d, hour, minute, tzinfo=TZ)


def tap(card: dict, action: str, chat=ADMIN, cq_id="cq1") -> dict:
    """Build the callback_query Telegram would send for a button on `card`."""
    data = None
    for row in card["markup"]["inline_keyboard"]:
        for btn in row:
            if btn["callback_data"].startswith(action + "|"):
                data = btn["callback_data"]
    assert data, f"no {action} button on card"
    return {"id": cq_id, "data": data,
            "message": {"message_id": card["message_id"], "chat": {"id": int(chat)},
                        "text": card["text"]}}
