import datetime

import pytest

from middlewared.plugins.pool_.pool_operations import (
    HIGH_PRIORITY,
    LOW_PRIORITY,
    ResilverPriority,
    calculate_resilver_priority,
)

# Reference dates with known isoweekday values (1=Mon .. 7=Sun):
#   2024-01-01 Mon(1)  2024-01-02 Tue(2)  2024-01-03 Wed(3)  2024-01-04 Thu(4)
#   2024-01-05 Fri(5)  2024-01-06 Sat(6)  2024-01-07 Sun(7)
MON, TUE, WED, THU, FRI, SAT, SUN = (datetime.date(2024, 1, d) for d in range(1, 8))

BUSINESS_DAYS = '1,2,3,4,5'
EVERY_DAY = '1,2,3,4,5,6,7'


def _resilver(weekday, begin, end, enabled=True):
    """Build a datastore-shaped resilver config row (times are datetime.time)."""
    return {
        'enabled': enabled,
        'weekday': weekday,
        'begin': datetime.time(*begin),
        'end': datetime.time(*end),
    }


def _at(day, hour, minute=0):
    return datetime.datetime.combine(day, datetime.time(hour, minute))


# ---------------------------------------------------------------------------
# Shape / return-value contract
# ---------------------------------------------------------------------------

def test_returns_resilver_priority_dataclass():
    result = calculate_resilver_priority(_resilver(EVERY_DAY, (9, 0), (17, 0)), _at(MON, 12))
    assert isinstance(result, ResilverPriority)


def test_priority_constant_values():
    # Locks in the exact tunables that get written to sysfs.
    assert HIGH_PRIORITY == ResilverPriority(
        resilver_min_time_ms=3000, nia_credit=10, nia_delay=2, scrub_max_active=8
    )
    assert LOW_PRIORITY == ResilverPriority(
        resilver_min_time_ms=1500, nia_credit=5, nia_delay=5, scrub_max_active=3
    )


# ---------------------------------------------------------------------------
# Daytime window (begin < end, no rollover past midnight)
# ---------------------------------------------------------------------------

def test_daytime_window_active():
    r = _resilver(BUSINESS_DAYS, (9, 0), (17, 0))
    assert calculate_resilver_priority(r, _at(MON, 12)) is HIGH_PRIORITY


def test_daytime_window_at_begin_is_inclusive():
    r = _resilver(BUSINESS_DAYS, (9, 0), (17, 0))
    assert calculate_resilver_priority(r, _at(MON, 9, 0)) is HIGH_PRIORITY


def test_daytime_window_before_begin():
    r = _resilver(BUSINESS_DAYS, (9, 0), (17, 0))
    assert calculate_resilver_priority(r, _at(MON, 8, 59)) is LOW_PRIORITY


def test_daytime_window_at_end_is_exclusive():
    r = _resilver(BUSINESS_DAYS, (9, 0), (17, 0))
    assert calculate_resilver_priority(r, _at(MON, 17, 0)) is LOW_PRIORITY


def test_daytime_window_after_end():
    r = _resilver(BUSINESS_DAYS, (9, 0), (17, 0))
    assert calculate_resilver_priority(r, _at(MON, 18, 0)) is LOW_PRIORITY


def test_daytime_window_wrong_weekday():
    # Saturday is not in the business-day set, so never high priority.
    r = _resilver(BUSINESS_DAYS, (9, 0), (17, 0))
    assert calculate_resilver_priority(r, _at(SAT, 12)) is LOW_PRIORITY


@pytest.mark.parametrize('day', [MON, TUE, WED, THU, FRI])
def test_daytime_window_every_business_day(day):
    r = _resilver(BUSINESS_DAYS, (9, 0), (17, 0))
    assert calculate_resilver_priority(r, _at(day, 12)) is HIGH_PRIORITY


