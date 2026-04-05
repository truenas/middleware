import pytest
from unittest.mock import AsyncMock

from middlewared.plugins.system.reboot import SystemRebootService, CACHE_KEY
from middlewared.pytest.unit.helpers import create_service
from middlewared.pytest.unit.middleware import Middleware


BOOT_ID = 'test-boot-id-aaa'


def make_service(*, cache_contents=None):
    m = Middleware()
    m['system.boot_id'] = AsyncMock(return_value=BOOT_ID)

    store = {} if cache_contents is None else {CACHE_KEY: dict(cache_contents)}

    async def cache_get(key):
        if key not in store:
            raise KeyError(key)
        return store[key]

    async def cache_put(key, value, *args):
        store[key] = value

    m['cache.get'] = cache_get
    m['cache.put'] = cache_put

    svc = create_service(m, SystemRebootService)
    return svc, m, store


# --- info() tests ---

@pytest.mark.asyncio
async def test_info_empty():
    svc, m, store = make_service()
    info = await svc.info()
    assert info['boot_id'] == BOOT_ID
    assert info['reboot_required_reasons'] == []


@pytest.mark.asyncio
async def test_info_with_reasons():
    svc, m, store = make_service(cache_contents={
        'FIPS': 'FIPS changed',
    })
    info = await svc.info()
    assert len(info['reboot_required_reasons']) == 1
    assert info['reboot_required_reasons'][0] == {'code': 'FIPS', 'reason': 'FIPS changed'}


@pytest.mark.asyncio
async def test_info_multiple_reasons():
    svc, m, store = make_service(cache_contents={
        'FIPS': 'FIPS changed',
        'UPGRADE': 'Upgrade pending',
    })
    info = await svc.info()
    assert len(info['reboot_required_reasons']) == 2
    codes = {r['code'] for r in info['reboot_required_reasons']}
    assert codes == {'FIPS', 'UPGRADE'}


# --- Mutation tests ---

@pytest.mark.asyncio
async def test_add_reason():
    svc, m, store = make_service()
    await svc.add_reason('FIPS', 'FIPS changed')
    assert store[CACHE_KEY] == {'FIPS': 'FIPS changed'}


@pytest.mark.asyncio
async def test_add_multiple():
    svc, m, store = make_service()
    await svc.add_reason('FIPS', 'FIPS changed')
    await svc.add_reason('UPGRADE', 'Upgrade needed')
    assert store[CACHE_KEY] == {
        'FIPS': 'FIPS changed',
        'UPGRADE': 'Upgrade needed',
    }


@pytest.mark.asyncio
async def test_toggle_on():
    svc, m, store = make_service()
    await svc.toggle_reason('FIPS', 'FIPS changed')
    assert 'FIPS' in store[CACHE_KEY]


@pytest.mark.asyncio
async def test_toggle_off():
    svc, m, store = make_service(cache_contents={
        'FIPS': 'FIPS changed',
    })
    await svc.toggle_reason('FIPS', 'FIPS changed')
    assert 'FIPS' not in store[CACHE_KEY]


@pytest.mark.asyncio
async def test_remove_reason():
    svc, m, store = make_service(cache_contents={
        'FIPS': 'FIPS changed',
    })
    await svc.remove_reason('FIPS')
    assert store[CACHE_KEY] == {}


@pytest.mark.asyncio
async def test_remove_nonexistent():
    svc, m, store = make_service()
    await svc.remove_reason('NONEXISTENT')
    assert store[CACHE_KEY] == {}


@pytest.mark.asyncio
async def test_list_reasons():
    svc, m, store = make_service(cache_contents={
        'FIPS': 'FIPS changed',
        'UPGRADE': 'Upgrade pending',
    })
    codes = await svc.list_reasons()
    assert sorted(codes) == ['FIPS', 'UPGRADE']


@pytest.mark.asyncio
async def test_list_reasons_empty():
    svc, m, store = make_service()
    codes = await svc.list_reasons()
    assert codes == []
