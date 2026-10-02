# Handoff

## 2026-10-02: daily quote approval flow
**Done**
- Fixed the relay. `poll_messages.py` had been crashing on every run since Sep 20 (`telegram_utils` was missing `get_updates`/`describe_message`). Brother's messages weren't reaching Denys during that time.
- Replaced the auto-send with a daily approval card (`approval.py`, `bot_brain.py`). Buttons: ✅ Send today / ⏭ Not today / 🚫 Never (with undo) / 🔄 Another.
  - Each card shows the offer count and last sent date. Nothing sent within 90 days is offered.
  - 6pm reminder; if he still doesn't approve, nothing is sent that day.
- Article lines come from RSS plus Groq, with a check that each quote appears word for word in its article (`articles.py`, `article_sources.json`). Bare timeless quotes get a subject and takeaway the first time they're offered.
- Instant mode: Vercel project `quote-relay` (STOA29) → repository_dispatch → `quote.yml`. Fallback: `poll.yml` (only while no webhook is set) and backup ticks in `quote.yml`.
- Removed `send_quote.py` (an auto-sender that bypassed approval). Quote queuing was dropped from `schedule.json`; habits are unchanged.
- GitHub-only mode hardened: hourly backup ticks (card from 7am), taps drained on every tick, and a 15-minute listen window after each card or reminder.
- Relay needs only GH_TOKEN now: the webhook secret is checked on GitHub, and there's a /ping self-test (`webhook.yml` → test).
- 57 tests (`python -m pytest -q`). actionlint clean. Timeouts and rebase-before-push added to all workflows (CI-BUDGET-01).

- Instant mode LIVE (Oct 2): webhook → quote-relay → GitHub. The self-test /ping round trip took about 11s. GH_TOKEN is set in Vercel.
- Removed the `poll.yml` schedule (CI-BUDGET-02); it's dispatch-only now.

**Waiting on Denys**
- GitHub secret `GROQ_API_KEY` (same key knowledge-bot uses). Until it's set, cards are timeless quotes only.
- Optional: `BOT_TOKEN` in Vercel for an instant "Sending…" toast on taps.

**Next**
- After GROQ_API_KEY: run Quote bot → `articles`, check feed health in `/stats`, and drop dead feeds from `article_sources.json`.
- Note the GH_TOKEN expiry date here when it's created.
