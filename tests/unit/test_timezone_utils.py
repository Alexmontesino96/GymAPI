from datetime import datetime, timezone, timedelta

import pytz

from app.core.timezone_utils import normalize_to_utc, is_session_in_future, convert_utc_to_local


def test_normalize_to_utc_naive_local():
    tz = 'America/New_York'
    # July 1, 2025 at 10:00 local (EDT is UTC-4)
    local_naive = datetime(2025, 7, 1, 10, 0, 0)
    utc_dt = normalize_to_utc(local_naive, tz)
    assert utc_dt.tzinfo is not None
    assert utc_dt.tzinfo == timezone.utc
    assert utc_dt.hour == 14 and utc_dt.minute == 0


def test_normalize_to_utc_aware_input():
    tz = 'America/New_York'
    # Aware +02:00 should convert to 08:00Z
    aware_dt = datetime(2025, 7, 1, 10, 0, 0, tzinfo=timezone(timedelta(hours=2)))
    utc_dt = normalize_to_utc(aware_dt, tz)
    assert utc_dt.tzinfo == timezone.utc
    assert utc_dt.hour == 8 and utc_dt.minute == 0


def test_is_session_in_future_accepts_aware_and_naive():
    tz = 'America/Mexico_City'
    # Current time references
    now_utc = datetime.now(timezone.utc)
    # Build a time 2 minutes ahead in gym local
    gym_tz = pytz.timezone(tz)
    now_local = now_utc.astimezone(gym_tz)
    future_local_naive = now_local.replace(tzinfo=None) + timedelta(minutes=2)
    # Aware UTC two minutes ahead
    future_utc_aware = now_utc + timedelta(minutes=2)

    assert is_session_in_future(future_local_naive, tz)
    assert is_session_in_future(future_utc_aware, tz)

