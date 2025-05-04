import pytest

from middlewared.plugins.virt.storage import VirtInstanceStorageService
from middlewared.pytest.unit.middleware import Middleware


CONFIG = {
    'id': 1,
    'pool': 'tank',
    'dataset': 'tank/.ix-virt',
    'storage_pools': ['tank', 'mypool'],
    'bridge': None,
    'v4_network': '10.163.122.1/24',
    'v6_network': 'fd42:4c07:7d8a:dbab::1/64',
    'state': 'INITIALIZED',
}


@pytest.mark.parametrize('all_disk_sources,path,expected', [
    (
        {'/dev/zvol/tank/abc': 'vm'},
        'tank/abc',
        True
    ),
    (
        {
            '/dev/zvol/tank/abc': 'vm',
            '/dev/zvol/tank/zvol': 'vm'
        },
        'tank/zvol',
        True
    ),
    (
        {'/dev/zvol/tank/abc': 'vm'},
        'tank/zvol',
        False
    ),
    (
        {},
        'tank/abc',
        False
    ),
    (
        {},
        'tank/.ix-virt/abcd',
        True
    ),
    (
        {},
        'non_incus_pool/.ix-virt/abcd',
        False
    )
])
@pytest.mark.asyncio
async def test_virt_path(all_disk_sources, path, expected):
    m = Middleware()
    m['virt.global.config'] = lambda *arg: CONFIG
    m['virt.instance.get_all_disk_sources'] = lambda *args: all_disk_sources
    result = await VirtInstanceStorageService(m).virt_path(path)
    assert result == expected
