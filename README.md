# Toronto Countdown Bot

## Daily quote: you approve, then he receives

Every morning (~8am Toronto) you get one candidate on Telegram:

```
🗳 Today's pick · Fri, Oct 2
📰 Fresh article · Farnam Street · Sep 29      (or 🏛 Timeless library · Seneca)
🔁 Offered 2× before (last Sep 14) · 📤 Never sent
🧮 Pool: 118 ready · 3 fresh articles
━━━━━━━━━━━━
<exactly what your brother will get, English + Ukrainian>

[✅ Send today] [⏭ Not today]
[🚫 Never send] [🔄 Another]
```

- **✅ Send today**: goes to him right away and onto the website.
- **⏭ Not today**: nothing is sent today. The item rests 5 days, then may come back.
- **🚫 Never send**: banned for good (there's an undo button). Another candidate is offered straight away.
- **🔄 Another**: swaps in a different one. Fresh articles and timeless quotes take turns.
- Anything sent in the last 90 days is never offered.
- No tap by ~6pm: one reminder. Still nothing: nothing goes out that day.
- Commands: `/today` (show today's pick, or reopen a skipped day), `/stats`, `/schedule`, `/help`.

Sources: `quotes.json` (themes), `quotes_flat_pending.json` (timeless quotes), and fresh article lines in `articles.json`. Those come from the feeds in `article_sources.json`, read by free Groq AI. A line is only kept if it appears word for word in the article.

### One-time setup for instant buttons
Button taps reach GitHub through a tiny Vercel relay (`vercel/`, project `quote-relay`):
1. GitHub → Settings → Developer settings → Fine-grained tokens → new token. Only this repo, **Contents: Read and write**.
2. Vercel → quote-relay → Settings → Environment Variables: add `BOT_TOKEN`, `GH_TOKEN` (the token above) and `ADMIN_CHAT_ID`. Then redeploy.
3. This repo → Settings → Secrets → Actions: add `GROQ_API_KEY`.
4. Actions → **Telegram webhook** → Run workflow → `connect`, url `https://quote-relay-stoa29.vercel.app`.

Without step 4, everything still works through GitHub alone, just slower. The card comes from about 7am, whenever GitHub gets to it. A tap within 15 minutes of the card works right away; later taps are picked up within about an hour.
To go back to that mode: same workflow, `disconnect`.

---

## Countdown, relay and roles (v3)

Two roles now:
- **CUSTOMER** (your brother) — receives the daily countdown photo
- **ADMIN** (you) — gets a copy of everything sent to him, plus a report
  whenever he sends *anything* to the bot

## Honest limits, read this first
- Telegram's Bot API does **not** give bots read receipts. This setup can
  tell you "the message was successfully delivered to Telegram's servers
  for his chat" — it cannot tell you if he opened or read it. No bot setup
  can do that; it's a platform limitation, not something more code fixes.
- "He typed something" reaches you within seconds once the Vercel relay
  is connected (see the quote section above). Without it, GitHub's
  "every 5 minutes" poll really runs every few hours.
- Worth actually telling your brother the bot works this way, so it's not
  a surprise later.

## What's new vs. v2
- `telegram_utils.py` — shared helper functions
- `send_countdown.py` — now sends to `CUSTOMER_CHAT_ID` **and** reports a
  copy to `ADMIN_CHAT_ID`
- `poll_messages.py` — new, checks for new messages from your brother and
  forwards a summary to you
- `.github/workflows/poll.yml` — new workflow, runs every 5 minutes
- `state.json` — tracks which messages have already been reported (the
  poll workflow commits updates to this file automatically — don't edit
  it by hand)

## Setup

### 1. Upload/replace these files in your repo
Replace: `send_countdown.py`, `.github/workflows/countdown.yml`
Add new: `telegram_utils.py`, `poll_messages.py`,
`.github/workflows/poll.yml`, `state.json`
(`docs/index.html` and `capture_countdown.py` are unchanged from v2 — no
need to re-upload if already there)

### 2. Rename your secret
- Go to Settings → Secrets and variables → Actions
- Your existing `CHAT_ID` secret was you (for testing) — add a new secret
  called `ADMIN_CHAT_ID` with that same value
- You can delete the old `CHAT_ID` secret once `ADMIN_CHAT_ID` is added,
  it's no longer used

### 3. Add your brother's chat ID
- Once he has messaged the bot at least once, get his chat ID the same way
  as before (`getUpdates`)
- Add it as a new secret called `CUSTOMER_CHAT_ID`
- Until this secret exists, the daily send will go to you only, with a
  warning in the message — nothing breaks, it just waits for you

### 4. Allow the poll workflow to save its progress
- Settings → Actions → General → scroll to "Workflow permissions"
- Select **"Read and write permissions"** → Save
- (Without this, `poll.yml` can't commit `state.json` back and will fail
  on the last step)

### 5. Test both workflows
- Actions tab → "Send daily countdown" → Run workflow
  → you should get a normal countdown message (with the "only sent to
  you" warning until `CUSTOMER_CHAT_ID` is set)
- Actions tab → "Poll for brother's messages" → Run workflow
  → check the logs; if `CUSTOMER_CHAT_ID` isn't set yet it'll just print
  "nothing to poll for" and exit cleanly, that's expected

## Changing things later
- **Poll frequency**: the `cron` line in `.github/workflows/poll.yml`
  (more frequent = more Actions minutes used, though this is free on a
  public repo)
- **What counts as "received"**: `send_countdown.py` already reports every
  send to you automatically, nothing to change there
- **Message wording**: `build_caption()` in `send_countdown.py`, or the
  report text in `poll_messages.py`
