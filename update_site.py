"""
Rebuilds the HTML between the <!-- QUOTES_START --> and <!-- QUOTES_END -->
markers in docs/index.html from quote_state.json.

Two entry shapes exist in the history and BOTH are rendered:

  themed (the original format, most of the history):
      subject, subject_uk, quotes[], analysis_en, analysis_uk, date
  single (what the newer sender writes):
      text, text_uk, author, date

Safety rule: this script must never replace real history with the
empty-state placeholder. If the history is non-empty but nothing in it can
be rendered, it aborts WITHOUT touching docs/index.html, so a shape it
doesn't understand can never silently wipe the page.
"""

import html as html_module
import json
import pathlib
import sys
from datetime import date

STATE_PATH = "quote_state.json"
SITE_PATH = pathlib.Path("docs/index.html")

START_MARKER = "<!-- QUOTES_START -->"
END_MARKER = "<!-- QUOTES_END -->"

HISTORY_DISPLAY_LIMIT = 60

EMPTY_STATE = ('<div style="text-align:center; color:var(--sub); padding:20px;">'
               "First quote lands after the daily job runs.</div>")


def esc(value):
    return html_module.escape(value) if isinstance(value, str) else ""


def first_str(entry, keys):
    if not isinstance(entry, dict):
        return None
    for key in keys:
        value = entry.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


# ---------- shape detection ----------

def is_themed(entry):
    return isinstance(entry, dict) and ("quotes" in entry or "subject" in entry)


def quote_items(entry):
    """[(english, ukrainian, author)] from a themed entry's quotes list."""
    raw = entry.get("quotes")
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list):
        return []

    items = []
    for q in raw:
        if isinstance(q, str) and q.strip():
            items.append((q.strip(), None, ""))
            continue
        if not isinstance(q, dict):
            continue
        en = first_str(q, ("text", "text_en", "en", "quote", "line", "quote_en"))
        uk = first_str(q, ("text_uk", "uk", "quote_uk", "text_ua", "line_uk", "uk_text"))
        author = first_str(q, ("author", "by", "source", "attribution")) or ""
        if en or uk:
            items.append((en, uk, author))
    return items


def single_parts(entry):
    """(english, ukrainian, author) from a single-quote entry, or None."""
    if isinstance(entry, str) and entry.strip():
        return entry.strip(), None, ""
    en = first_str(entry, ("text", "text_en", "en", "quote", "body", "message"))
    uk = first_str(entry, ("text_uk", "uk", "text_ua"))
    if not (en or uk):
        return None
    return en, uk, first_str(entry, ("author",)) or ""


def renderable(entry):
    if is_themed(entry):
        return bool(quote_items(entry)) or bool(
            first_str(entry, ("subject", "subject_uk", "analysis_en", "analysis_uk"))
        )
    return single_parts(entry) is not None


def format_date(value):
    if not isinstance(value, str):
        return ""
    try:
        y, m, d = (int(x) for x in value.split("-"))
        return date(y, m, d).strftime("%b %d, %Y").replace(" 0", " ")
    except (ValueError, TypeError):
        return value


def subject_line(entry):
    en = first_str(entry, ("subject",))
    uk = first_str(entry, ("subject_uk", "subject_ua"))
    parts = [p for p in (en, uk) if p]
    return " / ".join(parts)


# ---------- rendering ----------

def render_featured(entry):
    dt = format_date(entry.get("date") if isinstance(entry, dict) else None)

    if is_themed(entry):
        body = ""
        subject = subject_line(entry)
        if subject:
            body += f'\n      <div class="qsubject">{esc(subject)}</div>'
        for en, uk, author in quote_items(entry):
            if en:
                body += f'\n      <p class="qline">&ldquo;{esc(en)}&rdquo;</p>'
                if author:
                    body += f'\n      <div class="qauthor">&mdash; {esc(author)}</div>'
            if uk:
                body += f'\n      <p class="qline qline-uk">&laquo;{esc(uk)}&raquo;</p>'
                if author:
                    body += f'\n      <div class="qauthor">&mdash; {esc(author)}</div>'
        an_en = first_str(entry, ("analysis_en", "analysis"))
        an_uk = first_str(entry, ("analysis_uk", "analysis_ua"))
        if an_en:
            body += f'\n      <p class="qanalysis">{esc(an_en)}</p>'
        if an_uk:
            body += f'\n      <p class="qanalysis qanalysis-uk">{esc(an_uk)}</p>'
        return f"""
    <div class="quote-today">
      <div class="qmark">&ldquo;</div>{body}
      <div class="qdate">{dt}</div>
    </div>"""

    en, uk, author = single_parts(entry)
    primary = esc(uk or en)
    secondary = f'\n      <p class="quote-alt">&ldquo;{esc(en)}&rdquo;</p>' if (uk and en) else ""
    author_html = f'\n      <div class="qauthor">&mdash; {esc(author)}</div>' if author else ""
    return f"""
    <div class="quote-today">
      <div class="qmark">&ldquo;</div>
      <p>{primary}</p>{secondary}{author_html}
      <div class="qdate">{dt}</div>
    </div>"""


