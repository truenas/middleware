import pytest

from middlewared.plugins.vm.attachments import determine_recursive_search


@pytest.mark.parametrize('recursive,device,child_datasets,result', [
    (True, {'attributes': {'path': '/mnt/tank/somefile'}, 'dtype': 'CDROM'}, ['tank/child'], True),
    (False, {'attributes': {'path': '/dev/zvol/tank/somezvol'}, 'dtype': 'DISK'}, ['tank/child'], False),
    (False, {'attributes': {'path': '/mnt/tank/child/file'}, 'dtype': 'RAW'}, ['tank/child'], False),
    (False, {'attributes': {'path': '/mnt/tank/file'}, 'dtype': 'RAW'}, ['tank/child'], True),
])
@pytest.mark.asyncio
async def test_determining_recursive_search(recursive, device, child_datasets, result):
    assert await determine_recursive_search(recursive, device, child_datasets) is result
