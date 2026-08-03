"""One reading of the facts, and every applicability answer that follows from it."""

from __future__ import annotations

from middlewared.utils.entitlements import EntitlementFacts

from .engine import Declaration, ListedDeclaration, applies, applies_for_listing

__all__ = ("Applicability",)


class Applicability:
    """Every applicability answer for one reading of the facts.

    Holds no middleware object: it takes facts, so the whole tree of declarations can be
    evaluated against synthesized populations. Answers are memoized per declaration, which
    is the identity that is stable whatever shape a rule has.

    A caching facade and nothing more -- the answers come from the free ``applies`` and
    ``applies_for_listing``, which stay pure and directly testable.
    """

    __slots__ = ("_facts", "_class_memo", "_listed_memo", "_source_memo")

    def __init__(self, facts: EntitlementFacts) -> None:
        self._facts = facts
        self._class_memo: dict[type[ListedDeclaration], bool] = {}
        self._listed_memo: dict[type[ListedDeclaration], bool] = {}
        self._source_memo: dict[type[Declaration], bool] = {}

    @property
    def facts(self) -> EntitlementFacts:
        """The facts every answer here was derived from."""
        return self._facts

    def class_applies(self, klass: type[ListedDeclaration]) -> bool:
        """Whether `klass` applies here: displayed, sent, and offered in the catalogue."""
        try:
            return self._class_memo[klass]
        except KeyError:
            self._class_memo[klass] = result = applies(klass.applies_to, self._facts)
            return result

    def class_listed(self, klass: type[ListedDeclaration]) -> bool:
        """Whether `klass` belongs in this system's settings catalogue."""
        try:
            return self._listed_memo[klass]
        except KeyError:
            self._listed_memo[klass] = result = applies_for_listing(klass, self._facts)
            return result

    def source_runs(self, source: type[Declaration]) -> bool:
        """Whether `source`'s own rule admits this system.

        Takes the class, never an instance: a rule is a function, so reading it off an instance
        would bind that instance as the first argument.
        """
        try:
            return self._source_memo[source]
        except KeyError:
            self._source_memo[source] = result = applies(source.applies_to, self._facts)
            return result
