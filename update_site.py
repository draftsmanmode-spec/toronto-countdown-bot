"""
Rebuilds the HTML between the <!-- QUOTES_START --> and <!-- QUOTES_END -->
markers in docs/index.html from quote_state.json: today's quote as a
featured card, plus a collapsible list of everything sent before.

Shows Ukrainian and English together when the logged entry has both.

Run this right after send_quote.py so the log already includes today.
"""

import html as html_module
import json
import pathlib
from datetime import date

STATE_PATH = "quote_state.json"
SITE_PATH = pathlib.Path("docs/index.html")

START_MARKER = "<!-- QUOTES_START -->"
END_MARKER = "<!-- QUOTES_END -->"

HISTORY_DISPLAY_LIMIT = 60  # keep the page from growing forever


def esc(value):
    return html_module.escape(value or "")


def load_history():
    with open(STATE_PATH, encoding="utf-8") as f:
        return json.load(f).get("history", [])


def format_date(iso_date: str) -> str:
    y, m, d = (int(x) for x in iso_date.split("-"))
    return date(y, m, d).strftime("%b %d, %Y").replace(" 0", " ")


def build_html(history: list) -> str:
    if not history:
        return ('<div style="text-align:center; color:var(--sub); padding:20px;">'
                "First quote lands after the daily job runs.</div>")

    today_entry = history[-1]
    uk = today_entry.get("text_uk")
    en = today_entry["text"]
    author = today_entry.get("author")

    primary = esc(uk or en)
    secondary = f'<p class="quote-alt">&ldquo;{esc(en)}&rdquo;</p>' if uk else ""
    author_html = f'<div class="qauthor">&mdash; {esc(author)}</div>' if author else ""

    featured = f"""
    <div class="quote-today">
      <div class="qmark">&ldquo;</div>
      <p>{primary}</p>
      {secondary}
      {author_html}
      <div class="qdate">{format_date(today_entry["date"])}</div>
    </div>"""

    older = list(reversed(history[:-1]))[:HISTORY_DISPLAY_LIMIT]
    if not older:
        return featured

    items = ""
    for entry in older:
        e_uk = entry.get("text_uk")
        e_en = entry["text"]
        e_author = entry.get("author") or ""
        alt = f'<p class="qh-alt">&ldquo;{esc(e_en)}&rdquo;</p>' if e_uk else ""
        meta = format_date(entry["date"])
        if e_author:
            meta += " &middot; " + esc(e_author)
        items += f"""
        <div class="qh-item">
          <p>&ldquo;{esc(e_uk or e_en)}&rdquo;</p>
          {alt}
          <div class="qh-meta">{meta}</div>
        </div>"""

    plural = "s" if len(older) != 1 else ""
    history_html = f"""
    <details class="quote-history">
      <summary>See {len(older)} earlier quote{plural} &#9662;</summary>
      {items}
    </details>"""

    return featured + history_html


EXTRA_CSS = """
.quote-today .quote-alt { font-family:'Poppins',sans-serif; font-size:15px; line-height:1.5;
  color:var(--sub); margin:-4px 0 12px; font-style:italic; }
.qh-item .qh-alt { font-family:'Poppins',sans-serif; font-size:13px; line-height:1.45;
  color:var(--sub); margin:2px 0 4px; font-style:italic; }
"""


def ensure_css(site_html: str) -> str:
    """
    Add styling for the Ukrainian/English second line if it isn't there yet.
    Done here rather than by shipping a whole index.html, so the rest of the
    page (birthday section, photos, layout) is never overwritten.
    """
    if ".quote-alt" in site_html:
        return site_html
    close = site_html.find("</style>")
    if close == -1:
        print("WARNING: no </style> found, skipping CSS injection.")
        return site_html
    print("Injected bilingual quote CSS.")
    return site_html[:close] + EXTRA_CSS + site_html[close:]


def main():
    history = load_history()
    new_block = build_html(history)

    site_html = SITE_PATH.read_text(encoding="utf-8")
    site_html = ensure_css(site_html)
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
