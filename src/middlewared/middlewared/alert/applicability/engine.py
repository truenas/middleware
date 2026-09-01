from __future__ import annotations

import typing
from collections.abc import Callable

from middlewared.utils.entitlements import EntitlementFacts

if typing.TYPE_CHECKING:
    from middlewared.alert.base import AlertClass, AlertSource

__all__ = (
    "Rule",
    "applies",
    "applies_for_listing",
    "declaration_rule_name",
    "rule_name",
)


Rule: typing.TypeAlias = Callable[[EntitlementFacts], bool]
"""A predicate over the facts of one system.

Rules are named functions: ``rule_name`` reports a declaration's rule by its ``__name__``.
"""


def applies(rule: Rule | None, facts: EntitlementFacts) -> bool:
    """Whether a declaration carrying `rule` applies to a system with `facts`.

    ``None`` is the default on both AlertClass and AlertSource, so forgetting a rule and choosing
    none are the same declaration.
    """
    return True if rule is None else rule(facts)


def applies_for_listing(declaration: type[AlertClass], facts: EntitlementFacts) -> bool:
    """Whether `declaration` belongs in the settings catalogue of a system with `facts`.

    ``listed_only_when`` narrows ``applies_to`` for the catalogue and nowhere else: a class it
    excludes is still evaluated, still displayed and still sent.
    """
    return applies(declaration.applies_to, facts) and applies(declaration.listed_only_when, facts)


def rule_name(rule: Rule | None) -> str:
    return "unconstrained" if rule is None else getattr(rule, "__name__", repr(rule))


def declaration_rule_name(declaration: type[AlertSource] | type[AlertClass]) -> str:
    """The vocabulary name `declaration` gated itself on, for diagnostics.

    A diagnostic is not an enforcement point and must not become one.
    """
    return rule_name(declaration.applies_to)
