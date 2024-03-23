import pytest
from middlewared.test.integration.utils import call

pytestmark = pytest.mark.zfs


def test_pool_resilver_update():
    resilver = {
        "enabled": False,
        "begin": "18:00",
        "end": "09:00",
        "weekday": [1, 2, 3, 4, 5, 6, 7],
    }

    assert call("pool.resilver.update", resilver).items() > resilver.items()
