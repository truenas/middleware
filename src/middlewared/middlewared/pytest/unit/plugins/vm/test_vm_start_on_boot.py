import logging
from unittest.mock import Mock

import pytest
from truenas_pylicensed.features import LicenseFeature

from middlewared.api.current import VMEntry, VMStatus
from middlewared.plugins.vm.lifecycle import start_on_boot
from middlewared.pytest.unit.entitlements import install_entitlements_for_column
from middlewared.pytest.unit.middleware import Middleware
from middlewared.service import ServiceContext


class _Reached(Exception):
    pass


@pytest.mark.asyncio
async def test_start_on_boot_reaches_start_vm_without_strict_check():
    m = Middleware()
    checked = install_entitlements_for_column(m, LicenseFeature.VMS, "CE+L")
    m.services.truenas.entitlements.serving = lambda feature: True
    m.services.vm.query = lambda *args: [
        VMEntry.model_construct(id=1, name="myvm", autostart=True, status=VMStatus.model_construct(state="STOPPED"))
    ]
    m.services.vm.get_instance = Mock(side_effect=_Reached)

    await start_on_boot(ServiceContext(m, logging.getLogger("test_vm_start_on_boot")))

    m.services.vm.get_instance.assert_called_once_with(1)
    assert LicenseFeature.VMS not in checked
