import pytest
from truenas_pylicensed.features import LicenseFeature

from middlewared.plugins.fc.fc import FCService
from middlewared.pytest.unit.entitlements import install_entitlements_for_column
from middlewared.pytest.unit.helpers import create_service
from middlewared.pytest.unit.middleware import Middleware


@pytest.mark.asyncio
async def test_fc_capable_denied_when_not_entitled():
    m = Middleware()
    m["fc.hba_present"] = lambda *args: True
    checked = install_entitlements_for_column(m, LicenseFeature.FIBRECHANNEL, "CE+L")

    assert await create_service(m, FCService).capable() is False
    assert checked == [LicenseFeature.FIBRECHANNEL]


@pytest.mark.asyncio
async def test_fc_capable_granted_when_entitled():
    m = Middleware()
    m["fc.hba_present"] = lambda *args: True
    checked = install_entitlements_for_column(m, LicenseFeature.FIBRECHANNEL, "HW+K")

    assert await create_service(m, FCService).capable() is True
    assert checked == [LicenseFeature.FIBRECHANNEL]


@pytest.mark.asyncio
async def test_fc_capable_denied_without_hba_even_when_entitled():
    m = Middleware()
    m["fc.hba_present"] = lambda *args: False
    install_entitlements_for_column(m, LicenseFeature.FIBRECHANNEL, "HW+K")

    assert await create_service(m, FCService).capable() is False


@pytest.mark.asyncio
async def test_fc_capable_skips_hardware_probe_when_not_entitled():
    m = Middleware()
    probed = []

    def hba_present(*args):
        probed.append(True)
        return True

    m["fc.hba_present"] = hba_present
    install_entitlements_for_column(m, LicenseFeature.FIBRECHANNEL, "CE+L")

    assert await create_service(m, FCService).capable() is False
    assert probed == []
