from __future__ import annotations

import enum
import typing
from dataclasses import dataclass

from middlewared.utils.entitlements import DerivedEntitlement, EntitlementFacts, check_entitlement

if typing.TYPE_CHECKING:
    from .facts import AlertFacts, HardwareClass


__all__ = ("AnyOf", "HardwareRule", "LicenseRequirement", "LicenseRule", "Rule", "applies")


class LicenseRequirement(enum.Enum):
    """What a declaration needs from the license axis."""

    LICENSED = "LICENSED"
    """A license exists, of any type: the alert's subject is the license itself."""
    HA = "HA"
    """The license grants HA. Resolved by the entitlement policy, so there is one
    definition of this in the tree and it is the one ``failover.licensed`` reads."""


@dataclass(frozen=True, kw_only=True, slots=True)
class HardwareRule:
    """Applies only on the named hardware classes."""

    classes: frozenset[HardwareClass]
    """Hardware classes this declaration is meant for."""


@dataclass(frozen=True, kw_only=True, slots=True)
class LicenseRule:
    """Applies only when the license satisfies ``requirement``."""

    requirement: LicenseRequirement
    """What the license has to grant."""


@dataclass(frozen=True, kw_only=True, slots=True)
class AnyOf:
    """Applies when any member rule applies.

    Exactly one declaration needs it: the no-license alert, whose subject is a
    machine that is *expected* to carry a license -- iX-built, or already
    licensed. That is a genuine disjunction across the two axes, not a legacy
    predicate smuggled back in.
    """

    rules: tuple[Rule, ...]
    """Member rules; the declaration applies when any one of them does."""


Rule: typing.TypeAlias = typing.Union[HardwareRule, LicenseRule, "AnyOf"]


def applies(rule: Rule | None, facts: AlertFacts) -> bool:
    """Whether a declaration carrying `rule` applies to a system with `facts`.

    ``None`` states no constraint and applies everywhere -- which is what an
    undeclared alert has always meant.
    """
    if rule is None:
        return True
    if isinstance(rule, HardwareRule):
        return facts.hardware_class in rule.classes
    if isinstance(rule, AnyOf):
        return any(applies(member, facts) for member in rule.rules)
    if rule.requirement is LicenseRequirement.HA:
        return check_entitlement(
            DerivedEntitlement.HA,
            EntitlementFacts(hardware_class=facts.hardware_class, license=facts.license),
        ).entitled
    return facts.license is not None