def render_history_item(entry):
    dt = format_date(entry.get("date") if isinstance(entry, dict) else None)

    if is_themed(entry):
        body = ""
        subject = subject_line(entry)
        if subject:
            body += f'\n          <div class="qh-subject">{esc(subject)}</div>'
        for en, uk, author in quote_items(entry):
            if uk:
                body += f'\n          <p>&laquo;{esc(uk)}&raquo;</p>'
            if en:
                cls = ' class="qh-alt"' if uk else ""
                body += f'\n          <p{cls}>&ldquo;{esc(en)}&rdquo;</p>'
            if author:
                body += f'\n          <div class="qh-meta">&mdash; {esc(author)}</div>'
        return f"""
        <div class="qh-item">{body}
          <div class="qh-meta">{dt}</div>
        </div>"""

    en, uk, author = single_parts(entry)
    alt = f'\n          <p class="qh-alt">&ldquo;{esc(en)}&rdquo;</p>' if (uk and en) else ""
    meta = dt
    if author:
        meta = (meta + " &middot; " if meta else "") + esc(author)
    return f"""
        <div class="qh-item">
          <p>&ldquo;{esc(uk or en)}&rdquo;</p>{alt}
          <div class="qh-meta">{meta}</div>
        </div>"""


def build_html(history):
    """Returns (html, usable_count). html is None when it would be destructive."""
    usable = [e for e in history if renderable(e)]
    skipped = len(history) - len(usable)
    if skipped:
        print(f"Skipped {skipped} unrenderable entr"
              f"{'y' if skipped == 1 else 'ies'}.")
        for i, e in enumerate(history):
            if not renderable(e):
                shape = sorted(e.keys()) if isinstance(e, dict) else type(e).__name__
                print(f"  unrenderable[{i}]: {shape}")

    if not usable:
        return (EMPTY_STATE if not history else None), 0

    featured = render_featured(usable[-1])
    older = list(reversed(usable[:-1]))[:HISTORY_DISPLAY_LIMIT]
    if not older:
        return featured, len(usable)

    noun = "theme" if sum(1 for e in older if is_themed(e)) >= len(older) / 2 else "quote"
    items = "".join(render_history_item(e) for e in older)
    history_html = f"""
    <details class="quote-history">
      <summary>See {len(older)} earlier {noun}{'s' if len(older) != 1 else ''} &#9662;</summary>{items}
    </details>"""
    return featured + history_html, len(usable)


EXTRA_CSS = """
.quote-today .quote-alt { font-family:'Poppins',sans-serif; font-size:15px; line-height:1.5;
  color:var(--sub); margin:-4px 0 12px; font-style:italic; }
.qh-item .qh-alt { font-family:'Poppins',sans-serif; font-size:13px; line-height:1.45;
  color:var(--sub); margin:2px 0 4px; font-style:italic; }
"""


def ensure_css(site_html):
    if ".quote-alt" in site_html:
        return site_html
    close = site_html.find("</style>")
    if close == -1:
        print("WARNING: no </style> found, skipping CSS injection.")
        return site_html
    print("Injected bilingual quote CSS.")
    return site_html[:close] + EXTRA_CSS + site_html[close:]


def main():
    with open(STATE_PATH, encoding="utf-8") as f:
        history = json.load(f).get("history", [])

    new_block, usable_count = build_html(history)

    if new_block is None:
        print(
            f"ABORTING without writing: {len(history)} history entries exist but none "
            "could be rendered. Refusing to overwrite the live page with an empty "
            "placeholder. Fix the entry-shape handling above, then re-run.",
            file=sys.stderr,
        )
        sys.exit(1)

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
    print(f"Updated {SITE_PATH}: rendered {usable_count} of {len(history)} history entries.")


if __name__ == "__main__":
    main()
