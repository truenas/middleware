import pytest

from middlewared.service_exception import ValidationErrors
from middlewared.pytest.unit.helpers import load_compound_service
from middlewared.pytest.unit.middleware import Middleware


VMService = load_compound_service('vm')


@pytest.mark.parametrize('ha_capable,license_features,should_work', [
    (True, [], False),
    (True, ['VM'], True),
    (False, [], True),
])
@pytest.mark.asyncio
async def test_vm_license_active_response(ha_capable, license_features, should_work):
    m = Middleware()
    vm_svc = VMService(m)

    m['system.is_ha_capable'] = lambda *args: ha_capable
    m['system.license'] = lambda *args: {'features': license_features}

    assert await vm_svc.license_active() is should_work
