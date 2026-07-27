import pytest
from truenas_pylicensed.features import LicenseFeature

from middlewared.plugins.fc.fc import FCService
from middlewared.pytest.unit.helpers import create_service
from middlewared.pytest.unit.middleware import Middleware
from middlewared.utils.entitlements import Entitlement, Reason


def entitlements_stub(m, entitlement):
    checked = []

    def check(feature):
        checked.append(feature)
        return entitlement

    m.services.truenas.entitlements.check = check
    return checked


@pytest.mark.asyncio
async def test_fc_capable_denied_when_not_entitled():
    m = Middleware()
    m['fc.hba_present'] = lambda *args: True
    checked = entitlements_stub(m, Entitlement(
        entitled=False,
        reason=Reason.KEY_MISSING,
        column='CE+L',
        message='',
    ))

    assert await create_service(m, FCService).capable() is False
    assert checked == [LicenseFeature.FIBRECHANNEL]


@pytest.mark.asyncio
async def test_fc_capable_granted_when_entitled():
    m = Middleware()
    m['fc.hba_present'] = lambda *args: True
    checked = entitlements_stub(m, Entitlement(entitled=True, reason=Reason.ENTITLED, column='HW+K', message=''))

    assert await create_service(m, FCService).capable() is True
    assert checked == [LicenseFeature.FIBRECHANNEL]


@pytest.mark.asyncio
async def test_fc_capable_denied_without_hba_even_when_entitled():
    m = Middleware()
    m['fc.hba_present'] = lambda *args: False
    entitlements_stub(m, Entitlement(entitled=True, reason=Reason.ENTITLED, column='HW+K', message=''))

    assert await create_service(m, FCService).capable() is False


@pytest.mark.asyncio
async def test_fc_capable_skips_hardware_probe_when_not_entitled():
    m = Middleware()
    probed = []

    def hba_present(*args):
        probed.append(True)
        return True

    m['fc.hba_present'] = hba_present
    entitlements_stub(m, Entitlement(entitled=False, reason=Reason.KEY_MISSING, column='CE+L', message=''))

    assert await create_service(m, FCService).capable() is False
    assert probed == []
