"""
Sends a one-off custom message to your brother (CUSTOMER_CHAT_ID), typed in
at trigger time via the GitHub Actions "Run workflow" dialog - no need to
wait for the 5-minute poll relay or edit any code.

Reports a copy to you (ADMIN_CHAT_ID) automatically, same as the daily
countdown script does.

Required repo secrets (already exist from earlier setup):
  BOT_TOKEN
  ADMIN_CHAT_ID
  CUSTOMER_CHAT_ID

Message text comes from the MESSAGE_TEXT environment variable, which the
workflow fills in from the manual trigger's input field.
"""

import os
import sys

from telegram_utils import send_text

ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID")
CUSTOMER_CHAT_ID = os.environ.get("CUSTOMER_CHAT_ID", "").strip()
MESSAGE_TEXT = os.environ.get("MESSAGE_TEXT", "").strip()


def main():
    if not os.environ.get("BOT_TOKEN") or not ADMIN_CHAT_ID:
        print("Missing BOT_TOKEN or ADMIN_CHAT_ID.", file=sys.stderr)
        sys.exit(1)

    if not CUSTOMER_CHAT_ID:
        print("CUSTOMER_CHAT_ID isn't set - nothing to send to.", file=sys.stderr)
        sys.exit(1)

    if not MESSAGE_TEXT:
        print("MESSAGE_TEXT is empty - nothing to send.", file=sys.stderr)
        sys.exit(1)

    send_text(CUSTOMER_CHAT_ID, MESSAGE_TEXT)
    print("Sent to customer:", MESSAGE_TEXT)

    send_text(ADMIN_CHAT_ID, f"\U0001F4E4 Sent to your brother just now:\n\n{MESSAGE_TEXT}")
    print("Sent report to admin.")


if __name__ == "__main__":
    main()
