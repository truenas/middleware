from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from middlewared.utils.service.call_mixin import CallMixin

if TYPE_CHECKING:
    from middlewared.main import Middleware


class LicenseDelegate(CallMixin, ABC):
    """One policy row: what keeps the feature in grace, the alert text, the re-grant behaviour."""

    feature: str
    # service.control names whose user-session STOP or RESTART ends the grace
    services: frozenset[str] = frozenset()

    def __init__(self, middleware: Middleware) -> None:
        self.middleware = middleware

    async def in_use(self) -> bool:
        for service in self.services:
            if await self.call2(self.s.service.started, service):
                return True
        return False

    @abstractmethod
    async def alert_lines(self, in_grace: bool) -> list[str]:
        """Alert text while the feature is not entitled; [] when nothing applies. `in_grace`: the
        feature is in the grace record, so describe what is still served and the cut point."""

    async def on_grant(self) -> None:
        """Restore what the saved settings describe. Background task on the serving node after a grant."""


def touches(changed: frozenset[str] | None, *features: str) -> bool:
    """For `system.post_license_update` owner hooks; `changed` is None when the caller has no diff to give."""
    return changed is None or not changed.isdisjoint(features)
