from datetime import date

import articles

ARTICLE = (
    "<p>Most people think discipline is about willpower.</p>"
    "<p>The truth is quieter: you become what you repeatedly do when nobody is "
    "watching, and the results arrive long after the effort.</p>"
    "<p>Subscribe to our newsletter!</p>"
) * 3

RSS = f"""<?xml version="1.0"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/"
     xmlns:dc="http://purl.org/dc/elements/1.1/">
<channel><title>FS</title>
<item><title>On Discipline</title><link>https://fs.blog/discipline/</link>
<pubDate>Tue, 29 Sep 2026 10:00:00 +0000</pubDate><dc:creator>Shane Parrish</dc:creator>
<content:encoded><![CDATA[{ARTICLE}]]></content:encoded></item>
</channel></rss>""".encode()

ATOM = b"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"><title>Blog</title>
<entry><title>Atom Post</title><link rel="alternate" href="https://example.com/a"/>
<published>2026-09-30T08:00:00Z</published><author><name>Jane Doe</name></author>
<content type="html">&lt;p&gt;Hello there&lt;/p&gt;</content></entry>
</feed>"""

SOURCE = {"name": "Farnam Street", "url": "https://fs.blog/feed/", "author": "Shane Parrish"}


def test_parse_rss_and_atom():
    [post] = articles.parse_feed(RSS)
    assert post["title"] == "On Discipline"
    assert post["published"] == date(2026, 9, 29)
    assert post["author"] == "Shane Parrish"
    assert "nobody is" in articles.html_to_text(post["html"])

    [entry] = articles.parse_feed(ATOM)
    assert entry["link"] == "https://example.com/a"
    assert entry["author"] == "Jane Doe" and entry["published"] == date(2026, 9, 30)


def test_verbatim_check_tolerates_typography_only():
    text = articles.html_to_text(ARTICLE)
    good = "The truth is quieter: you become what you repeatedly do when nobody is watching"
    assert articles.is_verbatim(good.replace(":", " —"), text)
    assert not articles.is_verbatim("You become what you do every single day without fail", text)


def reply(**overrides):
    base = {
        "skip": False,
        "quote": "you become what you repeatedly do when nobody is watching, and the results arrive long after the effort.",
        "author": "Shane Parrish",
        "subject": "Quiet Discipline", "subject_uk": "Тиха дисципліна",
        "quote_uk": "ти стаєш тим, що робиш, коли ніхто не бачить.",
        "analysis_en": "One. Two.", "analysis_uk": "Один. Два.",
    }
    base.update(overrides)
    return base


def test_extract_accepts_a_verbatim_line(monkeypatch):
    [post] = articles.parse_feed(RSS)
    monkeypatch.setattr(articles, "groq_json", lambda s, u: reply())
    item = articles.extract(post, SOURCE, articles.html_to_text(post["html"]))
    assert item["id"].startswith("a-") and item["source"] == "Farnam Street"
    assert item["quotes"][0]["author"] == "Shane Parrish"
    assert item["published"] == "2026-09-29"


def test_extract_rejects_an_invented_line(monkeypatch):
    [post] = articles.parse_feed(RSS)
    monkeypatch.setattr(articles, "groq_json",
                        lambda s, u: reply(quote="Discipline is the bridge between goals and accomplishment."))
    assert articles.extract(post, SOURCE, articles.html_to_text(post["html"])) is None


def test_extract_respects_skip(monkeypatch):
    [post] = articles.parse_feed(RSS)
    monkeypatch.setattr(articles, "groq_json", lambda s, u: {"skip": True})
    assert articles.extract(post, SOURCE, articles.html_to_text(post["html"])) is None


def test_refresh_without_key_is_a_quiet_no_op(repo):
    data = articles.refresh(force=True)
    assert data["items"] == []
    assert not (repo / "articles.json").exists()


def test_json_reply_parsing():
    assert articles._parse_json_reply('```json\n{"a": 1}\n```') == {"a": 1}
    assert articles._parse_json_reply('Sure! {"skip": true}') == {"skip": True}
