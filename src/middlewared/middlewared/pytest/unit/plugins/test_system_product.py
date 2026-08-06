import pytest

from middlewared.plugins.system.product import SystemService
from middlewared.pytest.unit.helpers import create_service
from middlewared.pytest.unit.middleware import Middleware
from middlewared.utils.hardware import HardwareClass, HardwareInfo, Platform


def hardware_info(ha_platform: str) -> HardwareInfo:
    return HardwareInfo(
        platform=Platform.IX_HARDWARE,
        hardware_class=HardwareClass.TRUENAS_HW,
        chassis="TRUENAS-M50",
        ha_platform=ha_platform,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("ha_platform,expected", [("ECHOWARP", True), ("MANUAL", False)])
async def test_is_ha_capable(monkeypatch, ha_platform, expected):
    monkeypatch.setattr(
        "middlewared.plugins.system.product.get_hardware_info",
        lambda: hardware_info(ha_platform),
    )
    # "failover.hardware" is deliberately left unpopulated: Middleware is a dict
    # subclass, so a body that still called it would raise KeyError, not pass.
    assert await create_service(Middleware(), SystemService).is_ha_capable() is expected
