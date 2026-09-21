"""
Shared logic for the reviewable send schedule.

Instead of picking a quote/habit randomly at send time (which makes it
impossible to preview or approve anything in advance), the bot now keeps a
dated queue in schedule.json:

    {
      "quotes": {"2026-09-21": 42, "2026-09-22": 7, ...},
      "habits": {"2026-09-22": 3, "2026-09-29": 11, ...}
    }

The senders just look up today's date. generate_schedule.py extends the
queue forward, send_schedule_preview.py shows what's coming, and
reroll_schedule.py swaps a single dated entry.

Habits land on Mondays only.
"""

import json
import os
import random
from datetime import date, timedelta

SCHEDULE_PATH = "schedule.json"
QUOTES_PATH = "quotes.json"
HABITS_PATH = "habits.json"
QUOTE_STATE_PATH = "quote_state.json"
HABIT_STATE_PATH = "weekly_habit_state.json"

QUOTE_HORIZON_DAYS = 30   # how far ahead quotes are queued
HABIT_HORIZON_WEEKS = 8   # how many Mondays ahead habits are queued


def load_json(path, default):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_schedule():
    sched = load_json(SCHEDULE_PATH, {})
    sched.setdefault("quotes", {})
    sched.setdefault("habits", {})
    return sched


def save_schedule(sched):
    save_json(SCHEDULE_PATH, sched)


def load_library(kind):
    return load_json(QUOTES_PATH if kind == "quotes" else HABITS_PATH, [])


def used_indices(kind):
    path = QUOTE_STATE_PATH if kind == "quotes" else HABIT_STATE_PATH
    return set(load_json(path, {}).get("used_indices", []))


def pick_index(kind, sched, extra_blocked=()):
    """
    Pick an index that hasn't been sent yet and isn't already queued.
    When the whole library has been cycled through, start a fresh cycle but
    still avoid anything sitting in the upcoming queue.
    """
    pool_size = len(load_library(kind))
    if pool_size == 0:
        raise RuntimeError(f"{kind} library is empty")

    queued = set(sched.get(kind, {}).values())
    blocked = used_indices(kind) | queued | set(extra_blocked)

    available = [i for i in range(pool_size) if i not in blocked]
    if not available:
        # library exhausted - new cycle, but don't repeat what's still queued
        blocked = queued | set(extra_blocked)
        available = [i for i in range(pool_size) if i not in blocked]
    if not available:
        available = list(range(pool_size))

    return random.choice(available)


def upcoming_mondays(start, weeks):
    """Return the next `weeks` Mondays on or after `start`."""
    days_ahead = (0 - start.weekday()) % 7
    first = start + timedelta(days=days_ahead)
    return [first + timedelta(weeks=w) for w in range(weeks)]


def ensure_schedule(today=None):
    """
    Fill the queue forward so quotes cover QUOTE_HORIZON_DAYS and habits
    cover HABIT_HORIZON_WEEKS of Mondays. Existing entries are never
    overwritten. Returns (schedule, number_of_new_entries_added).
    """
    today = today or date.today()
    sched = load_schedule()
    added = 0

    # never queue further ahead than the library is big, or the queue fills
    # with repeats (13 themes over 30 days would repeat within two weeks)
    quote_days = min(QUOTE_HORIZON_DAYS, max(1, len(load_library("quotes"))))
    habit_weeks = min(HABIT_HORIZON_WEEKS, max(1, len(load_library("habits"))))

    for offset in range(quote_days):
        day = (today + timedelta(days=offset)).isoformat()
        if day not in sched["quotes"]:
            sched["quotes"][day] = pick_index("quotes", sched)
            added += 1

    for monday in upcoming_mondays(today, habit_weeks):
        day = monday.isoformat()
        if day not in sched["habits"]:
            sched["habits"][day] = pick_index("habits", sched)
            added += 1

    prune_past(sched, today)
    return sched, added


def prune_past(sched, today=None, keep_days=90):
    """Drop entries older than keep_days so schedule.json doesn't grow forever."""
    today = today or date.today()
    cutoff = (today - timedelta(days=keep_days)).isoformat()
    for kind in ("quotes", "habits"):
        sched[kind] = {d: i for d, i in sched[kind].items() if d >= cutoff}


def scheduled_index(kind, day, sched=None):
    """Index scheduled for `day` (a date), or None if nothing is queued."""
    sched = sched or load_schedule()
    return sched.get(kind, {}).get(day.isoformat())