# ---------------------------------------------------------------------------
# Overnight window (begin > end, rolls over midnight) -- evening half.
# This half is checked against "today" before the iterator is exhausted, so
# it behaves correctly.
# ---------------------------------------------------------------------------

def test_overnight_window_evening_active():
    # Default-style window: 18:00 -> 09:00 next day, every weekday enabled.
    r = _resilver(EVERY_DAY, (18, 0), (9, 0))
    assert calculate_resilver_priority(r, _at(MON, 22)) is HIGH_PRIORITY


def test_overnight_window_at_begin_is_inclusive():
    r = _resilver(EVERY_DAY, (18, 0), (9, 0))
    assert calculate_resilver_priority(r, _at(MON, 18, 0)) is HIGH_PRIORITY


def test_overnight_window_afternoon_gap_is_low():
    # 16:00 is after the previous night's window ended (09:00) and before
    # tonight's window starts (18:00) -> production priority.
    r = _resilver(EVERY_DAY, (18, 0), (9, 0))
    assert calculate_resilver_priority(r, _at(MON, 16)) is LOW_PRIORITY


def test_overnight_window_evening_wrong_weekday():
    r = _resilver(BUSINESS_DAYS, (18, 0), (9, 0))
    assert calculate_resilver_priority(r, _at(SAT, 22)) is LOW_PRIORITY


# ---------------------------------------------------------------------------
# Overnight window -- morning half (continuation of *yesterday's* window).
# These exercise the second membership test, which reads `weekdays` a second
# time after the first `in` check already consumed it.
# ---------------------------------------------------------------------------

def test_overnight_window_morning_after_end_is_low():
    # 10:00 is past the 09:00 end of the rolled-over window.
    r = _resilver(EVERY_DAY, (18, 0), (9, 0))
    assert calculate_resilver_priority(r, _at(TUE, 10)) is LOW_PRIORITY


def test_overnight_window_morning_at_end_is_exclusive():
    r = _resilver(EVERY_DAY, (18, 0), (9, 0))
    assert calculate_resilver_priority(r, _at(TUE, 9, 0)) is LOW_PRIORITY


def test_overnight_window_morning_previous_day_not_enabled():
    # Window is Tue-Sat. Tuesday 02:00 belongs to *Monday's* night, and Monday
    # is not enabled, so this is correctly low priority.
    r = _resilver('2,3,4,5,6', (18, 0), (9, 0))
    assert calculate_resilver_priority(r, _at(TUE, 2)) is LOW_PRIORITY


def test_overnight_window_sunday_night_into_monday_morning():
    # Monday 05:00 falls inside Sunday night's window. isoweekday()==1 matches
    # the FIRST enabled weekday, so the iterator is only advanced past '1' and
    # the lastweekday(=7) lookup still happens to find its value -> high.
    r = _resilver(EVERY_DAY, (23, 0), (6, 0))
    assert calculate_resilver_priority(r, _at(MON, 5)) is HIGH_PRIORITY


def test_overnight_window_into_next_morning_is_high_priority():
    # Tuesday 02:00 with the default every-day 18:00->09:00 window is squarely
    # inside Monday night's resilver window, so resilver should run at HIGH
    # priority.
    #
    # This currently FAILS: `calculate_resilver_priority` binds
    #     weekdays = map(lambda x: int(x), resilver['weekday'].split(','))
    # The evening check `now.isoweekday() in weekdays` (isoweekday 2) iterates
    # the map looking for 2, consuming elements 1 and 2. The morning check then
    # does `lastweekday in weekdays` (lastweekday 1), but 1 has already been
    # consumed from the one-shot map iterator, so it is never found and the
    # function wrongly returns LOW_PRIORITY. Replacing the `map(...)` with a
    # re-readable list/tuple fixes it.
    r = _resilver(EVERY_DAY, (18, 0), (9, 0))
    assert calculate_resilver_priority(r, _at(TUE, 2)) is HIGH_PRIORITY
