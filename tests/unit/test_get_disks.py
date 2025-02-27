from middlewared.utils.disks_.get_disks import get_disks

import pytest


@pytest.mark.parametrize(
    "name,should_find", [(["sda"], True), (["/dev/sdb"], True), (["nope"], False)]
)
def test__get_disks_filters(name, should_find):
    found = False
    for i in get_disks(name_filters=name):
        found = i

    if should_find:
        assert found
    else:
        assert not found
