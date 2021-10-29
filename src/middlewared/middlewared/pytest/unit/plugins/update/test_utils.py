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
    # Anything can be updated to a MASTER release
    ("TrueNAS-SCALE-22.02-RC.1", "TrueNAS-SCALE-22.02-MASTER-20211029-134913", True),
    # Anything can be updated to a INTERNAL build
    ("TrueNAS-SCALE-22.02-RC.1", "TrueNAS-SCALE-22.02-INTERNAL-225", True),
    # Master release can't be updated to INTERNAL build because INTERNAL are usually a bit outdated
    ("TrueNAS-SCALE-22.02-MASTER-20211029-134913", "TrueNAS-SCALE-22.02-INTERNAL-225", False),
    # Older MASTER to newer MASTER
    ("TrueNAS-SCALE-22.02-MASTER-20211029-134913", "TrueNAS-SCALE-22.02-MASTER-20211029-205533", True),
    # Older INTERNAL to newer INTERNAL
    ("TrueNAS-SCALE-22.02-INTERNAL-225", "TrueNAS-SCALE-22.02-INTERNAL-226", True),
])
def test__can_update(old_version, new_version, result):
    assert can_update(old_version, new_version) is result
    assert can_update(new_version, old_version) is not result
