"""The populations an alert declaration may be gated on.

Every ``applies_to`` and ``listed_only_when`` in the tree names one of these. Adding a name
here is a policy decision, not a convenience: a new name asserts that some set of machines is
worth distinguishing from every other set, and every declaration that takes it inherits that
assertion. Changing what a name covers moves every declaration using it at once, which is the
point -- the population a declaration applies to is decided and reviewed in this one file
rather than reconstructed from a rule expression at each declaration site.

A population is a plain predicate over the facts, so one can be written in terms of another and
a name reads at its declaration site exactly as it reads here.
"""

from __future__ import annotations

from middlewared.utils.entitlements import DerivedEntitlement, EntitlementFacts, check_entitlement
from middlewared.utils.hardware import HardwareClass

__all__ = (
    "ANY_LICENSE",
    "APPLIANCE_OR_HA_LICENSED",
    "EXPECTED_TO_BE_LICENSED",
    "HA_LICENSED",
    "MINI_HARDWARE",
    "NOT_APPLIANCE_HARDWARE",
    "TRUENAS_HARDWARE",
    "TRUENAS_OR_MINI_HARDWARE",
)


def TRUENAS_HARDWARE(facts: EntitlementFacts) -> bool:
    """iX-built appliances other than a Mini, plus the HA virtual machines that stand in for one.
    Licensed or not: this asks what the machine is, never what it paid for."""
    return facts.hardware_class.is_appliance


def MINI_HARDWARE(facts: EntitlementFacts) -> bool:
    """iX Mini appliances, licensed or not."""
    return facts.hardware_class is HardwareClass.MINI


def TRUENAS_OR_MINI_HARDWARE(facts: EntitlementFacts) -> bool:
    """Every machine iX builds, Minis included, for questions about the hardware rather than what
    it was licensed as -- ECC memory reporting, for one. Composed from the two names rather than as
    the complement of GENERIC so a hardware class added later lands outside it and has to be added
    here deliberately."""
    return TRUENAS_HARDWARE(facts) or MINI_HARDWARE(facts)


def NOT_APPLIANCE_HARDWARE(facts: EntitlementFacts) -> bool:
    """Everything that is not an iX appliance: commodity hardware, ordinary virtual machines, and
    Minis. Defined as the complement of ``HardwareClass.is_appliance`` so that a hardware class
    added later lands here by default rather than silently falling out of both halves, and so that
    a Mini whose chassis tag has degraded to GENERIC is still covered."""
    return not facts.hardware_class.is_appliance


def ANY_LICENSE(facts: EntitlementFacts) -> bool:
    """Machines carrying a license of any type, on any hardware. For declarations whose subject is
    the license itself. This is not "is this an enterprise system": a licensed Mini satisfies it and
    an unlicensed appliance does not."""
    return facts.license is not None


def HA_LICENSED(facts: EntitlementFacts) -> bool:
    """Machines whose license grants high availability, as the entitlement policy resolves it --
    every consumer of HA in the tree asks the policy the same question."""
    return check_entitlement(DerivedEntitlement.HA, facts).entitled


def APPLIANCE_OR_HA_LICENSED(facts: EntitlementFacts) -> bool:
    """Machines where high availability is a live concern: an iX appliance, which can be licensed
    for HA at any moment, or a machine already licensed for it. The HA alert classes take this
    rather than the hardware half alone, so an HA-licensed machine on non-iX hardware can still
    display and send what its source produced."""
    return TRUENAS_HARDWARE(facts) or HA_LICENSED(facts)


def EXPECTED_TO_BE_LICENSED(facts: EntitlementFacts) -> bool:
    """Machines that ought to carry a license: iX-built, or already licensed. The population the
    license alerts are addressed to -- a whitebox with no license is not failing to have one."""
    return TRUENAS_HARDWARE(facts) or ANY_LICENSE(facts)
