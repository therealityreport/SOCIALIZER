from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.core.config import get_settings

LIVE = "live"
DAY_OF = "day_of"
AFTER = "after"

_LIVE_PADDING = dt.timedelta(minutes=15)
_LIVE_DURATION = dt.timedelta(hours=3)
_PT_OFFSET = dt.timedelta(hours=3)


def determine_time_window(comment_utc: dt.datetime, air_time_utc: dt.datetime | None) -> str | None:
    """Assign a time window relative to the air time."""
    if air_time_utc is None:
        return None

    if comment_utc.tzinfo is None:
        comment_utc = comment_utc.replace(tzinfo=dt.timezone.utc)
    comment_utc = comment_utc.astimezone(dt.timezone.utc)

    if air_time_utc.tzinfo is None:
        air_time_utc = air_time_utc.replace(tzinfo=dt.timezone.utc)
    air_time_utc = air_time_utc.astimezone(dt.timezone.utc)

    settings = get_settings()
    try:
        primary_zone = ZoneInfo(settings.timezone)
    except ZoneInfoNotFoundError:
        primary_zone = ZoneInfo("US/Eastern")

    if _is_live_window(comment_utc, air_time_utc):
        return LIVE
    if settings.timezone in {"US/Eastern", "America/New_York"}:
        try:
            ZoneInfo("US/Pacific")
            if _is_live_window(comment_utc, air_time_utc + _PT_OFFSET):
                return LIVE
        except ZoneInfoNotFoundError:
            pass

    if _is_day_of(comment_utc, air_time_utc, primary_zone):
        return DAY_OF

    if settings.timezone in {"US/Eastern", "America/New_York"}:
        try:
            pt_zone = ZoneInfo("US/Pacific")
            if _is_day_of(comment_utc, air_time_utc + _PT_OFFSET, pt_zone):
                return DAY_OF
        except ZoneInfoNotFoundError:
            pass

    return AFTER


def _is_live_window(comment_utc: dt.datetime, air_time_utc: dt.datetime) -> bool:
    window_start = air_time_utc - _LIVE_PADDING
    window_end = air_time_utc + _LIVE_DURATION
    return window_start <= comment_utc <= window_end


def _is_day_of(comment_utc: dt.datetime, air_time_utc: dt.datetime, zone: ZoneInfo) -> bool:
    local_air = air_time_utc.astimezone(zone)
    day_start_local = local_air.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end_local = day_start_local + dt.timedelta(days=2)
    day_start = day_start_local.astimezone(dt.timezone.utc)
    day_end = day_end_local.astimezone(dt.timezone.utc)
    return day_start <= comment_utc < day_end
