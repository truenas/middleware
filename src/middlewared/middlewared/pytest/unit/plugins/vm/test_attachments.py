import pytest

from middlewared.api.current import VMDeviceEntry
from middlewared.plugins.vm.snapshot_tasks import determine_recursive_search


@pytest.mark.parametrize("recursive,device,child_datasets,result", [
    (
        True,
        VMDeviceEntry(id=1, vm=1, order=1000, attributes={"dtype": "CDROM", "path": "/mnt/tank/somefile"}),
        {"tank/child": {}},
        True,
    ),
    (
        False,
        VMDeviceEntry(id=2, vm=1, order=1001, attributes={"dtype": "DISK", "path": "/dev/zvol/tank/somezvol"}),
        {"tank/child": {}},
        False,
    ),
    (
        False,
        VMDeviceEntry(id=3, vm=1, order=1001, attributes={"dtype": "RAW", "path": "/mnt/tank/child/file"}),
        {"tank/child": {}},
        False,
    ),
    (
        False,
        VMDeviceEntry(id=4, vm=1, order=1001, attributes={"dtype": "RAW", "path": "/mnt/tank/file"}),
        {"tank/child": {}},
        True,
    ),
])
@pytest.mark.asyncio
async def test_determining_recursive_search(recursive, device, child_datasets, result):
    assert await determine_recursive_search(recursive, device, child_datasets) is result
