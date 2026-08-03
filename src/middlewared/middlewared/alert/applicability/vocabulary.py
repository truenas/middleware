"""The populations an alert declaration may be gated on.

Every ``applies_to`` and ``listed_only_when`` in the tree names one of these. Adding a name
here is a policy decision, not a convenience: a new name asserts that some set of machines is
worth distinguishing from every other set, and every declaration that takes it inherits that
assertion. Changing what a name covers moves every declaration using it at once, which is the
point -- the population a declaration applies to is decided and reviewed in this one file
rather than reconstructed from a rule expression at each of a hundred declaration sites.
"""

from __future__ import annotations

from middlewared.utils.entitlements import DerivedEntitlement
from middlewared.utils.hardware import HardwareClass

from .engine import AnyOf, EntitlementRule, HardwareRule, LicensePresentRule

__all__ = (
    "ANY_LICENSE",
    "APPLIANCE_OR_HA_LICENSED",
    "EXPECTED_TO_BE_LICENSED",
    "HA_LICENSED",
    "MINI_HARDWARE",
    "NOT_APPLIANCE_HARDWARE",
    "TRUENAS_HARDWARE",
)

TRUENAS_HARDWARE = HardwareRule(classes=frozenset({HardwareClass.TRUENAS_HW}))
"""iX-built appliances other than a Mini, plus the HA virtual machines that stand in for one.
Licensed or not: this asks what the machine is, never what it paid for."""

MINI_HARDWARE = HardwareRule(classes=frozenset({HardwareClass.MINI}))
"""iX Mini appliances, licensed or not."""

NOT_APPLIANCE_HARDWARE = HardwareRule(classes=frozenset(HardwareClass) - {HardwareClass.TRUENAS_HW})
"""Everything that is not an iX appliance: commodity hardware, ordinary virtual machines, and
Minis. Defined as the complement of ``HardwareClass.is_appliance`` so that a hardware class
added later lands here by default rather than silently falling out of both halves, and so that
a Mini whose chassis tag has degraded to GENERIC is still covered."""

ANY_LICENSE = LicensePresentRule()
"""Machines carrying a license of any type, on any hardware. For declarations whose subject is
the license itself. This is not "is this an enterprise system": a Mini with a MINI-R license
satisfies it and an unlicensed M-series does not."""

HA_LICENSED = EntitlementRule(feature=DerivedEntitlement.HA)
"""Machines whose license grants high availability. Resolved by the entitlement policy, so this
is the same answer ``failover.licensed`` gives and there is one definition of HA in the tree."""

APPLIANCE_OR_HA_LICENSED = AnyOf(rules=(TRUENAS_HARDWARE, HA_LICENSED))
"""Machines where high availability is a live concern: an iX appliance, which can be licensed
for HA at any moment, or a machine already licensed for it. Alert classes in the HA family use
this rather than the hardware half alone, so that a machine which is HA-licensed but not iX
hardware can still display and send what its source produced."""

EXPECTED_TO_BE_LICENSED = AnyOf(rules=(TRUENAS_HARDWARE, ANY_LICENSE))
"""Machines that ought to carry a license: iX-built, or already licensed. The population the
license alerts are addressed to -- a whitebox with no license is not failing to have one."""
