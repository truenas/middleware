from unittest.mock import AsyncMock, Mock

import pytest

from middlewared.plugins.container.lxc import LXCConfigService
from middlewared.pytest.unit.helpers import create_service
from middlewared.pytest.unit.middleware import Middleware
from middlewared.service_exception import ValidationErrors


SYSTEM_IPS = [
    {'type': 'INET', 'address': '192.168.1.50', 'netmask': 24, 'broadcast': '192.168.1.255'},
    {'type': 'INET6', 'address': 'fe80::1', 'netmask': 64, 'broadcast': 'fe80::ffff:ffff:ffff:ffff'},
]

DEFAULT_CONFIG = {
    'id': 1,
    'bridge': None,
    'preferred_pool': None,
    'v4_network': '172.200.0.0/24',
    'v6_network': 'fd42:4c58:43ae::/64',
}


def setup_middleware(config=None):
    m = Middleware()
    row = config or DEFAULT_CONFIG.copy()
    m['datastore.query'] = Mock(return_value=[row])
    m['datastore.update'] = AsyncMock()
    m['interface.query'] = Mock(return_value=[])
    m['interface.ip_in_use'] = AsyncMock(return_value=SYSTEM_IPS)
    return m


@pytest.mark.asyncio
async def test_overlap_v4_rejected():
    """Changing v4_network to one overlapping a system IP should raise ValidationErrors."""
    m = setup_middleware()
    svc = create_service(m, LXCConfigService)
    with pytest.raises(ValidationErrors) as ve:
        await svc.do_update({'v4_network': '192.168.1.0/24'})
    errors = ve.value.errors
    assert any('overlaps' in e.errmsg for e in errors)
    assert any('v4_network' in e.attribute for e in errors)


@pytest.mark.asyncio
async def test_overlap_v6_rejected():
    """Changing v6_network to one overlapping a system IP should raise ValidationErrors."""
    m = setup_middleware()
    svc = create_service(m, LXCConfigService)
    with pytest.raises(ValidationErrors) as ve:
        await svc.do_update({'v6_network': 'fe80::/48'})
    errors = ve.value.errors
    assert any('overlaps' in e.errmsg for e in errors)
    assert any('v6_network' in e.attribute for e in errors)


@pytest.mark.asyncio
async def test_no_overlap_v4_accepted():
    """Changing v4_network to a non-overlapping one should succeed."""
    m = setup_middleware()
    svc = create_service(m, LXCConfigService)
    await svc.do_update({'v4_network': '10.0.0.0/24'})
    m['datastore.update'].assert_awaited_once()


@pytest.mark.asyncio
async def test_unchanged_network_skips_validation():
    """Submitting the same v4_network should not call interface.ip_in_use."""
    m = setup_middleware()
    svc = create_service(m, LXCConfigService)
    # Submit the same value as already in config
    await svc.do_update({'v4_network': '172.200.0.0/24'})
    m['interface.ip_in_use'].assert_not_called()


@pytest.mark.asyncio
async def test_both_networks_changed_both_checked():
    """When both v4 and v6 overlap, both errors should be reported."""
    m = setup_middleware()
    svc = create_service(m, LXCConfigService)
    with pytest.raises(ValidationErrors) as ve:
        await svc.do_update({
            'v4_network': '192.168.1.0/24',
            'v6_network': 'fe80::/48',
        })
    attrs = [e.attribute for e in ve.value.errors]
    assert any('v4_network' in a for a in attrs)
    assert any('v6_network' in a for a in attrs)


@pytest.mark.asyncio
async def test_no_overlap_v6_accepted():
    """Changing v6_network to a non-overlapping one should succeed."""
    m = setup_middleware()
    svc = create_service(m, LXCConfigService)
    await svc.do_update({'v6_network': 'fd00::/64'})
    m['datastore.update'].assert_awaited_once()
