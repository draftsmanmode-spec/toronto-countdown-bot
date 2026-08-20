"""
Rebuilds the HTML between the <!-- QUOTES_START --> and <!-- QUOTES_END -->
markers in docs/index.html using quote_state.json's history: today's theme
(quotes + analysis, EN then UK) as a featured card, plus a collapsible list
of everything sent before.

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


def render_quotes_html(quotes: list) -> str:
    out = ""
    for q in quotes:
        text = html_module.escape(q["text"])
        text_uk = html_module.escape(q.get("text_uk", ""))
        author = html_module.escape(q.get("author", ""))
        out += f"""
      <p class="qline">&ldquo;{text}&rdquo;</p>
      <div class="qauthor">&mdash; {author}</div>
      <p class="qline qline-uk">&laquo;{text_uk}&raquo;</p>
      <div class="qauthor">&mdash; {author}</div>"""
    return out


def build_html(history: list) -> str:
    if not history:
        return '<div style="text-align:center; color:var(--sub); padding:20px;">First quote lands after the daily job runs.</div>'

    today_entry = history[-1]
    today_date = format_date(today_entry["date"])
    subject = html_module.escape(today_entry.get("subject", ""))
    subject_uk = html_module.escape(today_entry.get("subject_uk", ""))
    analysis_en = html_module.escape(today_entry.get("analysis_en", ""))
    analysis_uk = html_module.escape(today_entry.get("analysis_uk", ""))
    quotes_html = render_quotes_html(today_entry.get("quotes", []))

    featured = f"""
    <div class="quote-today">
      <div class="qmark">&ldquo;</div>
      <div class="qsubject">{subject} / {subject_uk}</div>
      {quotes_html}
      <p class="qanalysis">{analysis_en}</p>
      <p class="qanalysis qanalysis-uk">{analysis_uk}</p>
      <div class="qdate">{today_date}</div>
    </div>"""

    older = list(reversed(history[:-1]))[:HISTORY_DISPLAY_LIMIT]
    if older:
        items = ""
        for entry in older:
            d = format_date(entry["date"])
            subj = html_module.escape(entry.get("subject", ""))
            subj_uk = html_module.escape(entry.get("subject_uk", ""))
            q_html = render_quotes_html(entry.get("quotes", []))
            a_en = html_module.escape(entry.get("analysis_en", ""))
            a_uk = html_module.escape(entry.get("analysis_uk", ""))
            items += f"""
        <div class="qh-item">
          <div class="qh-subject">{subj} / {subj_uk}</div>
          {q_html}
          <p class="qanalysis">{a_en}</p>
          <p class="qanalysis qanalysis-uk">{a_uk}</p>
          <div class="qh-meta">{d}</div>
        </div>"""
        history_html = f"""
    <details class="quote-history">
      <summary>See {len(older)} earlier theme{'s' if len(older) != 1 else ''} &#9662;</summary>
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
    print(f"Updated {SITE_PATH} with {len(history)} theme(s) in history.")


if __name__ == "__main__":
    main()
