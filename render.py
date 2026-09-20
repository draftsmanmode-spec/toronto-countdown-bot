"""
Message rendering, including language.

LANG_MODE env var controls what gets sent:
  "both" (default) - Ukrainian first, English underneath
  "uk"             - Ukrainian only
  "en"             - English only

Set it as a repo secret or just leave it unset for bilingual.
"""

import os

LANG_MODE = (os.environ.get("LANG_MODE") or "both").strip().lower()
if LANG_MODE not in ("both", "uk", "en"):
    LANG_MODE = "both"

SEP = "\n———\n"


def quote_uk(q):
    return q.get("text_uk") or q["text"]


def build_quote_message(q, lang=None):
    lang = lang or LANG_MODE
    author = q.get("author")
    author_line = f"\n— {author}" if author else ""

    if lang == "uk":
        return f"\U0001F4AD Цитата дня\n\n«{quote_uk(q)}»{author_line}"
    if lang == "en":
        return f"\U0001F4AD Today's quote\n\n“{q['text']}”{author_line}"

    return (
        f"\U0001F4AD Цитата дня / Today's quote\n\n"
        f"«{quote_uk(q)}»\n\n"
        f"“{q['text']}”{author_line}"
    )


def build_habit_message(h, lang=None):
    lang = lang or LANG_MODE

    uk_block = (
        f"{h.get('title_uk') or h['title']}\n\n"
        f"{h.get('action_uk') or h['action']}\n\n"
        f"Навіщо: {h.get('why_uk') or h['why']}"
    )
    en_block = (
        f"{h['title']}\n\n"
        f"{h['action']}\n\n"
        f"Why: {h['why']}"
    )

    if lang == "uk":
        return f"\U0001F331 Звичка тижня\n\n{uk_block}"
    if lang == "en":
        return f"\U0001F331 This week's habit\n\n{en_block}"

    return (
        f"\U0001F331 Звичка тижня / This week's habit\n\n"
        f"{uk_block}{SEP}{en_block}"
    )


def short_label(item, kind):
    """One-line label for the schedule preview."""
    if kind == "quotes":
        text = quote_uk(item) if LANG_MODE in ("both", "uk") else item["text"]
        author = item.get("author")
        line = text if len(text) <= 95 else text[:92].rstrip() + "…"
        return f"{line}" + (f" — {author}" if author else "")
    title = item.get("title_uk") if LANG_MODE in ("both", "uk") else item["title"]
    return title or item["title"]
