import contextlib

import sys
import os
sys.path.append(os.getcwd())

import pytest

from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.utils import call
from middlewared.test.integration.assets.pool import dataset
from auto_config import dev_test
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skip for testing')


@contextlib.contextmanager
def iscsi_extent(data):
    extent = call("iscsi.extent.create", data)

    try:
        yield extent
    finally:
        call("iscsi.extent.delete", extent["id"])


def test__iscsi_extent__disk_choices():
    with dataset("test zvol", {
        "type": "VOLUME",
        "volsize": 1024000,
    }) as ds:
        call("zfs.snapshot.create", {"dataset": ds, "name": "snap-1"})

        assert call("iscsi.extent.disk_choices") == {
            f'zvol/{ds.replace(" ", "+")}': f'{ds} (1000K)',
            f'zvol/{ds.replace(" ", "+")}@snap-1': f'{ds}@snap-1 [ro]',
        }

        with iscsi_extent({
            "name": "test_extent",
            "type": "DISK",
            "disk": f"zvol/{ds.replace(' ', '+')}",
        }):
            assert call("iscsi.extent.disk_choices") == {
                f'zvol/{ds.replace(" ", "+")}@snap-1': f'{ds}@snap-1 [ro]',
            }


def test__iscsi_extent__create_with_invalid_disk_with_whitespace():
    with dataset("test zvol", {
        "type": "VOLUME",
        "volsize": 1024000,
    }) as ds:
        with pytest.raises(ValidationErrors) as e:
            with iscsi_extent({
                "name": "test_extent",
                "type": "DISK",
                "disk": f"zvol/{ds}",
            }):
                pass

        assert str(e.value) == (
            f"[EINVAL] iscsi_extent_create.disk: Device '/dev/zvol/{ds}' for volume '{ds}' does not exist\n"
        )


def test__iscsi_extent__locked():
    with dataset("test zvol", {
        "type": "VOLUME",
        "volsize": 1024000,
        "inherit_encryption": False,
        "encryption": True,
        "encryption_options": {"passphrase": "testtest"},
    }) as ds:
        with iscsi_extent({
            "name": "test_extent",
            "type": "DISK",
            "disk": f"zvol/{ds.replace(' ', '+')}",
        }) as extent:
            assert not extent["locked"]

            call("pool.dataset.lock", ds, job=True)

            extent = call("iscsi.extent.get_instance", extent["id"])
            assert extent["locked"]
