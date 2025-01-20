import pytest

from middlewared.plugins.virt.license import VirtLicenseGlobalService
from middlewared.pytest.unit.middleware import Middleware


@pytest.mark.parametrize('instance_type,chassis_hardware,license_active,expected_result', [
    (
        None,
        'TRUENAS-UNKNOWN',
        None,
        True
    ),
    (
        None,
        'TRUENAS-MINI-3.0-XL+',
        None,
        True
    ),
    (
        None,
        'TRUENAS-M60-HA',
        {'features': ['JAILS', 'VM']},
        True
    ),
    (
        'CONTAINER',
        'TRUENAS-M60-HA',
        {'features': ['JAILS', 'VM']},
        True
    ),
    (
        'VM',
        'TRUENAS-M60-HA',
        {'features': ['JAILS', 'VM']},
        True
    ),
    (
        'CONTAINER',
        'TRUENAS-M60-HA',
        {'features': ['VM']},
        False
    ),
    (
        'VM',
        'TRUENAS-M60-HA',
        {'features': ['JAILS']},
        False
    ),
    (
        None,
        'TRUENAS-M60-HA',
        None,
        False
    ),
    (
        'VM',
        'TRUENAS-M60-HA',
        None,
        False
    ),
])
@pytest.mark.asyncio
async def test_virt_license_validation(instance_type, chassis_hardware, license_active, expected_result):
    m = Middleware()
    m['truenas.get_chassis_hardware'] = lambda *arg: chassis_hardware
    m['system.license'] = lambda *arg: license_active
    assert await VirtLicenseGlobalService(m).license_active(instance_type) == expected_result
