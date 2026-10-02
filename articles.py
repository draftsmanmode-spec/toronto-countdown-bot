"""
Pulls fresh "latest article" candidates for the daily approval card.

Once a day (before the morning card) it reads the RSS feeds listed in
article_sources.json, takes the newest unseen post from each, and asks
Groq (free tier) to pick ONE quotable line from it, translate it into
Ukrainian and add a two-sentence takeaway. Results land in articles.json,
which approval.py reads as part of the pool.

Guard against made-up quotes: the line Groq returns must appear word for
word in the article text, or it is thrown away. Nothing reaches your
brother without your ✅ anyway, but you shouldn't have to fact-check.

It also exposes enrich_item(), used by approval.py to give bare timeless
quotes a short subject and takeaway the first time they're offered.

Env:
  GROQ_API_KEY   required; without it this script exits quietly
Usage:
  python articles.py            # skips if checked in the last 20 hours
  python articles.py --force    # check now
"""

import json
import os
import random
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser

import requests

import approval

SOURCES_PATH = "article_sources.json"
ARTICLES_PATH = approval.ARTICLES_PATH

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "openai/gpt-oss-120b"
USER_AGENT = "Mozilla/5.0 (compatible; daily-quote-bot/1.0)"

MAX_NEW_PER_RUN = 3        # Groq free tier: 8k tokens/min, so keep runs small
MAX_ATTEMPTS_PER_RUN = 6
MAX_AGE_DAYS = 14          # older posts aren't "latest"
REFRESH_HOURS = 20
ARTICLE_CHARS = 6000       # ~1.5k tokens of article per call
KEEP_ITEMS = 300
KEEP_SEEN_DAYS = 180

NS = {
    "content": "http://purl.org/rss/1.0/modules/content/",
    "dc": "http://purl.org/dc/elements/1.1/",
    "atom": "http://www.w3.org/2005/Atom",
}


# ---------- HTML -> text ----------

class _TextExtractor(HTMLParser):
    """Collects readable text; with paragraphs_only it keeps <p>/<blockquote>/<li> only."""

    BLOCK = {"p", "br", "li", "blockquote", "h1", "h2", "h3", "h4", "div", "tr"}
    KEEP = {"p", "blockquote", "li"}
    SKIP = {"script", "style", "noscript", "nav", "footer", "header", "form", "aside"}

    def __init__(self, paragraphs_only=False):
        super().__init__(convert_charrefs=True)
        self.paragraphs_only = paragraphs_only
        self.parts = []
        self.skip_depth = 0
        self.keep_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip_depth += 1
        if tag in self.KEEP:
            self.keep_depth += 1
        if tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip_depth:
            self.skip_depth -= 1
        if tag in self.KEEP and self.keep_depth:
            self.keep_depth -= 1
        if tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if self.skip_depth:
            return
        if self.paragraphs_only and not self.keep_depth:
            return
        self.parts.append(data)

    def text(self):
        raw = "".join(self.parts)
        raw = re.sub(r"[ \t\r\f\v]+", " ", raw)
        return re.sub(r"\n\s*\n+", "\n\n", raw).strip()


def html_to_text(html: str, paragraphs_only=False) -> str:
    parser = _TextExtractor(paragraphs_only)
    try:
        parser.feed(html or "")
        parser.close()
    except Exception:  # noqa: BLE001 - malformed HTML still yields partial text
        pass
    return parser.text()


# ---------- feeds ----------

def _parse_date(value: str):
    if not value:
        return None
    value = value.strip()
    try:
        return parsedate_to_datetime(value).date()
    except (TypeError, ValueError, IndexError):
        pass
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _t(el, path):
    found = el.find(path, NS)
    return (found.text or "").strip() if found is not None and found.text else ""


def parse_feed(xml_bytes: bytes) -> list:
    """Posts from an RSS 2.0 or Atom feed: title, link, published, author, html."""
    root = ET.fromstring(xml_bytes)
    posts = []
    for item in root.iter("item"):
        posts.append({
            "title": _t(item, "title"),
            "link": _t(item, "link"),
            "published": _parse_date(_t(item, "pubDate") or _t(item, "dc:date")),
            "author": _t(item, "dc:creator") or _t(item, "author"),
            "html": _t(item, "content:encoded") or _t(item, "description"),
        })
    for entry in root.iter(f"{{{NS['atom']}}}entry"):
        link = ""
        for l in entry.findall("atom:link", NS):
            if l.get("rel", "alternate") == "alternate":
                link = l.get("href", "")
                break
        posts.append({
            "title": _t(entry, "atom:title"),
            "link": link,
            "published": _parse_date(_t(entry, "atom:published") or _t(entry, "atom:updated")),
            "author": _t(entry, "atom:author/atom:name"),
            "html": _t(entry, "atom:content") or _t(entry, "atom:summary"),
        })
    return [p for p in posts if p["link"] and p["title"]]


