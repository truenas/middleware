import pytest
from ixhardware import DMIInfo

from middlewared.utils.hardware import detect, probe
from middlewared.utils.hardware.types import HardwareClass, Platform


@pytest.fixture(autouse=True)
def uncached():
    """Defensive only: no test here warms the real cache, because ``wire`` patches probe's
    own binding rather than ``detect_platform`` itself. Clearing keeps that true if it
    stops holding."""
    detect.detect_platform.cache_clear()
    yield
    detect.detect_platform.cache_clear()


@pytest.fixture
def wire(monkeypatch):
    """Stand in for both impure inputs: DMI, and the platform detector."""

    def build(dmi: DMIInfo, detect):
        monkeypatch.setattr(probe, "parse_dmi", lambda: dmi)
        monkeypatch.setattr(probe, "detect_platform", detect)

    return build


def test_hardware_half_reaches_ha_platform(wire):
    wire(DMIInfo(system_product_name="TRUENAS-M50"), lambda: ("ECHOWARP", "B"))

    info = probe.get_hardware_info()

    assert info.ha_platform == "ECHOWARP"
    assert info.is_ha_capable is True
    assert info.platform is Platform.IX_HARDWARE
    assert info.hardware_class is HardwareClass.TRUENAS_HW


def test_detection_failure_propagates(wire):
    """The chassis tag cannot say whether this is one half of an HA pair, so there is no honest fallback."""

    def boom():
        raise OSError("no enclosure")

    wire(DMIInfo(system_product_name="TRUENAS-MINI-R"), boom)
    with pytest.raises(OSError):
        probe.get_hardware_info()
