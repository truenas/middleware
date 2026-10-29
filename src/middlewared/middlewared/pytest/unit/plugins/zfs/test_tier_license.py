from unittest.mock import AsyncMock, Mock

import pytest
from truenas_pylicensed.features import LicenseFeature

from middlewared.api.current import ZfsTierEntry
from middlewared.plugins.zfs.tier import ZfsTierService
from middlewared.pytest.unit.entitlements import install_entitlements_for_column
from middlewared.pytest.unit.middleware import Middleware
from middlewared.service import CallError


class _Saved(Exception):
    pass


@pytest.mark.parametrize("old_enabled,enabled,refused", [(True, False, False), (False, True, True)])
@pytest.mark.asyncio
async def test_tier_update_disable_passes_unlicensed_enable_refused(monkeypatch, old_enabled, enabled, refused):
    m = Middleware()
    m.event_source_manager = Mock()
    install_entitlements_for_column(m, LicenseFeature.ZFSTIER, "CE+L")
    svc = ZfsTierService(m)
    monkeypatch.setattr(svc, "config", AsyncMock(return_value=ZfsTierEntry.model_construct(enabled=old_enabled)))
    monkeypatch.setattr(svc._svc_part, "do_update", AsyncMock(side_effect=_Saved))

    with pytest.raises(CallError if refused else _Saved):
        await svc.do_update({"enabled": enabled})
