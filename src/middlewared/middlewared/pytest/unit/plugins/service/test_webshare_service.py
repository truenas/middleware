import pytest
from truenas_pylicensed.features import LicenseFeature

from middlewared.plugins.service.services.webshare import WebShareService
from middlewared.pytest.unit.entitlements import install_entitlements_for_column
from middlewared.pytest.unit.middleware import Middleware
from middlewared.service_exception import CallError


@pytest.mark.asyncio
async def test_before_start_refuses_when_unentitled():
    """A RESTART runs stop+start, so a unit stopped by a revoke must not come back through it."""
    m = Middleware()
    install_entitlements_for_column(m, LicenseFeature.WEBSHARE, "CE")

    with pytest.raises(CallError):
        await WebShareService(m).before_start()
