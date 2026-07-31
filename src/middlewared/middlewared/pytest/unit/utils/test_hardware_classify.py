import pytest
from ixhardware import PLATFORM_PREFIXES, DMIInfo

from middlewared.utils.hardware import (
    HardwareClass,
    Platform,
    classify,
    classify_platform,
    hardware_class_for,
)


def dmi(**kwargs) -> DMIInfo:
    return DMIInfo(**kwargs)


# (a) Every shipped platform prefix resolves to iX hardware.
@pytest.mark.parametrize("prefix", PLATFORM_PREFIXES)
def test_platform_prefixes_are_ix_hardware(prefix):
    # FREENAS-MINI is the one prefix that names a Mini rather than an
    # appliance, so it is covered by the Mini cases instead.
    expected = Platform.MINI if "MINI" in prefix else Platform.IX_HARDWARE
    assert classify_platform(dmi(system_product_name=f"{prefix}50")) is expected


@pytest.mark.parametrize(
    "product",
    ["TRUENAS-M50", "TRUENAS-Z20", "TRUENAS-F100", "TRUENAS-H10", "TRUENAS-V260", "TRUENAS-R20"],
)
def test_real_chassis_tags_are_ix_hardware(product):
    assert classify_platform(dmi(system_product_name=product)) is Platform.IX_HARDWARE


# (b) Minis.
@pytest.mark.parametrize("product", ["TRUENAS-MINI-X+", "FREENAS-MINI-X", "TRUENAS-MINI-R"])
def test_minis(product):
    assert classify_platform(dmi(system_product_name=product)) is Platform.MINI


# (c) Nothing recognizable at all.
def test_empty_dmi_is_generic():
    assert classify_platform(dmi()) is Platform.GENERIC


def test_commodity_hardware_is_generic():
    info = dmi(system_manufacturer="Supermicro", system_product_name="X11SSH-F")
    assert classify_platform(info) is Platform.GENERIC


# (d) X10 baseboard fallback: production did not burn the chassis tag, so the
# motherboard model is the only evidence this is an appliance.
def test_x10_baseboard_fallback():
    info = dmi(system_product_name="Super Server", baseboard_product_name="iXsystems TrueNAS X10")
    assert classify_platform(info) is Platform.IX_HARDWARE
    assert classify(info).chassis == "TRUENAS-X"


# (e) QEMU stamped as an HA node.
@pytest.mark.parametrize("serial", ["ha", "ha1", "ha_something", "x_c1", "x_c2"])
def test_qemu_ha_serials_are_ixkvm(serial):
    info = dmi(system_manufacturer="QEMU", system_product_name="Standard PC", system_serial_number=serial)
    assert classify_platform(info) is Platform.IXKVM


@pytest.mark.parametrize("serial", ["", "abc123", "_c3", "notha"])
def test_qemu_without_ha_serial_is_generic(serial):
    info = dmi(system_manufacturer="QEMU", system_product_name="Standard PC", system_serial_number=serial)
    assert classify_platform(info) is Platform.GENERIC


# (f) bhyve turns on the backplane the caller found, not on DMI alone.
@pytest.mark.parametrize("present,expected", [(True, Platform.BHYVE), (False, Platform.GENERIC)])
def test_bhyve_requires_backplane(present, expected):
    info = dmi(system_product_name="BHYVE")
    assert classify_platform(info, ha_backplane_present=present) is expected


def test_backplane_alone_does_not_make_a_bhyve():
    assert classify_platform(dmi(), ha_backplane_present=True) is Platform.GENERIC


# (g) Chassis wins over the QEMU stamp: a VM claiming to be an appliance is
# taken at its word, which is where this deliberately diverges from
# detect_platform's QEMU-first ordering.
def test_spoofed_chassis_under_qemu_is_hardware():
    info = dmi(system_manufacturer="QEMU", system_product_name="TRUENAS-M50", system_serial_number="ha1")
    assert classify_platform(info) is Platform.IX_HARDWARE


# (h) Platform -> HardwareClass mapping.
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


# (i) classify() ties the three fields together.
@pytest.mark.parametrize(
    "info,platform,hardware_class,chassis",
    [
        (dmi(system_product_name="TRUENAS-M50"), Platform.IX_HARDWARE, HardwareClass.TRUENAS_HW, "TRUENAS-M50"),
        (dmi(system_product_name="TRUENAS-MINI-R"), Platform.MINI, HardwareClass.MINI, "TRUENAS-MINI-R"),
        (dmi(), Platform.GENERIC, HardwareClass.GENERIC, "TRUENAS-UNKNOWN"),
        (
            dmi(system_manufacturer="QEMU", system_product_name="Standard PC", system_serial_number="ha1"),
            Platform.IXKVM,
            HardwareClass.TRUENAS_HW,
            "TRUENAS-UNKNOWN",
        ),
    ],
)
def test_classify(info, platform, hardware_class, chassis):
    result = classify(info)
    assert result.platform is platform
    assert result.hardware_class is hardware_class
    assert result.chassis == chassis


def test_classify_bhyve():
    result = classify(dmi(system_product_name="BHYVE"), ha_backplane_present=True)
    assert result.platform is Platform.BHYVE
    assert result.hardware_class is HardwareClass.TRUENAS_HW


# (j) HardwareClass.from_chassis, migrated from test_entitlements.
@pytest.mark.parametrize(
    "chassis,expected",
    [
        ("TRUENAS-UNKNOWN", HardwareClass.GENERIC),
        ("TRUENAS-MINI-X+", HardwareClass.MINI),
        ("FREENAS-MINI-X", HardwareClass.MINI),
        ("TRUENAS-M50", HardwareClass.TRUENAS_HW),
        ("TRUENAS-F100", HardwareClass.TRUENAS_HW),
    ],
)
def test_hardware_class_from_chassis(chassis, expected):
    assert HardwareClass.from_chassis(chassis) is expected
