from __future__ import annotations
import enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from middlewared.main import Middleware


class LicenseReconcileAction(enum.StrEnum):
    """What a delegate wants done to bring its config back in line with the license."""

    RENDER = "RENDER"
    # Reload the service, which regenerates its config first, so it picks the new config up
    RELOAD = "RELOAD"
    # Restart the service, which regenerates its config first, because a reload is not enough
    RESTART = "RESTART"


class LicenseReconcileDelegate:
    """
    Represents a subsystem whose on-disk configuration is derived from the license.

    A license change (upload or replacement) can silently invalidate config that was rendered
    under the previous entitlements. Each affected subsystem registers a delegate describing
    which `etc` groups it owns and what has to happen after they are re-rendered, so that the
    reconcile pass converges every affected subsystem.

    `etc_groups` is the *static superset* of every group this delegate may own. It has to be
    declarable without making any call, because it is what uniqueness checking is written
    against.

    Only `RENDER` delegates are rendered by the reconcile runner, from `resolve_groups()`.
    `RELOAD` and `RESTART` delegates are rendered by `service.control` from the service's own
    `select_etc()`, so the runner does not render them as well; for those, `etc_groups` is a
    declaration of ownership rather than a list anyone renders from.
    """

    name: str = NotImplemented
    # Static union of every `etc` group this delegate may own. No two delegates may claim
    # the same group. Only rendered from when `action` is RENDER; see the class docstring.
    etc_groups: tuple[str, ...] = ()
    # Service to act on, or None when this delegate only renders config
    service: str | None = None
    action: LicenseReconcileAction = LicenseReconcileAction.RENDER
    # Lower runs first. Ties keep registration order.
    order: int = 0

    async def resolve_groups(self, middleware: Middleware) -> list[str]:
        """
        Return the `etc` groups to regenerate on this system.

        Defaults to the whole of `etc_groups`. Override when the subsystem chooses between
        mutually exclusive groups at runtime, and the choice needs a call to determine.
        """
        return list(self.etc_groups)

    async def should_run(self, middleware: Middleware) -> bool:
        """
        Return whether this delegate should be processed at all.

        Returning `False` skips the delegate outright, which means its `etc` groups are not
        re-rendered either, not just that the service verb is not issued.

        Defaults to `True`. Override when acting is pointless or harmful in some states,
        e.g. a delegate that reloads a service which is not currently running.
        """
        return True
