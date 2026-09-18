from datetime import datetime, time
from types import SimpleNamespace as NS

from larder.services.scheduler import daily_due, weekly_due

H = NS(weekly_refresh_day=6, weekly_refresh_time=time(18, 0), daily_refresh_time=time(6, 0))


def test_weekly_due_on_sunday_evening():
    assert weekly_due(H, datetime(2026, 9, 20, 18, 5)) == "2026-W38"  # Sunday
    assert weekly_due(H, datetime(2026, 9, 20, 18, 0)) == "2026-W38"
    assert weekly_due(H, datetime(2026, 9, 20, 17, 55)) is None
    assert weekly_due(H, datetime(2026, 9, 19, 19, 0)) is None  # Saturday


def test_daily_due_after_six():
    assert daily_due(H, datetime(2026, 9, 18, 6, 0)) == "2026-09-18"
    assert daily_due(H, datetime(2026, 9, 18, 5, 59)) is None


def test_custom_schedule():
    h = NS(weekly_refresh_day=2, weekly_refresh_time=time(20, 30), daily_refresh_time=time(7, 0))
    assert weekly_due(h, datetime(2026, 9, 16, 20, 30)) == "2026-W38"  # Wednesday
    assert weekly_due(h, datetime(2026, 9, 16, 20, 29)) is None
