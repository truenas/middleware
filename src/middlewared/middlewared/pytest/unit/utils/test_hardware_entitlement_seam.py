"""The join between hardware detection and the entitlement engine.

`classify` decides a `HardwareClass` and `HardwareClass.is_appliance` decides which half of
every matrix row a machine reads, but the two halves are tested apart: nothing else imports
both `classify` and `check_entitlement`. A machine detected into the wrong column is entitled
out of the wrong column, and that is invisible to either suite on its own.

DEDUP is the probe. It is the only live vector whose halves disagree with no license present
(``ce=1``, ``hw=0``), so appliance and non-appliance hardware give opposite answers off one
code path, and the assertion can be on the outcome rather than on the column name.
"""

import pytest
from ixhardware import DMIInfo
from truenas_pylicensed.features import LicenseFeature

from middlewared.pytest.unit.entitlements import make_facts, make_license
from middlewared.utils.entitlements import check_entitlement
from middlewared.utils.hardware import classify

# (dmi, ha_platform, is_appliance, dedup granted with no license present)
SEAM_TABLE = [
    (DMIInfo(system_product_name="TRUENAS-M50"), "MANUAL", True, False),
    (DMIInfo(system_product_name="TRUENAS-MINI-R"), "MANUAL", False, True),
    (DMIInfo(), "MANUAL", False, True),
    (DMIInfo(system_manufacturer="Supermicro", system_product_name="X11SSH-F"), "MANUAL", False, True),
    # Production did not burn a chassis tag on the X10, so the motherboard model is the only
    # evidence it is an appliance -- and the only thing keeping unlicensed DEDUP away from it.
    (
        DMIInfo(system_product_name="Super Server", baseboard_product_name="iXsystems TrueNAS X10"),
        "MANUAL",
        True,
        False,
    ),
    (
        DMIInfo(system_manufacturer="QEMU", system_product_name="Standard PC", system_serial_number="ha1"),
        "IXKVM",
        True,
        False,
    ),
    # classify_platform reads ha_platform before the chassis tag, so this machine is entitled
    # out of the appliance column despite advertising a Mini product name. This is the only
    # place that ordering is pinned against an entitlement outcome rather than a Platform.
    (
        DMIInfo(system_manufacturer="QEMU", system_product_name="TRUENAS-MINI-R", system_serial_number="ha1"),
        "IXKVM",
        True,
        False,
    ),
]


@pytest.mark.parametrize("dmi,ha_platform,is_appliance,dedup_unlicensed", SEAM_TABLE)
def test_is_appliance_follows_detection(dmi, ha_platform, is_appliance, dedup_unlicensed):
    assert classify(dmi, ha_platform=ha_platform).hardware_class.is_appliance is is_appliance


@pytest.mark.parametrize("dmi,ha_platform,is_appliance,dedup_unlicensed", SEAM_TABLE)
def test_unlicensed_dedup_follows_the_detected_hardware_class(dmi, ha_platform, is_appliance, dedup_unlicensed):
    facts = make_facts(hardware_class=classify(dmi, ha_platform=ha_platform).hardware_class)
    assert check_entitlement(LicenseFeature.DEDUP, facts).entitled is dedup_unlicensed


@pytest.mark.parametrize("dmi,ha_platform,is_appliance,dedup_unlicensed", SEAM_TABLE)
def test_keyed_dedup_is_granted_on_every_detected_hardware_class(dmi, ha_platform, is_appliance, dedup_unlicensed):
    # The control: with the key present every row grants, so the denials above are the
    # hardware axis doing its job and not a fact object the engine cannot read.
    facts = make_facts(
        hardware_class=classify(dmi, ha_platform=ha_platform).hardware_class,
        license=make_license(feature_names=(LicenseFeature.DEDUP,)),
    )
    assert check_entitlement(LicenseFeature.DEDUP, facts).entitled is True
