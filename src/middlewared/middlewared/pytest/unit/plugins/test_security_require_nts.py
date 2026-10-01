"""`system.security.update` and `require_nts`: when it may be enabled, and that chronyd is told on both controllers."""

import logging
from unittest.mock import AsyncMock, Mock

import pytest

from middlewared.api.current import SystemSecurityEntry, SystemSecurityUpdate
from middlewared.plugins.security.config import SystemSecurityConfigServicePart
from middlewared.pytest.unit.middleware import FakeJob, Middleware
from middlewared.service import ValidationError
from middlewared.service.context import ServiceContext


def security(require_nts):
    return SystemSecurityEntry(id=1, enable_fips=False, enable_gpos_stig=False, require_nts=require_nts)


def update(*, old_require_nts, new_require_nts, nts_servers=(), ha=False):
    m = Middleware()
    m["failover.licensed"] = AsyncMock(return_value=ha)
    m["failover.disabled.reasons"] = Mock(return_value=[])
    m["failover.call_remote"] = AsyncMock()
    m.services.system.ntpserver.query = Mock(return_value=list(nts_servers))
    m.services.service.control = Mock(return_value=FakeJob())

    svc_part = SystemSecurityConfigServicePart(ServiceContext(m, logging.getLogger("test")))
    svc_part.config = AsyncMock(return_value=security(old_require_nts))
    svc_part._update = AsyncMock()

    async def run():
        await svc_part.do_update(FakeJob(), SystemSecurityUpdate(require_nts=new_require_nts))

    return m, svc_part, run


@pytest.mark.asyncio
async def test_enabling_requires_an_nts_server():
    m, svc_part, run = update(old_require_nts=False, new_require_nts=True)

    with pytest.raises(ValidationError) as ve:
        await run()

    assert ve.value.attribute == "system_security_update.require_nts"
    m.services.system.ntpserver.query.assert_called_once_with([["nts", "=", True]])
    svc_part._update.assert_not_called()
    m.services.service.control.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("old,new", [(False, True), (True, False)])
async def test_a_change_restarts_chronyd(old, new):
    m, svc_part, run = update(old_require_nts=old, new_require_nts=new, nts_servers=[Mock(nts=True)])

    await run()

    svc_part._update.assert_awaited_once()
    m.services.service.control.assert_called_once_with("RESTART", "ntpd")
    m["failover.call_remote"].assert_not_called()


@pytest.mark.asyncio
async def test_disabling_does_not_need_an_nts_server():
    m, svc_part, run = update(old_require_nts=True, new_require_nts=False)

    await run()

    m.services.system.ntpserver.query.assert_not_called()
    m.services.service.control.assert_called_once_with("RESTART", "ntpd")


@pytest.mark.asyncio
async def test_no_change_leaves_chronyd_alone():
    m, svc_part, run = update(old_require_nts=True, new_require_nts=True, nts_servers=[Mock(nts=True)])

    await run()

    m.services.service.control.assert_not_called()


@pytest.mark.asyncio
async def test_ha_restarts_chronyd_on_the_other_controller_too():
    m, svc_part, run = update(old_require_nts=False, new_require_nts=True, nts_servers=[Mock(nts=True)], ha=True)

    await run()

    m.services.service.control.assert_called_once_with("RESTART", "ntpd")
    m["failover.call_remote"].assert_awaited_once_with("service.control", ["RESTART", "ntpd"], {"job": True})
