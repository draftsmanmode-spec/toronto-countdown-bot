"""
One-off: sends two birthday photos + a Ukrainian birthday poem to your
brother (CUSTOMER_CHAT_ID), then reports a copy to you (ADMIN_CHAT_ID).

Required repo secrets (already exist):
  BOT_TOKEN
  ADMIN_CHAT_ID
  CUSTOMER_CHAT_ID

Photos live in birthday/photo1.png and birthday/photo2.png in this repo.
"""

import os
import sys

from telegram_utils import send_photo, send_text

ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID")
CUSTOMER_CHAT_ID = os.environ.get("CUSTOMER_CHAT_ID", "").strip()

POEM = (
    "Братику мій, з Днем народження вітаю,\n"
    "Козацький дух тобі від брата дарую!\n"
    "Хай серце буде хоробре й завзяте,\n"
    "А мрії збуваються, наче крилаті.\n"
    "\n"
    "Ти ростеш сильним, добрим і чесним,\n"
    "Пишаюсь тобою — це щастя безмежне.\n"
    "За два тижні вже мчу до тебе в гості,\n"
    "Обійняти міцно, як справжні браття прості.\n"
    "\n"
    "Люблю тебе дуже, більше за слова,\n"
    "Хай доля твоя буде щедра й ясна.\n"
    "З Днем народження, брате, будь щасливим,\n"
    "Козацького духу тобі — незламним і вірним!"
)

PHOTO_1 = "birthday/photo1.png"
PHOTO_2 = "birthday/photo2.png"


def main():
    if not os.environ.get("BOT_TOKEN") or not ADMIN_CHAT_ID:
        print("Missing BOT_TOKEN or ADMIN_CHAT_ID.", file=sys.stderr)
        sys.exit(1)

    if not CUSTOMER_CHAT_ID:
        print("CUSTOMER_CHAT_ID isn't set - nothing to send to.", file=sys.stderr)
        sys.exit(1)

    send_photo(CUSTOMER_CHAT_ID, PHOTO_1, POEM)
    print("Sent photo 1 with poem to customer.")

    send_photo(CUSTOMER_CHAT_ID, PHOTO_2, "")
    print("Sent photo 2 to customer.")

    send_text(
        ADMIN_CHAT_ID,
        "\U0001F4E4 Sent birthday photos + poem to your brother just now:\n\n" + POEM,
    )
    print("Sent report to admin.")


if __name__ == "__main__":
    main()
