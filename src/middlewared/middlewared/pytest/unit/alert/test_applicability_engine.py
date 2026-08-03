import pytest
from truenas_pylicensed import LicenseType

from middlewared.alert.applicability import (
    ANY_LICENSE,
    HA_LICENSED,
    AllOf,
    AnyOf,
    HardwareRule,
    applies,
)
from middlewared.pytest.unit.utils.test_entitlements import make_license
from middlewared.utils.entitlements import DerivedEntitlement, EntitlementFacts, check_entitlement
from middlewared.utils.hardware import HardwareClass

NO_LICENSE = None
PLAIN_LICENSE = make_license(type_=LicenseType.ENTERPRISE_SINGLE)
HA_LICENSE = make_license(type_=LicenseType.ENTERPRISE_HA)

TRUENAS_HW_ONLY = HardwareRule(classes=frozenset({HardwareClass.TRUENAS_HW}))
MINI_ONLY = HardwareRule(classes=frozenset({HardwareClass.MINI}))
GENERIC_OR_MINI = HardwareRule(classes=frozenset({HardwareClass.GENERIC, HardwareClass.MINI}))


def make_facts(hardware_class, license):
    return EntitlementFacts(hardware_class=hardware_class, license=license)


TABLE = [
    # An undeclared rule states no constraint, on any system.
    (None, HardwareClass.TRUENAS_HW, NO_LICENSE, True),
    (None, HardwareClass.MINI, NO_LICENSE, True),
    (None, HardwareClass.GENERIC, NO_LICENSE, True),
    (None, HardwareClass.GENERIC, HA_LICENSE, True),
    # Hardware axis: pure membership, indifferent to the license.
    (TRUENAS_HW_ONLY, HardwareClass.TRUENAS_HW, NO_LICENSE, True),
    (TRUENAS_HW_ONLY, HardwareClass.MINI, NO_LICENSE, False),
    (TRUENAS_HW_ONLY, HardwareClass.GENERIC, NO_LICENSE, False),
    (TRUENAS_HW_ONLY, HardwareClass.MINI, HA_LICENSE, False),
    (MINI_ONLY, HardwareClass.TRUENAS_HW, NO_LICENSE, False),
    (MINI_ONLY, HardwareClass.MINI, NO_LICENSE, True),
    (MINI_ONLY, HardwareClass.GENERIC, NO_LICENSE, False),
    (GENERIC_OR_MINI, HardwareClass.TRUENAS_HW, NO_LICENSE, False),
    (GENERIC_OR_MINI, HardwareClass.MINI, NO_LICENSE, True),
    (GENERIC_OR_MINI, HardwareClass.GENERIC, NO_LICENSE, True),
    (HardwareRule(classes=frozenset()), HardwareClass.TRUENAS_HW, NO_LICENSE, False),
    # License presence: any license at all, on any hardware.
    (ANY_LICENSE, HardwareClass.TRUENAS_HW, NO_LICENSE, False),
    (ANY_LICENSE, HardwareClass.GENERIC, NO_LICENSE, False),
    (ANY_LICENSE, HardwareClass.GENERIC, PLAIN_LICENSE, True),
    (ANY_LICENSE, HardwareClass.TRUENAS_HW, PLAIN_LICENSE, True),
    (ANY_LICENSE, HardwareClass.MINI, HA_LICENSE, True),
    # Entitlement: the policy decides, not the hardware.
    (HA_LICENSED, HardwareClass.TRUENAS_HW, NO_LICENSE, False),
    (HA_LICENSED, HardwareClass.TRUENAS_HW, PLAIN_LICENSE, False),
    (HA_LICENSED, HardwareClass.TRUENAS_HW, HA_LICENSE, True),
    (HA_LICENSED, HardwareClass.GENERIC, HA_LICENSE, True),
    (HA_LICENSED, HardwareClass.GENERIC, PLAIN_LICENSE, False),
    # AnyOf: the no-license alert's predicate, and its degenerate forms.
    (AnyOf(rules=()), HardwareClass.TRUENAS_HW, HA_LICENSE, False),
    (AnyOf(rules=(TRUENAS_HW_ONLY, ANY_LICENSE)), HardwareClass.TRUENAS_HW, NO_LICENSE, True),
    (AnyOf(rules=(TRUENAS_HW_ONLY, ANY_LICENSE)), HardwareClass.GENERIC, PLAIN_LICENSE, True),
    (AnyOf(rules=(TRUENAS_HW_ONLY, ANY_LICENSE)), HardwareClass.GENERIC, NO_LICENSE, False),
    (AnyOf(rules=(TRUENAS_HW_ONLY, ANY_LICENSE)), HardwareClass.MINI, NO_LICENSE, False),
    # AllOf: the conjunction, including its identity.
    (AllOf(rules=()), HardwareClass.GENERIC, NO_LICENSE, True),
    (AllOf(rules=(TRUENAS_HW_ONLY,)), HardwareClass.TRUENAS_HW, NO_LICENSE, True),
    (AllOf(rules=(TRUENAS_HW_ONLY, ANY_LICENSE)), HardwareClass.TRUENAS_HW, NO_LICENSE, False),
    (AllOf(rules=(TRUENAS_HW_ONLY, ANY_LICENSE)), HardwareClass.TRUENAS_HW, PLAIN_LICENSE, True),
    (AllOf(rules=(TRUENAS_HW_ONLY, ANY_LICENSE)), HardwareClass.GENERIC, PLAIN_LICENSE, False),
    (AllOf(rules=(TRUENAS_HW_ONLY, HA_LICENSED)), HardwareClass.TRUENAS_HW, HA_LICENSE, True),
    (AllOf(rules=(TRUENAS_HW_ONLY, HA_LICENSED)), HardwareClass.TRUENAS_HW, PLAIN_LICENSE, False),
    # Nested: each combinator recurses into members of any kind, including the other.
    (AnyOf(rules=(AnyOf(rules=(MINI_ONLY,)), HA_LICENSED)), HardwareClass.MINI, NO_LICENSE, True),
    (AnyOf(rules=(AnyOf(rules=(MINI_ONLY,)), HA_LICENSED)), HardwareClass.GENERIC, HA_LICENSE, True),
    (AnyOf(rules=(AnyOf(rules=(MINI_ONLY,)), HA_LICENSED)), HardwareClass.GENERIC, PLAIN_LICENSE, False),
    (AnyOf(rules=(AnyOf(rules=()),)), HardwareClass.MINI, HA_LICENSE, False),
    (
        AllOf(rules=(AnyOf(rules=(MINI_ONLY, TRUENAS_HW_ONLY)), ANY_LICENSE)),
        HardwareClass.MINI,
        PLAIN_LICENSE,
        True,
    ),
    (AllOf(rules=(AnyOf(rules=(MINI_ONLY,)), ANY_LICENSE)), HardwareClass.GENERIC, PLAIN_LICENSE, False),
    (AnyOf(rules=(AllOf(rules=(TRUENAS_HW_ONLY, HA_LICENSED)), MINI_ONLY)), HardwareClass.MINI, NO_LICENSE, True),
    (AnyOf(rules=(AllOf(rules=()),)), HardwareClass.GENERIC, NO_LICENSE, True),
]


@pytest.mark.parametrize("rule,hardware_class,license,expected", TABLE)
def test_applies(rule, hardware_class, license, expected):
    assert applies(rule, make_facts(hardware_class, license)) is expected


def test_ha_matches_the_entitlement_policy():
    """HA is not reimplemented here: it has to be the same answer the entitlement policy gives.

    Asked of the shipped ``HA_LICENSED`` rather than a copy of it, so this proves the name every
    HA declaration in the tree carries resolves to the policy's answer.
    """
    for hardware_class in HardwareClass:
        for license in (NO_LICENSE, PLAIN_LICENSE, HA_LICENSE):
            entitlement = check_entitlement(
                DerivedEntitlement.HA,
                EntitlementFacts(hardware_class=hardware_class, license=license),
            )
            assert applies(HA_LICENSED, make_facts(hardware_class, license)) is entitlement.entitled
