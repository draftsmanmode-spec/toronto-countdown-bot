"""
Rebuilds the HTML between the <!-- QUOTES_START --> and <!-- QUOTES_END -->
markers in docs/index.html using quote_state.json's history: today's quote
as a featured card, plus a collapsible list of everything sent before.

Run this right after send_quote.py so the log already includes today's
entry.
"""

import html as html_module
import json
import pathlib

STATE_PATH = "quote_state.json"
SITE_PATH = pathlib.Path("docs/index.html")

START_MARKER = "<!-- QUOTES_START -->"
END_MARKER = "<!-- QUOTES_END -->"

HISTORY_DISPLAY_LIMIT = 60  # keep the page from growing forever


def load_history():
    with open(STATE_PATH, encoding="utf-8") as f:
        return json.load(f).get("history", [])


def format_date(iso_date: str) -> str:
    # e.g. "2026-08-03" -> "Aug 3, 2026"
    from datetime import date
    y, m, d = (int(x) for x in iso_date.split("-"))
    return date(y, m, d).strftime("%b %-d, %Y")


def render_quote_block(entry: dict) -> str:
    text = html_module.escape(entry["text"])
    author = entry.get("author")
    author_html = f'<div class="qauthor">— {html_module.escape(author)}</div>' if author else ""
    return text, author_html


def build_html(history: list) -> str:
    if not history:
        return '<div style="text-align:center; color:var(--sub); padding:20px;">First quote lands after the daily job runs.</div>'

    today_entry = history[-1]
    text, author_html = render_quote_block(today_entry)
    today_date = format_date(today_entry["date"])

    featured = f"""
    <div class="quote-today">
      <div class="qmark">&ldquo;</div>
      <p>{text}</p>
      {author_html}
      <div class="qdate">{today_date}</div>
    </div>"""

    older = list(reversed(history[:-1]))[:HISTORY_DISPLAY_LIMIT]
    if older:
        items = ""
        for entry in older:
            t, a_html = render_quote_block(entry)
            d = format_date(entry["date"])
            author_txt = entry.get("author") or ""
            items += f"""
        <div class="qh-item">
          <p>&ldquo;{t}&rdquo;</p>
          <div class="qh-meta">{d}{' &middot; ' + html_module.escape(author_txt) if author_txt else ''}</div>
        </div>"""
        history_html = f"""
    <details class="quote-history">
      <summary>See {len(older)} earlier quote{'s' if len(older) != 1 else ''} ▾</summary>
      {items}
    </details>"""
    else:
        history_html = ""

    return featured + history_html


def main():
    history = load_history()
    new_block = build_html(history)

    site_html = SITE_PATH.read_text(encoding="utf-8")
    start = site_html.find(START_MARKER)
    end = site_html.find(END_MARKER)
    if start == -1 or end == -1:
        raise RuntimeError("Could not find QUOTES_START/QUOTES_END markers in docs/index.html")

    updated = (
        site_html[: start + len(START_MARKER)]
        + "\n" + new_block + "\n  "
        + site_html[end:]
    )
    SITE_PATH.write_text(updated, encoding="utf-8")
    print(f"Updated {SITE_PATH} with {len(history)} quote(s) in history.")


if __name__ == "__main__":
    main()
