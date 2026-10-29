import logging
from unittest.mock import AsyncMock

import pytest
from truenas_pylicensed.features import LicenseFeature

from middlewared.api.current import SharingWebshareEntry
from middlewared.plugins.webshare import sharing_validate
from middlewared.plugins.webshare.sharing_crud import SharingWebsharePart
from middlewared.pytest.unit.entitlements import install_entitlements_for_column
from middlewared.pytest.unit.middleware import Middleware
from middlewared.service import ValidationErrors
from middlewared.service.context import ServiceContext


@pytest.mark.parametrize("old_enabled,refused", [(True, False), (False, True)])
@pytest.mark.asyncio
async def test_enabling_share_requires_license_but_editing_enabled_share_does_not(monkeypatch, old_enabled, refused):
    m = Middleware()
    install_entitlements_for_column(m, LicenseFeature.WEBSHARE, "CE+L")
    part = SharingWebsharePart(ServiceContext(m, logging.getLogger("test")))
    for name in ("validate_share_name", "resolve_share_path", "validate_share_path", "validate_home_base"):
        monkeypatch.setattr(sharing_validate, name, AsyncMock())
    old = SharingWebshareEntry.model_construct(id=1, name="share", enabled=old_enabled)
    data = SharingWebshareEntry.model_construct(id=1, name="share", enabled=True, is_home_base=False)

    verrors = ValidationErrors()
    await sharing_validate.validate_webshare(part, data, "sharing_webshare_update", verrors, old)

    assert bool(verrors.errors) is refused
