# Toronto Countdown Bot (v3 — admin/customer roles)

Two roles now:
- **CUSTOMER** (your brother) — receives the daily countdown photo
- **ADMIN** (you) — gets a copy of everything sent to him, plus a report
  whenever he sends *anything* to the bot

## Honest limits, read this first
- Telegram's Bot API does **not** give bots read receipts. This setup can
  tell you "the message was successfully delivered to Telegram's servers
  for his chat" — it cannot tell you if he opened or read it. No bot setup
  can do that; it's a platform limitation, not something more code fixes.
- "He typed something" is checked **every 5 minutes**, not instantly —
  there's no always-on server here, so it's near-real-time rather than
  live.
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
