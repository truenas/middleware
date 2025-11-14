import asyncio

from middlewared.api import api_method, Event
from middlewared.api.current import (
    SystemBootIdArgs,
    SystemBootIdResult,
    SystemReadyArgs,
    SystemReadyResult,
    SystemRebootArgs,
    SystemRebootResult,
    SystemShutdownArgs,
    SystemShutdownResult,
    SystemStateArgs,
    SystemStateResult,
    SystemReadyAddedEvent,
    SystemRebootAddedEvent,
    SystemShutdownAddedEvent,
)
from middlewared.service import job, private, Service
from middlewared.utils import run
from .utils import lifecycle_conf, RE_KDUMP_CONFIGURED


class SystemService(Service):

    class Config:
        events = [
            Event(
                name='system.ready',
                description='Finished boot process',
                roles=['SYSTEM_GENERAL_READ'],
                models={
                    'ADDED': SystemReadyAddedEvent,
                },
            ),
            Event(
                name='system.reboot',
                description='Started reboot process',
                roles=['SYSTEM_GENERAL_READ'],
                models={
                    'ADDED': SystemRebootAddedEvent,
                },
            ),
            Event(
                name='system.shutdown',
                description='Started shutdown process',
                roles=['SYSTEM_GENERAL_READ'],
                models={
                    'ADDED': SystemShutdownAddedEvent,
                },
            ),
        ]

    @private
    async def first_boot(self):
        return lifecycle_conf.SYSTEM_FIRST_BOOT

    @private
    async def boot_env_first_boot(self):
        # First boot after upgrading server
        return lifecycle_conf.SYSTEM_BOOT_ENV_FIRST_BOOT

    @api_method(
        SystemBootIdArgs,
        SystemBootIdResult,
        authentication_required=False,
        pass_app=True,
    )
    async def boot_id(self, app):
        """
        Returns a unique boot identifier.

        It is supposed to be unique every system boot.
        """
        # NOTE: this is used, at time of writing, by the UI
        # team to handle caching of web page assets. This
        # doesn't require authentication since our login page
        # also has information that is cached. Security team
        # is aware and the risk is minimal
        return lifecycle_conf.SYSTEM_BOOT_ID

    @api_method(
        SystemReadyArgs,
        SystemReadyResult,
        roles=["SYSTEM_GENERAL_READ"]
    )
    async def ready(self):
        """
        Returns whether the system completed boot and is ready to use
        """
        return await self.middleware.call("system.state") != "BOOTING"

    @api_method(
        SystemStateArgs,
        SystemStateResult,
        roles=["SYSTEM_GENERAL_READ"]
    )
    async def state(self):
        """
        Returns system state:
        "BOOTING" - System is booting
        "READY" - System completed boot and is ready to use
        "SHUTTING_DOWN" - System is shutting down
        """
        if lifecycle_conf.SYSTEM_SHUTTING_DOWN:
            return "SHUTTING_DOWN"
        if lifecycle_conf.SYSTEM_READY:
            return "READY"
        return "BOOTING"

    @api_method(
        SystemRebootArgs,
        SystemRebootResult,
        pass_app=True,
        roles=["FULL_ADMIN"],
    )
    @job()
    async def reboot(self, app, job, reason, options):
        """
        Reboots the operating system.

        Emits an "added" event of name "system" and id "reboot".
        """
        await self.middleware.log_audit_message(app, "REBOOT", {"reason": reason}, True)

        self.middleware.send_event("system.reboot", "ADDED", fields={"reason": reason})

        if options["delay"] is not None:
            await asyncio.sleep(options["delay"])

        await run(["/sbin/shutdown", "-r", "now"])

    @api_method(
        SystemShutdownArgs,
        SystemShutdownResult,
        pass_app=True,
        roles=["FULL_ADMIN"],
    )
    @job()
    async def shutdown(self, app, job, reason, options):
        """
        Shuts down the operating system.

        An "added" event of name "system" and id "shutdown" is emitted when shutdown is initiated.
        """
        await self.middleware.log_audit_message(
            app, "SHUTDOWN", {"reason": reason}, True
        )

        self.middleware.send_event(
            "system.shutdown", "ADDED", fields={"reason": reason}
        )

        if options["delay"] is not None:
            await asyncio.sleep(options["delay"])

        await run(["/sbin/poweroff"])


async def _event_system_ready(middleware, event_type, args):
    lifecycle_conf.SYSTEM_READY = True

    if (await middleware.call("system.advanced.config"))["kdump_enabled"]:
        cp = await run(["kdump-config", "status"], check=False)
        if cp.returncode:
            middleware.logger.error(
                "Failed to retrieve kdump-config status: %s", cp.stderr.decode()
            )
        else:
            if not RE_KDUMP_CONFIGURED.findall(cp.stdout.decode()):
                await middleware.call("alert.oneshot_create", "KdumpNotReady", None)
            else:
                await middleware.call("alert.oneshot_delete", "KdumpNotReady", None)
    else:
        await middleware.call("alert.oneshot_delete", "KdumpNotReady", None)

    if await middleware.call("system.first_boot"):
        middleware.create_task(middleware.call("usage.firstboot"))


async def _event_system_shutdown(middleware, event_type, args):
    lifecycle_conf.SYSTEM_SHUTTING_DOWN = True


async def setup(middleware):
    middleware.event_subscribe("system.ready", _event_system_ready)
    middleware.event_subscribe("system.shutdown", _event_system_shutdown)
