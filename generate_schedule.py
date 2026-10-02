"""
Fills the weekly habit queue forward so there's always something
scheduled to preview. (Daily quotes go through the approval card instead.)

Runs automatically before the weekly habit send and the Saturday preview.

Existing entries are never overwritten - rerolling a specific date is what
reroll_schedule.py is for.
"""

import schedule_utils as su


def main():
    sched, added = su.ensure_schedule()
    su.save_schedule(sched)
    print(f"Schedule extended: {added} new entr{'y' if added == 1 else 'ies'} added.")
    print(f"Queued: {len(sched['habits'])} habit day(s). Quotes go through daily approval.")


if __name__ == "__main__":
    main()
