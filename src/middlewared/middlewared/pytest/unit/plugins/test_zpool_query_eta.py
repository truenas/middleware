import time
from types import SimpleNamespace

import pytest

from middlewared.plugins.zpool.query_impl import _format_expand, _format_scan

NOW = 1_000_000
MIB = 1024 * 1024
TOTAL = 100 * 1024 * MIB


@pytest.fixture(autouse=True)
def fixed_time(monkeypatch):
    monkeypatch.setattr(time, "time", lambda: NOW)


def scrub_info(func="SCRUB", state="SCANNING", **kwargs):
    fields = {
        "start_time": NOW - 100,
        "end_time": 0,
        "to_examine": TOTAL,
        "examined": 0,
        "skipped": 0,
        "processed": 0,
        "issued": 0,
        "errors": 0,
        "pass_start": NOW - 100,
        "pass_scrub_pause": 0,
        "pass_scrub_spent_paused": 0,
        "pass_issued": 0,
        "percentage": None,
    }
    fields.update(kwargs)
    return SimpleNamespace(func=SimpleNamespace(name=func), state=SimpleNamespace(name=state), **fields)


def expand_info(state="SCANNING", **kwargs):
    fields = {
        "expanding_vdev": 0,
        "start_time": NOW - 100,
        "end_time": 0,
        "to_reflow": TOTAL,
        "reflowed": 10_000 * MIB,
        "waiting_for_resilver": 0,
    }
    fields.update(kwargs)
    return SimpleNamespace(state=SimpleNamespace(name=state), **fields)


@pytest.mark.parametrize(
    "info,expected",
    [
        (scrub_info(issued=10_000 * MIB, pass_issued=10_000 * MIB), 924),
        (scrub_info(), None),
        (scrub_info(issued=50_000 * MIB, pass_start=NOW - 5), None),
        (scrub_info(issued=500 * MIB, pass_issued=500 * MIB), None),
        (scrub_info(issued=10_000 * MIB, pass_issued=10_000 * MIB, pass_scrub_pause=NOW - 10), None),
        (scrub_info(issued=2**64 - 1000, pass_issued=10_000 * MIB), None),
        (scrub_info(func="RESILVER", issued=10_000 * MIB, pass_issued=10_000 * MIB), None),
        (scrub_info(func="RESILVER", processed=MIB, issued=10_000 * MIB, pass_issued=10_000 * MIB), 924),
        (scrub_info(state="FINISHED", issued=TOTAL, pass_issued=TOTAL), None),
        (scrub_info(to_examine=2**50, issued=10_000 * MIB, pass_issued=10_000 * MIB, pass_start=NOW - 999), 107265811),
    ],
    ids=[
        "issuing",
        "before_issue_phase",
        "after_import",
        "below_10_mib_per_sec",
        "paused",
        "issued_exceeds_total",
        "resilver_not_repairing",
        "resilver_repairing",
        "finished",
        "integer_math_like_zpool",
    ],
)
def test_scan_total_secs_left(info, expected):
    assert _format_scan(info)["total_secs_left"] == expected


@pytest.mark.parametrize(
    "info,expected",
    [
        (expand_info(), 924),
        (expand_info(waiting_for_resilver=1), None),
        (expand_info(reflowed=0), None),
        (expand_info(reflowed=MIB), None),
        (expand_info(state="FINISHED", reflowed=TOTAL), None),
        (expand_info(to_reflow=5_000 * MIB), None),
    ],
    ids=["expanding", "waiting_for_resilver", "nothing_reflowed", "over_30_days", "finished", "reflowed_exceeds_total"],
)
def test_expand_total_secs_left(info, expected):
    assert _format_expand(info)["total_secs_left"] == expected
