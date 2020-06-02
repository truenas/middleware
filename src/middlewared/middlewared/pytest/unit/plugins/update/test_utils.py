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
])
def test__can_update(old_version, new_version, result):
    assert can_update(old_version, new_version) is result
    assert can_update(new_version, old_version) is not result
