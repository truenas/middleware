import pytest
from ixhardware import DMIInfo

from middlewared.utils.hardware import (
    HardwareClass,
    Platform,
    classify,
    hardware_class_for,
)


def dmi(**kwargs) -> DMIInfo:
    return DMIInfo(**kwargs)


# One table over whole `classify()` results, so every rule the classifier applies is visible in the answer.
CLASSIFY_TABLE = [
    (dmi(system_product_name="TRUENAS-M50"), "MANUAL", Platform.IX_HARDWARE, HardwareClass.TRUENAS_HW, "TRUENAS-M50"),
    # A Mini is iX-built but gets its own column.
    (
        dmi(system_product_name="TRUENAS-MINI-R"),
        "MANUAL",
        Platform.MINI,
        HardwareClass.MINI,
        "TRUENAS-MINI-R",
    ),
    # Nothing recognizable at all.
    (dmi(), "MANUAL", Platform.GENERIC, HardwareClass.GENERIC, "TRUENAS-UNKNOWN"),
    # Commodity hardware advertises a real product name and is still generic.
    (
        dmi(system_manufacturer="Supermicro", system_product_name="X11SSH-F"),
        "MANUAL",
        Platform.GENERIC,
        HardwareClass.GENERIC,
        "TRUENAS-UNKNOWN",
    ),
    # X10 baseboard fallback: production did not burn the chassis tag, so the motherboard
    # model is the only evidence this is an appliance.
    (
        dmi(system_product_name="Super Server", baseboard_product_name="iXsystems TrueNAS X10"),
        "MANUAL",
        Platform.IX_HARDWARE,
        HardwareClass.TRUENAS_HW,
        "TRUENAS-X",
    ),
    # An HA virtual machine stands in for an appliance and is entitled as one.
    (
        dmi(system_manufacturer="QEMU", system_product_name="Standard PC", system_serial_number="ha1"),
        "IXKVM",
        Platform.IXKVM,
        HardwareClass.TRUENAS_HW,
        "TRUENAS-UNKNOWN",
    ),
    # Detection wins over the chassis tag, so a Mini-tagged HA VM lands in the appliance
    # column. The raw tag is still reported truthfully; only the column moved.
    (
        dmi(system_manufacturer="QEMU", system_product_name="TRUENAS-MINI-R", system_serial_number="ha1"),
        "IXKVM",
        Platform.IXKVM,
        HardwareClass.TRUENAS_HW,
        "TRUENAS-MINI-R",
    ),
    (dmi(system_product_name="BHYVE"), "BHYVE", Platform.BHYVE, HardwareClass.TRUENAS_HW, "TRUENAS-UNKNOWN"),
    # An unrecognized codename must land in the appliance column rather than being demoted.
    (dmi(), "WARPCORE9", Platform.IX_HARDWARE, HardwareClass.TRUENAS_HW, "TRUENAS-UNKNOWN"),
]


@pytest.mark.parametrize("info,ha_platform,platform,hardware_class,chassis", CLASSIFY_TABLE)
def test_classify(info, ha_platform, platform, hardware_class, chassis):
    result = classify(info, ha_platform=ha_platform)

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