def fetch(url: str) -> requests.Response:
    resp = requests.get(url, timeout=25, headers={"User-Agent": USER_AGENT})
    resp.raise_for_status()
    return resp


def article_text(post: dict) -> str:
    text = html_to_text(post.get("html") or "")
    if len(text) >= 1500:
        return text
    try:
        page = fetch(post["link"]).text
        full = html_to_text(page, paragraphs_only=True)
        if len(full) > len(text):
            return full
    except requests.RequestException as exc:
        print(f"  (couldn't open the full article: {exc})")
    return text


# ---------- Groq ----------

class GroqError(RuntimeError):
    pass


def groq_json(system: str, user: str) -> dict:
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        raise GroqError("GROQ_API_KEY not set")
    body = {
        "model": GROQ_MODEL,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "temperature": 0.3,
        "max_completion_tokens": 1500,
        "response_format": {"type": "json_object"},
        "reasoning_effort": "low",
    }
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    for attempt in range(3):
        resp = requests.post(GROQ_URL, json=body, headers=headers, timeout=60)
        if resp.status_code == 429 and attempt < 2:
            wait = float(resp.headers.get("retry-after") or 20)
            print(f"  Groq rate limit, waiting {wait:.0f}s")
            time.sleep(min(wait, 45))
            continue
        if resp.status_code == 400 and attempt == 0 and "reasoning_effort" in body:
            # older/other models reject the optional knobs - retry plain
            body.pop("reasoning_effort", None)
            body.pop("response_format", None)
            continue
        if resp.status_code >= 400:
            raise GroqError(f"HTTP {resp.status_code}: {resp.text[:200]}")
        content = resp.json()["choices"][0]["message"]["content"] or ""
        return _parse_json_reply(content)
    raise GroqError("gave up after retries")


def _parse_json_reply(content: str) -> dict:
    content = content.strip()
    content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content)
    start, end = content.find("{"), content.rfind("}")
    if start == -1 or end == -1:
        raise GroqError(f"no JSON in reply: {content[:120]!r}")
    return json.loads(content[start:end + 1])


EXTRACT_SYSTEM = """You pick ONE line of practical wisdom a day for a man who reads it in English and Ukrainian. He cares about resilience, discipline, relationships, money, health and timeless philosophy.

From the article you are given, choose the single most quotable passage. Rules:
- Copy it EXACTLY, character for character, from the article text. Do not fix, shorten or merge sentences.
- 10 to 45 words. It must make sense on its own, without the article.
- No questions, no calls to action, no promotion, no list fragments, no statistics without meaning.
- If the article itself quotes someone, the author is that person. Otherwise it is the article's author.
- If nothing in the article meets these rules, reply {"skip": true}.

Otherwise reply with JSON only:
{"skip": false,
 "quote": "<exact passage>",
 "author": "<name>",
 "subject": "<2-4 word theme in English, Title Case>",
 "subject_uk": "<the theme in Ukrainian>",
 "quote_uk": "<natural, modern Ukrainian translation of the passage>",
 "analysis_en": "<2 short sentences: what it means and how to use it this week. Plain words, no fluff.>",
 "analysis_uk": "<the same two sentences in natural Ukrainian>"}"""


ENRICH_SYSTEM = """You add context to a famous quote for a daily bilingual (English/Ukrainian) message about practical wisdom. Do not change or re-translate the quote, and do not guess an author.

Reply with JSON only:
{"subject": "<2-4 word theme in English, Title Case>",
 "subject_uk": "<the theme in Ukrainian>",
 "analysis_en": "<2 short sentences: what it means and how to use it this week. Plain words, no fluff.>",
 "analysis_uk": "<the same two sentences in natural Ukrainian>"}"""


def _clean(s) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip()


def is_verbatim(quote: str, text: str) -> bool:
    q, t = approval.norm_text(quote), approval.norm_text(text)
    return len(q.split()) >= 6 and q in t


