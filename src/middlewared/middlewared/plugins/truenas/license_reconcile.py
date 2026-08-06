import asyncio
from typing import Any, TYPE_CHECKING

from middlewared.common.license_reconcile import LicenseReconcileAction, LicenseReconcileDelegate
from middlewared.service import Service, job, private

if TYPE_CHECKING:
    from middlewared.job import Job
    from middlewared.main import Middleware


# A delegate that only re-renders config talks to the etc plugin and nothing else, so it has no
# business taking half a minute. A delegate that also drives a service verb is bounded by that
# verb's own timeout, which `ServiceOptions.timeout` defaults to 120 seconds, so the outer bound
# here has to sit above it: otherwise this timeout fires first and the verb's own one, which is
# the informative one, never reports.
RENDER_TIMEOUT = 30
SERVICE_TIMEOUT = 180


class TrueNASLicenseService(Service):
    """
    Registry of the subsystems that have to be reconciled after a license change.

    Declared in the `truenas.license` namespace so that it is merged into the same compound
    service as the rest of the license plugin.
    """

    class Config:
        namespace = "truenas.license"
        cli_private = True

    def __init__(self, middleware: "Middleware"):
        super().__init__(middleware)
        self.reconcile_delegates_list: list[LicenseReconcileDelegate] = []

    @private
    async def register_reconcile_delegate(self, delegate: LicenseReconcileDelegate) -> None:
        if any(registered.name == delegate.name for registered in self.reconcile_delegates_list):
            raise ValueError(f"{delegate.name!r} delegate is already registered with license reconcile")

        claimed = {group: registered for registered in self.reconcile_delegates_list for group in registered.etc_groups}
        for group in delegate.etc_groups:
            if (owner := claimed.get(group)) is not None:
                # Two delegates rendering the same group would double render it in an order
                # nobody declared, so make it a startup failure instead.
                raise ValueError(
                    f"{delegate.name!r} delegate claims etc group {group!r} which is already "
                    f"claimed by the {owner.name!r} delegate"
                )

        self.reconcile_delegates_list.append(delegate)

    @private
    async def reconcile_delegates(self) -> list[LicenseReconcileDelegate]:
        """
        Return the registered delegates in the order they should be processed.

        `sorted` is stable, so delegates sharing an `order` keep their registration order.
        """
        return sorted(self.reconcile_delegates_list, key=lambda delegate: delegate.order)

    @private
    @job(lock="license_reconcile", lock_queue_size=1)
    async def reconcile(self, job: "Job") -> None:
        """
        Bring the registered subsystems back in line with the current license.

        A delegate whose `should_run` returns False is skipped entirely -- neither its `etc`
        groups nor its service verb are touched -- so this does not converge everything that
        is registered, only everything that wants converging on this system right now.

        A job rather than a plain method because the pass is bounded in minutes rather than
        seconds, and `job.set_progress` below is what makes a stuck delegate nameable in
        `core.get_jobs` while it is stuck.
        """
        delegates = await self.reconcile_delegates()
        for index, delegate in enumerate(delegates):
            # Reported before the delegate runs rather than after, so that a delegate sitting on
            # its timeout is the one named in `core.get_jobs` for as long as it sits there.
            job.set_progress(int(index / len(delegates) * 100), f"Reconciling {delegate.name}")
            try:
                timeout = SERVICE_TIMEOUT if delegate.action is not LicenseReconcileAction.RENDER else RENDER_TIMEOUT
                async with asyncio.timeout(timeout):
                    if not await delegate.should_run(self.middleware):
                        continue

                    if delegate.action is LicenseReconcileAction.RENDER:
                        for group in await delegate.resolve_groups(self.middleware):
                            await self.middleware.call("etc.generate", group)
                    else:
                        # No `etc.generate` loop here: `service.control` renders the service's own
                        # `select_etc()` on the way into reload and restart alike. Rendering here as
                        # well would regenerate every group a second time, and some of those
                        # renderers are expensive enough for that to stretch the pass out.
                        #
                        # `ha_propagate` is decided here rather than per delegate because it is a
                        # property of how this hook runs, not of any subsystem: on an HA pair both
                        # nodes reach `system.post_license_update` independently (the peer via
                        # `failover.send_license` uploading with `ha_propagate=False`, or via the
                        # remote `core.call_hook` that `failover.sync_to_peer` issues). Leaving the
                        # default of True would have `failover.service_remote` replay every verb on
                        # a node that is already reconciling itself.
                        service_job = await self.middleware.call(
                            "service.control",
                            delegate.action.value,
                            delegate.service,
                            {"ha_propagate": False},
                        )
                        await service_job.wait(raise_error=True)
            except TimeoutError:
                # The underlying job keeps running; we simply stop waiting on it so that one slow
                # subsystem cannot hold every subsystem behind it out of convergence indefinitely.
                self.logger.error("%s: timed out reconciling license state after %d seconds", delegate.name, timeout)
            except Exception:
                # Deliberately not `asyncio.gather`: a subsystem that fails to converge must not
                # take the remaining ones down with it.
                self.logger.error("%s: failed to reconcile license state", delegate.name, exc_info=True)

        job.set_progress(100, "License state reconciled")


async def _post_license_update(middleware: "Middleware", *args: Any, **kwargs: Any) -> None:
    await middleware.call("truenas.license.reconcile")


async def setup(middleware: "Middleware") -> None:
    middleware.register_hook("system.post_license_update", _post_license_update, sync=True, order=0)
