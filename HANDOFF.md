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
- 52 tests (`python -m pytest -q`). actionlint clean. Timeouts and rebase-before-push added to all workflows (CI-BUDGET-01).

**Waiting on Denys (one-time setup)**
1. GitHub fine-grained token: this repo only, Contents read/write.
2. Vercel → quote-relay → Environment Variables: `BOT_TOKEN`, `GH_TOKEN`, `ADMIN_CHAT_ID`. Then redeploy.
3. GitHub secret `GROQ_API_KEY` (same key knowledge-bot uses).
4. Then run Actions → "Telegram webhook" → connect, with `https://quote-relay-stoa29.vercel.app`.

**Next**
- After setup: confirm one tap round-trip and check feed health in `/stats`. Drop dead feeds from `article_sources.json`.
- Once instant mode is proven: remove the `*/5` schedule from `poll.yml` (keep workflow_dispatch). Hourly ticks can stay; they cost nothing on a public repo.
- Note the GH_TOKEN expiry date here when it's created.
