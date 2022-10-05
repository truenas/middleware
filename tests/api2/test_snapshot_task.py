import pytest
from pytest_dependency import depends

from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.assets.snapshot_task import snapshot_task
from middlewared.test.integration.utils import call

import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from auto_config import dev_test
reason = 'Skipping for test development testing'
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason=reason)


@pytest.fixture(scope="module")
def ds(request):
    depends(request, ["pool_04"], scope="session")
    with dataset("child"):
        with dataset("child/work"):
            yield


@pytest.mark.parametrize("data,path,include", [
    ({"dataset": "tank/child/work", "recursive": False}, "/mnt/tank/child", False),
    ({"dataset": "tank/child/work", "recursive": False}, "/mnt/tank/child/work", True),
    ({"dataset": "tank/child/work", "recursive": False}, "/mnt/tank/child/work/ix", False),
    ({"dataset": "tank/child/work", "recursive": True}, "/mnt/tank/child/work/ix", True),
    ({"dataset": "tank/child/work", "recursive": True, "exclude": ["tank/child/work/ix"]},
     "/mnt/tank/child/work/ix", False),
    ({"dataset": "tank/child/work", "recursive": True, "exclude": ["tank/child/work/ix"]},
     "/mnt/tank/child/work/ix/child", False),
])
def test_query_attachment_delegate(ds, data, path, include):
    data = {
        "lifetime_value": 1,
        "lifetime_unit": "DAY",
        "naming_schema": "%Y%m%d%H%M",
        **data,
    }

    with snapshot_task(data) as t:
        result = call("pool.dataset.query_attachment_delegate", "snapshottask", path, True)
        if include:
            assert len(result) == 1
            assert result[0]["id"] == t["id"]
        else:
            assert len(result) == 0
