import datetime as dt
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
BACKEND_PATH = ROOT / "src" / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

from app.services.time_window import AFTER, DAY_OF, LIVE, determine_time_window


def _utc(year: int, month: int, day: int, hour: int, minute: int = 0) -> dt.datetime:
    return dt.datetime(year, month, day, hour, minute, tzinfo=dt.timezone.utc)


def test_determine_time_window_live_et():
    air_time = _utc(2024, 1, 1, 1)  # 8pm ET previous day
    comment_time = _utc(2024, 1, 1, 2)  # Within live window
    assert determine_time_window(comment_time, air_time) == LIVE


def test_determine_time_window_live_pt_offset():
    air_time = _utc(2024, 1, 1, 1)
    comment_time = _utc(2024, 1, 1, 4, 30)  # 8:30pm PT equivalent
    assert determine_time_window(comment_time, air_time) == LIVE


def test_determine_time_window_day_of():
    air_time = _utc(2024, 1, 1, 1)
    comment_time = _utc(2024, 1, 1, 15)  # Later same day ET
    assert determine_time_window(comment_time, air_time) == DAY_OF


def test_determine_time_window_after():
    air_time = _utc(2024, 1, 1, 1)
    comment_time = _utc(2024, 1, 3, 1)
    assert determine_time_window(comment_time, air_time) == AFTER


def test_determine_time_window_missing_air_time():
    comment_time = _utc(2024, 1, 1, 1)
    assert determine_time_window(comment_time, None) is None
