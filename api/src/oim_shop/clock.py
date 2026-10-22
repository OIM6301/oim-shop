"""The shop's clock.

oim-api moves every Northwind date forward by CLOCK_SHIFT_DAYS so that orders keep
arriving until 2027-06-30, and lists only orders placed by now, Boston time. The
seed is loaded on the same clock, and sync stops if oim-api reports another shift.
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

CLOCK_SHIFT_DAYS = 1341
BOSTON = ZoneInfo("America/New_York")


def now() -> datetime:
    """Now in Boston, without a time zone, to compare with the data's timestamps."""
    return datetime.now(BOSTON).replace(tzinfo=None, microsecond=0)


def shift(published: str) -> str:
    """A published ISO timestamp moved onto the shop's clock."""
    return (datetime.fromisoformat(published) + timedelta(days=CLOCK_SHIFT_DAYS)).isoformat()
