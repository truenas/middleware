from unittest.mock import Mock

import pytest

from middlewared.plugins.snapshot import PeriodicSnapshotTaskService


@pytest.mark.parametrize("task,count", [
    ({"schedule": {"hour": "0", "minute": "0", "dom": "*", "month": "*", "dow": "*"},
      "lifetime_value": 1, "lifetime_unit": "MONTH"}, 30),
    ({"schedule": {"hour": "0", "minute": "0", "dom": "*", "month": "*", "dow": "*"},
      "lifetime_value": 2, "lifetime_unit": "MONTH"}, 60),
    ({"schedule": {"hour": "0", "minute": "0", "dom": "*", "month": "*", "dow": "*"},
      "lifetime_value": 5, "lifetime_unit": "YEAR"}, 365 * 5),
    ({"schedule": {"hour": "*", "minute": "0", "dom": "*", "month": "*", "dow": "*"},
      "lifetime_value": 1, "lifetime_unit": "MONTH"}, 720),
    ({"schedule": {"hour": "*", "minute": "0", "dom": "*", "month": "*", "dow": "*", "begin": "16:00", "end": "18:59"},
      "lifetime_value": 1, "lifetime_unit": "MONTH"}, 90),
])
def test__snapshot_task__foreseen_count(task, count):
    assert PeriodicSnapshotTaskService(Mock()).foreseen_count(task) == count
