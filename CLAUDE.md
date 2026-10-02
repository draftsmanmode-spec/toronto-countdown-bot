# toronto-countdown-bot

Telegram bot for Denys's brother: a daily quote (approval-gated), a weekly habit, a two-way relay, and a GitHub Pages site (`docs/index.html`). Public repo: Actions minutes are free. State lives in JSON files the workflows commit back.

## How the daily quote works
- `approval.py`: the engine. It builds the pool (`quotes.json` themes, `quotes_flat_pending.json` timeless quotes, `articles.json` article lines). It sends Denys one card each morning with buttons (✅ Send today / ⏭ Not today / 🚫 Never / 🔄 Another) and records state in `approval_state.json`. Items have content-hash ids (`t-`, `q-`, `a-`).
- Rules: nothing sent in the last 90 days is offered, an item that was passed on rests 5 days, and fresh articles alternate with the timeless library. A reminder goes out at 6pm Toronto; if he still doesn't tap ✅, nothing is sent that day.
- `articles.py`: RSS (`article_sources.json`) plus Groq `openai/gpt-oss-120b`. A quote must appear word for word in the article or it is rejected. It also adds a subject and analysis to bare timeless quotes, cached in `approval_state.json` → `enriched`.
- `bot_brain.py`: single entry point for taps, messages, commands (`/today /stats /schedule /help`) and the daily tick.
- Sends are logged to `quote_state.json` history, which `update_site.py` renders.

## Event paths
- Instant mode: Telegram → Vercel project `quote-relay` (`vercel/api/telegram.py`, team STOA29) → `repository_dispatch` → `.github/workflows/quote.yml`. A Vercel cron (`vercel/api/tick.py`) fires `daily_tick` at 12:00 and 22:00 UTC.
- GitHub-only mode (no webhook): `quote.yml` runs hourly backup ticks (`17 * * * *`, idempotent; GitHub starts them hours late). Each tick first drains waiting taps (`bot_brain.drain`, offset in `state.json`) and long-polls for 15 minutes after sending a card or reminder. `poll.yml` drains too, every few hours. All of this is skipped when a webhook is set.
- `webhook.yml` connects or disconnects the Telegram webhook. Its secret is derived from BOT_TOKEN, and both sides must match.
- State-changing runs share the concurrency group `bot-state` and check out `ref: main`.
- Dates are Toronto-local (`approval.TZ`), not UTC.

## Checks
- `pip install -r requirements-dev.txt && BOT_TOKEN=x python -m pytest -q` (fake Telegram, temp copies of the data).
- `actionlint .github/workflows/*.yml` after any workflow edit.
- No CI on push (budget). Run the checks locally before pushing.

## Deploying the Vercel relay
It isn't git-connected. Redeploy changes in `vercel/` via the Vercel connector (`create_deployment` with the files inline, project `quote-relay`, target production). Env vars: GH_TOKEN (required; fine-grained, this repo, Contents RW), CRON_SECRET, GH_REPO. BOT_TOKEN and ADMIN_CHAT_ID are optional (instant tap toast and failure alerts). The webhook secret is checked on GitHub in `bot_brain.dispatched_update`. `webhook.yml` mode `test` sends a fake /ping through the whole chain.

## Don't
- Don't hand-edit `approval_state.json`, `state.json` or `quote_state.json` while workflows run. Use the bot commands.
- Don't print message text in workflow logs. The repo is public.

## Session kickoff
Skills: `anthropic-skills:actions-budget` (before touching workflows), `anthropic-skills:push-budget` (before pushing).
