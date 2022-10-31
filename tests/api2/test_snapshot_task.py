import pytest

from middlewared.service_exception import InstanceNotFound
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


def test_snapshot_task_is_not_deleted_when_deleting_a_child_dataset():
    with dataset("parent") as parent:
        with dataset("parent/child") as child:
            with snapshot_task({
                "dataset": parent,
                "recursive": True,
                "lifetime_value": 1,
                "lifetime_unit": "DAY",
                "naming_schema": "%Y%m%d%H%M",
            }) as t:
                call("pool.dataset.delete", child)

                assert call("pool.snapshottask.get_instance", t["id"])


def test_snapshot_task_is_deleted_when_deleting_a_parent_dataset():
    with dataset("parent") as parent:
        with dataset("parent/child") as child:
            with snapshot_task({
                "dataset": child,
                "recursive": True,
                "lifetime_value": 1,
                "lifetime_unit": "DAY",
                "naming_schema": "%Y%m%d%H%M",
            }) as t:
                call("pool.dataset.delete", parent, {"recursive": True})

                with pytest.raises(InstanceNotFound):
                    assert call("pool.snapshottask.get_instance", t["id"])
