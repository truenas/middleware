import pytest

from middlewared.utils.hardware import (
    HardwareClass,
    Platform,
    classify,
    hardware_class_for,
)

# One table over whole `classify()` results, so every rule the classifier applies is visible in the answer.
CLASSIFY_TABLE = [
    ("TRUENAS-M50", "MANUAL", Platform.IX_HARDWARE, HardwareClass.TRUENAS_HW),
    # A Mini is iX-built but gets its own column.
    ("TRUENAS-MINI-R", "MANUAL", Platform.MINI, HardwareClass.MINI),
    # Nothing recognizable at all.
    ("TRUENAS-UNKNOWN", "MANUAL", Platform.GENERIC, HardwareClass.GENERIC),
    # An HA virtual machine stands in for an appliance and is entitled as one.
    ("TRUENAS-UNKNOWN", "IXKVM", Platform.IXKVM, HardwareClass.TRUENAS_HW),
    # Detection wins over the chassis tag, so a Mini-tagged HA VM lands in the appliance
    # column. The raw tag is still reported truthfully; only the column moved.
    ("TRUENAS-MINI-R", "IXKVM", Platform.IXKVM, HardwareClass.TRUENAS_HW),
    ("TRUENAS-UNKNOWN", "BHYVE", Platform.BHYVE, HardwareClass.TRUENAS_HW),
    # An unrecognized codename must land in the appliance column rather than being demoted.
    ("TRUENAS-UNKNOWN", "WARPCORE9", Platform.IX_HARDWARE, HardwareClass.TRUENAS_HW),
]


@pytest.mark.parametrize("chassis,ha_platform,platform,hardware_class", CLASSIFY_TABLE)
def test_classify(chassis, ha_platform, platform, hardware_class):
    result = classify(chassis=chassis, ha_platform=ha_platform)

    assert result.platform is platform
    assert result.hardware_class is hardware_class
    assert result.chassis == chassis
    assert result.ha_platform == ha_platform
    assert result.is_ha_capable is (ha_platform != "MANUAL")


@pytest.mark.parametrize(
    "platform,expected",
    [
        (Platform.IX_HARDWARE, HardwareClass.TRUENAS_HW),
        (Platform.MINI, HardwareClass.MINI),
        (Platform.IXKVM, HardwareClass.TRUENAS_HW),
        (Platform.BHYVE, HardwareClass.TRUENAS_HW),
        (Platform.GENERIC, HardwareClass.GENERIC),
    ],
)
def test_hardware_class_for(platform, expected):
    assert hardware_class_for(platform) is expected


def test_every_platform_is_mapped():
    """A new Platform member must not be able to land unmapped."""
    for platform in Platform:
        assert isinstance(hardware_class_for(platform), HardwareClass)
