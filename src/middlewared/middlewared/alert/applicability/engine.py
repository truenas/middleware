from __future__ import annotations

import typing
from collections.abc import Callable

from middlewared.utils.entitlements import EntitlementFacts

__all__ = (
    "Declaration",
    "ListedDeclaration",
    "Rule",
    "applies",
    "applies_for_listing",
    "declaration_rule_name",
    "rule_name",
)


Rule: typing.TypeAlias = Callable[[EntitlementFacts], bool]
"""A predicate over the facts of one system.

A rule is nothing but a function, so a population is defined the same way a feature flag is and
the two can be the same object. Nothing introspects a rule's structure; the only thing ever asked
of one is its answer, and -- for diagnostics -- the name it was defined under.
"""


class Declaration(typing.Protocol):
    """An alert class or source as the engine sees it."""

    applies_to: Rule | None


class ListedDeclaration(Declaration, typing.Protocol):
    """An alert class as the settings catalogue sees it."""

    listed_only_when: Rule | None


def applies(rule: Rule | None, facts: EntitlementFacts) -> bool:
    """Whether a declaration carrying `rule` applies to a system with `facts`.

    ``None`` states no constraint and applies everywhere -- which is what an
    undeclared alert has always meant.
    """
    return True if rule is None else rule(facts)


def applies_for_listing(declaration: type[ListedDeclaration], facts: EntitlementFacts) -> bool:
    """Whether `declaration` belongs in the settings catalogue of a system with `facts`.

    The only place ``listed_only_when`` is read. It narrows ``applies_to`` for the catalogue
    and nowhere else: a class it excludes is still evaluated, still displayed and still sent.
    Consulting it at any other enforcement point would silence alerts that already exist.
    """
    return applies(declaration.applies_to, facts) and applies(declaration.listed_only_when, facts)


def rule_name(rule: Rule | None) -> str:
    """The vocabulary name a declaration gated itself on, for diagnostics."""
    return "unconstrained" if rule is None else getattr(rule, "__name__", repr(rule))


def declaration_rule_name(declaration: type[Declaration]) -> str:
    """The vocabulary name `declaration` gated itself on, for diagnostics.

    Here rather than at the call site so that ``applies_to`` keeps a single reader outside the
    declarations themselves; a diagnostic is not an enforcement point and must not become one.
    """
    return rule_name(declaration.applies_to)
