import pytest

from middlewared.scripts import ha_panic
from middlewared.utils.hardware import HardwareClass, HardwareInfo, Platform


def hardware_info(ha_platform: str) -> HardwareInfo:
    return HardwareInfo(
        platform=Platform.IX_HARDWARE,
        hardware_class=HardwareClass.TRUENAS_HW,
        chassis="TRUENAS-M50",
        ha_platform=ha_platform,
    )


@pytest.mark.parametrize("ha_platform,expected", [("ECHOWARP", True), ("MANUAL", False)])
def test_is_ha_capable(monkeypatch, ha_platform, expected):
    monkeypatch.setattr("middlewared.scripts.ha_panic.get_hardware_info", lambda: hardware_info(ha_platform))
    assert ha_panic.is_ha_capable() is expected
