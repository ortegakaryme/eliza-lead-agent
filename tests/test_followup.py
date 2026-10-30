from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.followup import compute_follow_up

TZ = "America/Mexico_City"


def at(y, m, d, h, mi=0):
    return datetime(y, m, d, h, mi, tzinfo=ZoneInfo(TZ))


# 2026-10-26 is a Monday.
@pytest.mark.parametrize(
    "now, deadline, phrase",
    [
        (at(2026, 10, 26, 7, 30), at(2026, 10, 26, 18), "hoy antes de las 6:00 de la tarde"),
        (at(2026, 10, 26, 15, 59), at(2026, 10, 26, 18), "hoy antes de las 6:00 de la tarde"),
        (at(2026, 10, 26, 16, 30), at(2026, 10, 27, 12), "mañana antes del mediodía"),
        (at(2026, 10, 30, 20, 0), at(2026, 10, 31, 12), "mañana antes del mediodía"),       # Fri night -> Sat
        (at(2026, 10, 31, 11, 0), at(2026, 10, 31, 14), "hoy antes de las 2:00 de la tarde"),  # Sat morning
        (at(2026, 10, 31, 13, 0), at(2026, 11, 2, 12), "el lunes antes del mediodía"),       # Sat afternoon
        (at(2026, 11, 1, 10, 0), at(2026, 11, 2, 12), "mañana antes del mediodía"),          # Sunday
    ],
)
def test_follow_up(now, deadline, phrase):
    result = compute_follow_up(TZ, now=now)
    assert result.deadline == deadline
    assert phrase in result.message
