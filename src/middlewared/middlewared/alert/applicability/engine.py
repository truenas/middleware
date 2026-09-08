from __future__ import annotations

from collections.abc import Callable
import typing

from middlewared.utils.entitlements import EntitlementFacts

__all__ = (
    "Rule",
    "applies",
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


def rule_name(rule: Rule | None) -> str:
    return "unconstrained" if rule is None else getattr(rule, "__name__", repr(rule))
