import pytest
from ixhardware import DMIInfo

from middlewared.utils.hardware import detect, probe
from middlewared.utils.hardware.types import HardwareClass, Platform


@pytest.fixture(autouse=True)
def uncached():
    """Both ``get_hardware_info`` and the detector it calls cache, so every
    test here has to start from a cold cache and must not leave a warm one
    behind for the next file. ``detect_platform`` is mocked out below, but
    clearing only one of the two would go wrong the first time it is not."""
    probe.get_hardware_info.cache_clear()
    detect.detect_platform.cache_clear()
    yield
    probe.get_hardware_info.cache_clear()
    detect.detect_platform.cache_clear()


@pytest.fixture
def wire(monkeypatch):
    """Stand in for both impure inputs: DMI, and the platform detector."""

    def build(dmi: DMIInfo, detect):
        monkeypatch.setattr(probe, "parse_dmi", lambda: dmi)
        monkeypatch.setattr(probe, "detect_platform", detect)

    return build


def test_detect_result_reaches_classify(wire):
    """The HARDWARE half of the detect tuple is what classify is given."""
    wire(DMIInfo(system_product_name="Standard PC"), lambda: ("IXKVM", "A"))
    info = probe.get_hardware_info()
    assert info.platform is Platform.IXKVM
    assert info.hardware_class is HardwareClass.TRUENAS_HW


def test_node_half_is_discarded(wire):
    """NODE says which side of an HA pair this is, which changes nothing here."""
    dmi = DMIInfo(system_product_name="Standard PC")
    wire(dmi, lambda: ("BHYVE", "A"))
    a = probe.get_hardware_info()
    probe.get_hardware_info.cache_clear()
    wire(dmi, lambda: ("BHYVE", "B"))
    assert probe.get_hardware_info() == a


def test_manual_falls_through_to_dmi(wire):
    """MANUAL is not an answer, so the chassis tag decides."""
    wire(DMIInfo(system_product_name="TRUENAS-MINI-R"), lambda: ("MANUAL", "MANUAL"))
    info = probe.get_hardware_info()
    assert info.platform is Platform.MINI
    assert info.hardware_class is HardwareClass.MINI


def test_dmi_still_supplies_the_chassis_field(wire):
    """Detection sets the platform; the raw tag still comes from DMI."""
    wire(DMIInfo(system_product_name="TRUENAS-M50"), lambda: ("ECHOWARP", "A"))
    info = probe.get_hardware_info()
    assert info.platform is Platform.IX_HARDWARE
    assert info.chassis == "TRUENAS-M50"


def test_detection_failure_falls_back_to_manual(wire):
    """A detector that raises must not take the whole classification with it;
    it degrades to exactly the chassis-only path."""

    def boom():
        raise OSError("no enclosure")

    wire(DMIInfo(system_product_name="TRUENAS-MINI-R"), boom)
    info = probe.get_hardware_info()
    assert info.platform is Platform.MINI
    assert info.hardware_class is HardwareClass.MINI


def test_detection_failure_on_a_whitebox_is_generic(wire):
    def boom():
        raise RuntimeError("ipmi-raw exploded")

    wire(DMIInfo(system_manufacturer="Supermicro", system_product_name="X11SSH-F"), boom)
    assert probe.get_hardware_info().hardware_class is HardwareClass.GENERIC


def test_get_hardware_class_is_the_class_field(wire):
    wire(DMIInfo(system_product_name="TRUENAS-M50"), lambda: ("MANUAL", "MANUAL"))
    assert probe.get_hardware_class() is probe.get_hardware_info().hardware_class


def test_result_is_cached(wire):
    calls = []

    def detect():
        calls.append(None)
        return ("MANUAL", "MANUAL")

    wire(DMIInfo(system_product_name="TRUENAS-M50"), detect)
    probe.get_hardware_info()
    probe.get_hardware_info()
    assert len(calls) == 1
