import pytest
from ixhardware import DMIInfo

from middlewared.utils.hardware import detect, probe
from middlewared.utils.hardware.types import HardwareClass, Platform


@pytest.fixture(autouse=True)
def uncached():
    """``detect_platform`` caches, so every test here has to start from a cold
    cache and must not leave a warm one behind for the next file. It is mocked
    out below, but a real call would otherwise leak across tests."""
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
    """Only the HARDWARE half of the detect tuple is wanted here: it is what reaches
    `classify` and what populates `ha_platform`. The NODE half says which side of an HA pair
    this is, which is not a question this package asks."""
    wire(DMIInfo(system_product_name="TRUENAS-M50"), lambda: ("ECHOWARP", "B"))

    info = probe.get_hardware_info()

    assert info.ha_platform == "ECHOWARP"
    assert info.is_ha_capable is True
    assert info.platform is Platform.IX_HARDWARE
    assert info.hardware_class is HardwareClass.TRUENAS_HW


def test_detection_failure_propagates(wire):
    """A detector that raises takes the whole classification with it. The
    chassis tag cannot say whether this is one half of an HA pair, so there is
    no honest answer to fall back to."""

    def boom():
        raise OSError("no enclosure")

    wire(DMIInfo(system_product_name="TRUENAS-MINI-R"), boom)
    with pytest.raises(OSError):
        probe.get_hardware_info()
