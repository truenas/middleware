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
    assert classify_platform(dmi(system_product_name=f"{prefix}50"), ha_platform="MANUAL") is expected


@pytest.mark.parametrize(
    "product",
    ["TRUENAS-M50", "TRUENAS-Z20", "TRUENAS-F100", "TRUENAS-H10", "TRUENAS-V260", "TRUENAS-R20"],
)
def test_real_chassis_tags_are_ix_hardware(product):
    assert classify_platform(dmi(system_product_name=product), ha_platform="MANUAL") is Platform.IX_HARDWARE


# (b) Minis.
@pytest.mark.parametrize("product", ["TRUENAS-MINI-X+", "FREENAS-MINI-X", "TRUENAS-MINI-R"])
def test_minis(product):
    assert classify_platform(dmi(system_product_name=product), ha_platform="MANUAL") is Platform.MINI


# (c) Nothing recognizable at all.
def test_empty_dmi_is_generic():
    assert classify_platform(dmi(), ha_platform="MANUAL") is Platform.GENERIC


def test_commodity_hardware_is_generic():
    info = dmi(system_manufacturer="Supermicro", system_product_name="X11SSH-F")
    assert classify_platform(info, ha_platform="MANUAL") is Platform.GENERIC


# (d) X10 baseboard fallback: production did not burn the chassis tag, so the
# motherboard model is the only evidence this is an appliance.
def test_x10_baseboard_fallback():
    info = dmi(system_product_name="Super Server", baseboard_product_name="iXsystems TrueNAS X10")
    assert classify_platform(info, ha_platform="MANUAL") is Platform.IX_HARDWARE
    assert classify(info, ha_platform="MANUAL").chassis == "TRUENAS-X"


# (e) The detector's verdict drives the platform.
def test_ixkvm():
    info = dmi(system_manufacturer="QEMU", system_product_name="Standard PC", system_serial_number="ha1")
    assert classify_platform(info, ha_platform="IXKVM") is Platform.IXKVM


def test_bhyve():
    assert classify_platform(dmi(system_product_name="BHYVE"), ha_platform="BHYVE") is Platform.BHYVE


@pytest.mark.parametrize("codename", ["LAJOLLA2", "SUBLIGHT", "LUDICROUS", "PLAID", "ECHOWARP", "PUMA"])
def test_shipped_codenames_are_ix_hardware(codename):
    """Every codename detect can currently return, other than the two VM
    flavors, names an iX appliance."""
    assert classify_platform(dmi(), ha_platform=codename) is Platform.IX_HARDWARE


def test_unknown_codename_degrades_to_ix_hardware():
    """A platform shipped after this was written must land in the appliance
    column, not raise."""
    assert classify_platform(dmi(), ha_platform="WARPCORE9") is Platform.IX_HARDWARE


# (f) MANUAL is never an answer. It says "not one half of an HA pair", which
# is true of every single-controller appliance, so it must fall through to the
# chassis tag rather than demoting the machine.
def test_manual_falls_through_to_the_mini_tag():
    assert classify_platform(dmi(system_product_name="TRUENAS-MINI-R"), ha_platform="MANUAL") is Platform.MINI


def test_manual_falls_through_to_an_appliance_tag():
    assert classify_platform(dmi(system_product_name="TRUENAS-R20"), ha_platform="MANUAL") is Platform.IX_HARDWARE


# (g) Detection wins over the chassis tag: a VM stamped as an HA node is that
# VM whatever product name it advertises. This is the reverse of the ordering
# this module used to apply, and it is a deliberate grant.
def test_spoofed_chassis_under_qemu_is_ixkvm():
    info = dmi(system_manufacturer="QEMU", system_product_name="TRUENAS-M50", system_serial_number="ha1")
    assert classify_platform(info, ha_platform="IXKVM") is Platform.IXKVM


def test_mini_tagged_ha_vm_is_ixkvm_not_mini():
    """The licensing-visible half of that grant: a Mini-tagged HA VM is
    entitled out of the appliance column, not the Mini one."""
    info = dmi(system_manufacturer="QEMU", system_product_name="TRUENAS-MINI-R", system_serial_number="ha1")
    result = classify(info, ha_platform="IXKVM")
    assert result.platform is Platform.IXKVM
    assert result.hardware_class is HardwareClass.TRUENAS_HW
    # The raw tag is still reported truthfully; only the column moved.
    assert result.chassis == "TRUENAS-MINI-R"


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
    "info,ha_platform,platform,hardware_class,chassis",
    [
        (
            dmi(system_product_name="TRUENAS-M50"),
            "MANUAL",
            Platform.IX_HARDWARE,
            HardwareClass.TRUENAS_HW,
            "TRUENAS-M50",
        ),
        (
            dmi(system_product_name="TRUENAS-MINI-R"),
            "MANUAL",
            Platform.MINI,
            HardwareClass.MINI,
            "TRUENAS-MINI-R",
        ),
        (dmi(), "MANUAL", Platform.GENERIC, HardwareClass.GENERIC, "TRUENAS-UNKNOWN"),
        (
            dmi(system_manufacturer="QEMU", system_product_name="Standard PC", system_serial_number="ha1"),
            "IXKVM",
            Platform.IXKVM,
            HardwareClass.TRUENAS_HW,
            "TRUENAS-UNKNOWN",
        ),
    ],
)
def test_classify(info, ha_platform, platform, hardware_class, chassis):
    result = classify(info, ha_platform=ha_platform)
    assert result.platform is platform
    assert result.hardware_class is hardware_class
    assert result.chassis == chassis


def test_classify_bhyve():
    result = classify(dmi(system_product_name="BHYVE"), ha_platform="BHYVE")
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
