# Toronto Countdown Bot

Sends your brother a daily "days left" message in Telegram until Aug 9, 2026.

## Setup (10 minutes)

1. **Create the bot**
   - Open Telegram, message [@BotFather](https://t.me/BotFather)
   - Send `/newbot`, follow the prompts, name it whatever (e.g. `TorontoCountdownBot`)
   - Copy the **token** it gives you (looks like `123456:ABC-DEF...`)

2. **Get your brother's chat ID**
   - Have your brother open Telegram and send `/start` (or any message) to your new bot
   - In a browser, visit:
     `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
   - Find `"chat":{"id":XXXXXXXXX` in the response — that number is his `CHAT_ID`

3. **Put this on GitHub**
   - Create a new repo, upload everything in this `countdown_bot` folder
     (keep the `.github/workflows/countdown.yml` path exactly as-is)
   - Go to repo **Settings → Secrets and variables → Actions**
   - Add two secrets:
     - `BOT_TOKEN` — the token from step 1
     - `CHAT_ID` — the number from step 2

4. **Test it**
   - Go to the **Actions** tab → "Send daily countdown" → **Run workflow**
   - Check Telegram — your brother should get the message within a few seconds

That's it. It'll now run automatically every day at 9am Toronto time until the
flight date, with no server, no laptop needing to stay on, nothing to maintain.

## Changing things later
- **Flight date**: edit `FLIGHT_DATE` in `send_countdown.py`
- **Send time**: edit the `cron` line in `.github/workflows/countdown.yml`
  (time is in UTC)
- **Message wording**: edit `build_message()` in `send_countdown.py`
