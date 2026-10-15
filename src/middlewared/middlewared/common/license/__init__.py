from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Literal

from middlewared.service_exception import CallError
from middlewared.utils.libvirt.utils import ACTIVE_STATES
from middlewared.utils.service.call_mixin import CallMixin

if TYPE_CHECKING:
    from middlewared.main import Middleware
    from middlewared.plugins.container import ContainerService
    from middlewared.plugins.vm import VMService

Verb = Literal["START", "STOP", "RELOAD", "RESTART"]


async def is_active_node(middleware: Middleware) -> bool:
    if await middleware.call("failover.in_progress"):
        return False
    is_master: bool = await middleware.call("failover.is_single_master_node")
    return is_master


class LicenseDelegate(CallMixin):
    """
    Converges one license feature's runtime state after the license changes.

    `apply(changes)` receives `{feature: entitled}` for the delegate's features that changed, and only
    those. It returns, or raises one `CallError` naming what failed; it never logs and never changes the
    peer, which applies its own diff. A plugin method called from `apply()` runs with its own options and
    may swallow a failure, so the delegate re-checks the resulting state and raises itself. Whether a
    feature is allowed is the plugin's gate, never the delegate's.
    """

    features: ClassVar[tuple[str, ...]] = ()
    active_only: ClassVar[bool] = True
    by_feature: ClassVar[dict[str, type[LicenseDelegate]]] = {}

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        for feature in cls.__dict__.get("features", ()):
            if feature in LicenseDelegate.by_feature:
                raise ValueError(f"{feature} already has a license delegate")
            LicenseDelegate.by_feature[feature] = cls

    def __init__(self, middleware: Middleware) -> None:
        self.middleware = middleware

    @property
    def name(self) -> str:
        return ", ".join(self.features)

    async def apply(self, changes: dict[str, bool]) -> None:
        raise NotImplementedError

    async def revoke_pending(self) -> str | None:
        return None

    async def is_active(self) -> bool:
        return await is_active_node(self.middleware)

    async def render(self, *groups: str) -> None:
        for group in groups:
            await self.middleware.call("etc.generate", group)

    async def control(
        self,
        service: str,
        verb: Verb,
        *,
        timeout: int = 120,
        standby_ok: bool = False,
        running: bool | None = None,
    ) -> None:
        """
        RESTART only a running service (it would start a stopped one); RELOAD always (a stopped service's
        config is regenerated and that is not a failure); START/STOP only on the active node unless
        `standby_ok`. `running` overrides the `service.started` read for units whose activating state must
        count. Never forwarded to the peer; a `False` result from a running service is a failure.
        """
        started = await self.call2(self.s.service.started, service) if running is None else running
        if verb == "RESTART" and not started:
            return
        if verb in ("START", "STOP") and not standby_ok and not await self.is_active():
            return
        job = await self.middleware.call(
            "service.control", verb, service, {"silent": False, "ha_propagate": False, "timeout": timeout}
        )
        if not await job.wait(raise_error=True) and (started or verb == "START"):
            raise CallError(f"{service}: {verb} did not leave the service in the expected state")


class ConvergeDelegate(LicenseDelegate):
    """A template reads the entitlement live; reloading or restarting each declared service regenerates it."""

    services: ClassVar[tuple[tuple[str, Literal["RELOAD", "RESTART"]], ...]] = ()
    active_only = False

    async def apply(self, changes: dict[str, bool]) -> None:
        for service, verb in self.services:
            await self.control(service, verb)


class WorkloadDelegate[S: (VMService, ContainerService)](LicenseDelegate):
    """libvirt instances with autostart, managed through the plugin's `service`."""

    namespace: ClassVar[str]

    @property
    def service(self) -> S:
        raise NotImplementedError

    async def start(self, id_: int) -> None:
        raise NotImplementedError

    async def apply(self, changes: dict[str, bool]) -> None:
        if changes[self.features[0]]:
            await self._start_autostart()
        else:
            await self.call2(self.service.stop_active)

    async def _start_autostart(self) -> None:
        stopped = await self.call2(self.service.query, [["autostart", "=", True], ["status.state", "=", "STOPPED"]])
        failures = []
        for inst in stopped:
            if not await self.is_active():
                break
            try:
                await self.start(inst.id)
            except Exception as e:
                # The start path can raise after the instance is up; only an instance left STOPPED failed.
                current = await self.call2(self.service.get_instance, inst.id)
                if current.status.state == "STOPPED":
                    failures.append(f"{inst.name}: {e}")
        if failures:
            raise CallError(f"{self.namespace}s not started: " + "; ".join(failures))

    async def revoke_pending(self) -> str | None:
        active = await self.call2(self.service.query, [["status.state", "in", ACTIVE_STATES]])
        return f"{len(active)} {self.namespace}(s) still active" if active else None
