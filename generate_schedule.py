"""
Fills the send queue forward so there's always something scheduled to
preview and approve.

Runs automatically at the end of the daily quote job, and can be run by
hand from the Actions tab ("Generate schedule") any time the queue needs
topping up.

Existing entries are never overwritten - rerolling a specific date is what
reroll_schedule.py is for.
"""

import schedule_utils as su


def main():
    sched, added = su.ensure_schedule()
    su.save_schedule(sched)
    print(f"Schedule extended: {added} new entr{'y' if added == 1 else 'ies'} added.")
    print(f"Queued: {len(sched['quotes'])} quote day(s), {len(sched['habits'])} habit day(s).")


if __name__ == "__main__":
    main()
