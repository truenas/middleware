import pytest

from middlewared.plugins.update_.utils import can_update


@pytest.mark.parametrize("old_version,new_version,result", [
    ("FreeNAS-11", "FreeNAS-11.1", True),
    ("FreeNAS-11.1", "FreeNAS-11.1-U1", True),
    ("FreeNAS-11.3-U2", "FreeNAS-11.3-U2.1", True),
    ("FreeNAS-11.3-U2", "FreeNAS-12.0", True),
    ("FreeNAS-11.3-U2", "TrueNAS-12.0", True),
    ("FreeNAS-11.3-U2", "TrueNAS-12.0-MASTER-202004190426", True),
    ("FreeNAS-11.3-U2", "TrueNAS-12.0-MASTER-20200419-0426", True),
    ("FreeNAS-11.3", "TrueNAS-12.0-MASTER-20200419-0426", True),
    ("22.02-MASTER-20220207-112927", "22.02.1-MASTER-20220208-034252", True),
    ("22.02-ALPHA", "22.02-RC", True),
    ("22.02-ALPHA", "22.02-RC.2", True),
    ("22.02-RC", "22.02-RC.2", True),
    ("22.02-RC.2", "22.02", True),
    ("22.02-RC.2", "22.02.0", True),
    ("22.02", "22.02.1", True),
    ("22.02.0", "22.02.1", True),
    # Anything can be updated to a MASTER release
    ("TrueNAS-SCALE-22.02-RC.1", "TrueNAS-SCALE-22.02-MASTER-20211029-134913", True),
    # Older MASTER to newer MASTER
    ("TrueNAS-SCALE-22.02-MASTER-20211029-134913", "TrueNAS-SCALE-22.02-MASTER-20211029-205533", True),
    # Older INTERNAL to newer INTERNAL
    ("TrueNAS-SCALE-22.02-INTERNAL-225", "TrueNAS-SCALE-22.02-INTERNAL-226", True),
    # Anything can be updated to a CUSTOM build
    ("TrueNAS-SCALE-22.02-RC.1", "TrueNAS-SCALE-22.02-CUSTOM", True),
    ("TrueNAS-SCALE-22.02-MASTER-20211029-134913", "TrueNAS-SCALE-22.02-CUSTOM", True),
    ("22.02.0", "22.02.CUSTOM", True),
])
def test__can_update(old_version, new_version, result):
    assert can_update(old_version, new_version) is result
    assert can_update(new_version, old_version) is not result


def test_can_update_anything_to_internal():
    assert can_update("TrueNAS-SCALE-22.02-INTERNAL-225", "TrueNAS-SCALE-22.02-RC.1")


def test_can_update_internal_to_anything():
    assert can_update("TrueNAS-SCALE-22.02-RC.1", "TrueNAS-SCALE-22.02-INTERNAL-225")