def extract(post: dict, source: dict, text: str) -> dict | None:
    """Ask Groq for one line; return an article item, or None if nothing qualifies."""
    author_hint = post.get("author") or source.get("author") or source["name"]
    user = (f"Source: {source['name']}\nArticle author: {author_hint}\n"
            f"Title: {post['title']}\n\nArticle text:\n{text[:ARTICLE_CHARS]}")
    reply = groq_json(EXTRACT_SYSTEM, user)
    if reply.get("skip"):
        print("  Groq found nothing quotable.")
        return None

    quote = _clean(reply.get("quote"))
    if not is_verbatim(quote, text):
        print(f"  Rejected: not word-for-word in the article: {quote[:80]!r}")
        return None
    if len(quote.split()) > 60:
        print("  Rejected: too long.")
        return None
    needed = ("quote_uk", "subject", "subject_uk", "analysis_en", "analysis_uk")
    if not all(_clean(reply.get(k)) for k in needed):
        print("  Rejected: reply missing fields.")
        return None

    today = date.today().isoformat()
    return {
        "id": "a-" + approval.short_hash(post["link"]),
        "url": post["link"],
        "title": _clean(post["title"]),
        "source": source["name"],
        "published": (post["published"] or date.today()).isoformat(),
        "fetched": today,
        "subject": _clean(reply["subject"]),
        "subject_uk": _clean(reply["subject_uk"]),
        "quotes": [{
            "text": quote,
            "text_uk": _clean(reply["quote_uk"]),
            "author": _clean(reply.get("author")) or author_hint,
        }],
        "analysis_en": _clean(reply["analysis_en"]),
        "analysis_uk": _clean(reply["analysis_uk"]),
    }


def enrich_item(item: dict) -> dict | None:
    """Subject + takeaway for a bare timeless quote. Returns None without a Groq key."""
    if not os.environ.get("GROQ_API_KEY"):
        return None
    q = item["quotes"][0]
    user = (f"Quote: {q['text']}\nAuthor: {q.get('author') or 'unknown'}\n"
            f"Ukrainian version already used: {q.get('text_uk') or '(none)'}")
    reply = groq_json(ENRICH_SYSTEM, user)
    out = {k: _clean(reply.get(k)) for k in ("subject", "subject_uk", "analysis_en", "analysis_uk")}
    return out if all(out.values()) else None


# ---------- main ----------

def refresh(force=False, now=None) -> dict:
    now = now or datetime.now(timezone.utc)
    data = approval.load_json(ARTICLES_PATH, {})
    data.setdefault("seen", {})
    data.setdefault("items", [])
    data.setdefault("feeds", {})

    last = data.get("fetched_at")
    if not force and last:
        try:
            if now - datetime.fromisoformat(last) < timedelta(hours=REFRESH_HOURS):
                print(f"Articles checked at {last}; skipping (use --force).")
                return data
        except ValueError:
            pass

    if not os.environ.get("GROQ_API_KEY"):
        print("GROQ_API_KEY not set - skipping article refresh.")
        return data

    sources = approval.load_json(SOURCES_PATH, [])
    random.shuffle(sources)
    cutoff = date.today() - timedelta(days=MAX_AGE_DAYS)
    known_ids = {i["id"] for i in data["items"]}
    added = attempts = 0

    for source in sources:
        if added >= MAX_NEW_PER_RUN or attempts >= MAX_ATTEMPTS_PER_RUN:
            break
        name = source["name"]
        try:
            posts = parse_feed(fetch(source["url"]).content)
            data["feeds"][name] = {"ok": True, "at": now.isoformat(timespec="minutes"), "posts": len(posts)}
        except Exception as exc:  # noqa: BLE001 - one dead feed must not stop the rest
            data["feeds"][name] = {"ok": False, "at": now.isoformat(timespec="minutes"), "error": str(exc)[:160]}
            print(f"{name}: feed failed: {exc}")
            continue

        fresh = [p for p in posts
                 if p["link"] not in data["seen"]
                 and (p["published"] is None or p["published"] >= cutoff)]
        fresh.sort(key=lambda p: p["published"] or date.min, reverse=True)
        if not fresh:
            print(f"{name}: nothing new.")
            continue

        post = fresh[0]
        attempts += 1
        print(f"{name}: {post['title']!r}")
        text = article_text(post)
        if len(text) < 400:
            print("  Too little text to work with.")
            data["seen"][post["link"]] = date.today().isoformat()
            continue
        try:
            item = extract(post, source, text)
        except (GroqError, requests.RequestException, ValueError) as exc:
            print(f"  Groq call failed, will retry next run: {exc}")
            continue
        data["seen"][post["link"]] = date.today().isoformat()
        if item and item["id"] not in known_ids:
            data["items"].append(item)
            known_ids.add(item["id"])
            added += 1
            print(f"  Added: {item['quotes'][0]['text'][:90]!r}")

    seen_cutoff = (date.today() - timedelta(days=KEEP_SEEN_DAYS)).isoformat()
    data["seen"] = {u: d for u, d in data["seen"].items() if d >= seen_cutoff}
    data["items"] = data["items"][-KEEP_ITEMS:]
    data["fetched_at"] = now.isoformat(timespec="minutes")
    approval.save_json(ARTICLES_PATH, data)
    ok = sum(1 for f in data["feeds"].values() if f.get("ok"))
    print(f"Done: {added} new article line(s); {ok}/{len(data['feeds'])} feeds reachable.")
    return data


if __name__ == "__main__":
    refresh(force="--force" in sys.argv)
