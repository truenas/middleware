from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
import errno
from typing import Literal

from middlewared.api.current import ServiceOptions
from middlewared.service import CallError, ServiceContext

__all__ = ["ControlServiceAction", "EtcGenerateAction", "HaSynchronizationActions", "ha_synchronization"]


class HaSynchronizationBaseAction:
    def describe(self) -> str:
        raise NotImplementedError()

    async def perform(self, context: ServiceContext) -> None:
        raise NotImplementedError()

    async def perform_backup(self, context: ServiceContext) -> None:
        raise NotImplementedError()


class ControlServiceAction(HaSynchronizationBaseAction):
    def __init__(self, verb: Literal["RESTART", "RELOAD"], service: str):
        self.verb = verb
        self.service = service

    def describe(self) -> str:
        return f"{self.verb.title()} {self.service} service"

    async def perform(self, context: ServiceContext) -> None:
        await (await context.call2(
            context.s.service.control,
            self.verb,
            self.service,
            ServiceOptions(ha_propagate=False),
        )).wait(raise_error=True)

    async def perform_backup(self, context: ServiceContext) -> None:
        await context.middleware.call(
            "failover.call_remote",
            "core.bulk",
            ["service.control", [[self.verb, self.service]]],
        )


class EtcGenerateAction(HaSynchronizationBaseAction):
    def __init__(self, name: str) -> None:
        self.name = name

    def describe(self) -> str:
        return f"Generate {self.name} configuration"

    async def perform(self, context: ServiceContext) -> None:
        await context.middleware.call("etc.generate", self.name)

    async def perform_backup(self, context: ServiceContext) -> None:
        await context.middleware.call("failover.call_remote", "etc.generate", [self.name])


class HaSynchronizationActions:
    def __init__(self, context: ServiceContext, actions: list[HaSynchronizationBaseAction]):
        self.context = context
        self.actions = actions

    async def perform(self, perform_on_backup: bool) -> list[str]:
        for action in self.actions:
            await action.perform(self.context)

        failed_backup_actions = []
        if perform_on_backup:
            for action in self.actions:
                try:
                    await action.perform_backup(self.context)
                except Exception as e:
                    action_description = action.describe()
                    failed_backup_actions.append(f"{action_description} ({e!r})")
                    self.context.logger.warning(f"Failed to {action_description} on standby controller", exc_info=True)

        return failed_backup_actions


@asynccontextmanager
async def ha_synchronization(actions: HaSynchronizationActions, force: bool) -> AsyncGenerator[None]:
    context = actions.context
    strict = not force

    status = await context.middleware.call("failover.status")
    if strict:
        if status not in ("SINGLE", "MASTER"):
            if status == "BACKUP":
                raise CallError("Security settings can only be changed on active HA controller.", errno.ENOLINK)
            else:
                raise CallError(
                    f"Changing security settings requires HA to be healthy. Current status is {status}.",
                    errno.ENOLINK,
                )

        if status == "MASTER":
            try:
                rem_status = await context.middleware.call(
                    "failover.call_remote", "failover.status", [],
                    {"raise_connect_error": False, "timeout": 2, "connect_timeout": 2},
                )
                if rem_status != "BACKUP":
                    raise CallError(
                        f"Changing security settings requires HA to be healthy. Standby node reported {rem_status} "
                        "status.",
                        errno.ENOLINK,
                    )
            except Exception as e:
                raise CallError(
                    "Changing security settings requires HA to be healthy. An error occurred while contacting the remote "
                    f"node: {e!r}.",
                    errno.ENOLINK,
                )

    yield

    failed_backup_actions = await actions.perform(status == "MASTER")

    if strict:
        if await context.middleware.call("failover.datastore.is_failure"):
            failed_backup_actions = ["Replicate configuration database"] + failed_backup_actions

        if failed_backup_actions:
            raise CallError(
                "Security settings were successfully changed on active HA controller, but were not replicated to "
                "standby controller. The following actions failed:\n\n" + "\n".join([
                    f"* {action}" for action in failed_backup_actions
                ]),
            )
