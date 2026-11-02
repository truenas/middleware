from unittest.mock import AsyncMock, Mock

import pytest
from truenas_pylicensed.features import LicenseFeature

from middlewared.api.current import ZfsTierEntry
from middlewared.plugins.zfs.tier import ZfsTierService
from middlewared.pytest.unit.entitlements import install_entitlements_for_column
from middlewared.pytest.unit.middleware import Middleware, fake_service_control
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


@pytest.mark.parametrize("column,verb", [("CE+L", "RESTART"), ("CE+K", "RELOAD")])
@pytest.mark.asyncio
async def test_tier_update_restarts_daemon_while_unlicensed(monkeypatch, column, verb):
    m = Middleware()
    m.event_source_manager = Mock()
    install_entitlements_for_column(m, LicenseFeature.ZFSTIER, column)
    calls = fake_service_control(m)
    m["etc.generate"] = lambda *args: None
    svc = ZfsTierService(m)
    entry = ZfsTierEntry.model_construct(enabled=True, max_concurrent_jobs=2, special_class_metadata_reserve_pct=25)
    monkeypatch.setattr(svc, "config", AsyncMock(return_value=entry))
    monkeypatch.setattr(svc._svc_part, "do_update", AsyncMock(return_value=entry))

    await svc.do_update({"max_used_percentage": 80})

    assert [(v, s) for v, s, _ in calls] == [(verb, "truenas_zfstierd")]
