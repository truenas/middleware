import asyncio

from middlewared.utils import run

from .base import SimpleService


class ISCSITargetService(SimpleService):
    name = "iscsitarget"
    reloadable = True
    systemd_async_start = True

    etc = ["scst", "scst_targets"]

    systemd_unit = "scst"

    async def _wait_to_avoid_states(self, states, retries=10):
        initial_retries = retries
        while retries > 0:
            curstate = await self.middleware.call("service.get_unit_state", self.name)
            if curstate not in states:
                break
            retries -= 1
            await asyncio.sleep(1)
        if retries != initial_retries:
            if curstate in states:
                self.middleware.logger.debug(f'Waited unsucessfully for {self.name} to enter {curstate} state')
            else:
                self.middleware.logger.debug(f'Waited sucessfully for {self.name} to enter {curstate} state')

    async def before_start(self):
        await self.middleware.call("iscsi.alua.before_start")
        # Because we are a systemd_async_start service, it is possible that
        # a start could be requested while a stop is still in progress.
        if await self.middleware.call("failover.in_progress"):
            await self._wait_to_avoid_states(['deactivating'], 5)
        else:
            await self._wait_to_avoid_states(['deactivating'])

    async def after_start(self):
        await self.middleware.call("iscsi.host.injection.start")
        await self.middleware.call("iscsi.alua.after_start")

    async def before_stop(self):
        await self.middleware.call("iscsi.alua.before_stop")
        await self.middleware.call("iscsi.host.injection.stop")

    async def reload(self):
        return (await run(
            ["scstadmin", "-noprompt", "-force", "-config", "/etc/scst.conf"], check=False
        )).returncode == 0

    async def failover(self):
        if await self.middleware.call('iscsi.global.alua_enabled'):
            if await self.middleware.call('iscsi.scst.is_kernel_module_loaded'):
                if await self.middleware.call("failover.status") == "MASTER":
                    try:
                        return await self.middleware.call("iscsi.alua.failover_to_master")
                    except Exception as e:
                        self.logger.warning('Failover exception: %r', e, exc_info=True)
                        # Fall through
        # Fallback to doing a regular restart
        return await self.middleware.call('service.restart', self.name, {'ha_propagate': False})
