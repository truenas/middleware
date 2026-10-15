from unittest.mock import Mock

import pytest
from truenas_pylicensed.features import LicenseFeature

from middlewared.plugins.iscsi_.iscsi_global import FibreChannelLicenseDelegate
from middlewared.pytest.unit.middleware import Middleware, fake_service_control
from middlewared.service_exception import CallError


@pytest.mark.asyncio
async def test_fc_revoke_raises_when_qla_target_stays_enabled_after_reload():
    """The iscsitarget reload swallows scstadmin failures, so a revoke must not report success on its word."""
    m = Middleware()
    m.services.service.started = Mock(return_value=True)
    reloads = fake_service_control(m, result=True)
    m["fcport.any_qla_target_enabled"] = Mock(return_value=True)

    with pytest.raises(CallError, match="Fibre Channel targets still enabled"):
        await FibreChannelLicenseDelegate(m).apply({LicenseFeature.FIBRECHANNEL: False})

    assert [(verb, service) for verb, service, _ in reloads] == [("RELOAD", "iscsitarget")]
