from __future__ import annotations

import typing
from dataclasses import dataclass

from middlewared.utils.entitlements import EntitlementFacts, check_entitlement

if typing.TYPE_CHECKING:
    from middlewared.utils.hardware import HardwareClass


__all__ = (
    "AllOf",
    "AnyOf",
    "EntitlementRule",
    "HardwareRule",
    "LicensePresentRule",
    "ListedDeclaration",
    "Rule",
    "applies",
    "applies_for_listing",
)


@dataclass(frozen=True, kw_only=True, slots=True)
class HardwareRule:
    """Applies only on the named hardware classes."""

    classes: frozenset[HardwareClass]
    """Hardware classes this declaration is meant for."""


@dataclass(frozen=True, slots=True)
class LicensePresentRule:
    """Applies wherever a license exists, whatever type it is and whatever it grants.

    For declarations whose subject *is* the license. Anything asking what the license
    grants is an ``EntitlementRule``: this rule cannot tell an enterprise system from a
    Mini.
    """


@dataclass(frozen=True, kw_only=True, slots=True)
class EntitlementRule:
    """Applies where the entitlement policy grants `feature`.

    Delegated rather than reimplemented, so a feature has one definition in the tree and
    an alert cannot drift from the code gating the feature it reports on.
    ``check_entitlement`` raises for a feature the policy does not know, so a name with no
    ``POLICY`` entry fails on the first evaluation instead of quietly denying everywhere.
    """

    feature: str
    """Feature key, or ``DerivedEntitlement`` member, the policy is asked about."""


@dataclass(frozen=True, kw_only=True, slots=True)
class AnyOf:
    """Applies when any member rule applies. With no members it applies nowhere."""

    rules: tuple[Rule, ...]
    """Member rules."""


@dataclass(frozen=True, kw_only=True, slots=True)
class AllOf:
    """Applies when every member rule applies. With no members it applies everywhere."""

    rules: tuple[Rule, ...]
    """Member rules."""


Rule: typing.TypeAlias = typing.Union[HardwareRule, LicensePresentRule, EntitlementRule, "AnyOf", "AllOf"]


class ListedDeclaration(typing.Protocol):
    """An alert class as the settings catalogue sees it."""

    applies_to: Rule | None
    listed_only_when: Rule | None


def applies(rule: Rule | None, facts: EntitlementFacts) -> bool:
    """Whether a declaration carrying `rule` applies to a system with `facts`.

    ``None`` states no constraint and applies everywhere -- which is what an
    undeclared alert has always meant.
    """
    if rule is None:
        return True
    if isinstance(rule, HardwareRule):
        return facts.hardware_class in rule.classes
    if isinstance(rule, LicensePresentRule):
        return facts.license is not None
    if isinstance(rule, EntitlementRule):
        return check_entitlement(rule.feature, facts).entitled
    if isinstance(rule, AnyOf):
        return any(applies(member, facts) for member in rule.rules)
    return all(applies(member, facts) for member in rule.rules)


def applies_for_listing(declaration: type[ListedDeclaration], facts: EntitlementFacts) -> bool:
    """Whether `declaration` belongs in the settings catalogue of a system with `facts`.

    The only place ``listed_only_when`` is read. It narrows ``applies_to`` for the catalogue
    and nowhere else: a class it excludes is still evaluated, still displayed and still sent.
    Consulting it at any other enforcement point would silence alerts that already exist.
    """
    return applies(declaration.applies_to, facts) and applies(declaration.listed_only_when, facts)
