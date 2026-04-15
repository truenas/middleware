import asyncio

from middlewared.utils import run
from middlewared.utils.lio.config import ISCSI_DIR, teardown_lio_config

from .base import SwitchableSimpleService
from .base_state import ServiceState


class ISCSITargetService(SwitchableSimpleService):
    name = "iscsitarget"
    reloadable = True
    systemd_async_start = True

    etc = ["scst", "scst_targets"]

    systemd_unit = "scst"

    async def _lio_mode(self):
        return await self.middleware.call('iscsi.global.lio_enabled')

    async def select_systemd_unit_name(self):
        if await self._lio_mode():
            return None
        return self.systemd_unit

    async def get_state_no_unit(self):
        return ServiceState(ISCSI_DIR.exists(), [])

    async def select_etc(self):
        if await self._lio_mode():
            return ['lio']
        return self.etc

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
        if not await self._lio_mode():
            # Because we are a systemd_async_start service, it is possible that
            # a start could be requested while a stop is still in progress.
            if await self.middleware.call("failover.in_progress"):
                await self._wait_to_avoid_states(['deactivating'], 5)
            else:
                await self._wait_to_avoid_states(['deactivating'])
        await self.middleware.call("iscsi.iser.before_start")

    async def start(self):
        if await self._lio_mode():
            # In LIO mode there is no systemd unit to start (select_systemd_unit_name
            # returns None) and config is written by etc.generate('lio') before this
            # method is called.  Nothing further to do here.
            return
        if await self.middleware.call("failover.status") not in ["MASTER", "SINGLE"]:
            if not await self.middleware.call("iscsi.global.alua_enabled"):
                # Do not start SCST on STANDBY node unless ALUA is enabled.
                return
        await super().start()

    async def stop(self):
        if await self._lio_mode():
            # In LIO mode there is no systemd unit; tear down the configfs tree
            # directly and return without invoking the SCST stop path.
            await self.middleware.run_in_thread(teardown_lio_config)
            return
        await super().stop()

    async def after_start(self):
        await self.middleware.call("iscsi.alua.after_start")

    async def before_stop(self):
        await self.middleware.call("iscsi.alua.before_stop")

    async def after_stop(self):
        await self.middleware.call("iscsi.alua.after_stop")

    async def reload(self):
        if await self._lio_mode():
            # In LIO mode reloads are handled by etc.generate('lio') which rewrites
            # the configfs tree directly.  No scstadmin reload is needed.
            return True
        if await self.middleware.call("iscsi.global.direct_config_enabled"):
            return await self.middleware.call("iscsi.scst.apply_config_file")
        else:
            return (await run(
                ["scstadmin", "-noprompt", "-force", "-config", "/etc/scst.conf"], check=False
            )).returncode == 0

    async def become_active(self):
        """If we are becoming the ACTIVE node on a HA system, and if SCST was already loaded
        then we can perform a shortcut operation to switch from being the STANDBY node to the
        ACTIVE one, *without* restarting SCST, but just by reconfiguring it."""
        if not await self._lio_mode():
            if await self.middleware.call('iscsi.global.alua_enabled'):
                if await self.middleware.call('iscsi.scst.is_kernel_module_loaded'):
                    try:
                        return await self.middleware.call("iscsi.alua.become_active")
                    except Exception:
                        self.logger.warning('Failover exception', exc_info=True)
                        # Fall through
        # Fallback to doing a regular restart
        rjob = await self.middleware.call(
            'service.control',
            'RESTART',
            self.name,
            {'ha_propagate': False}
        )
        await rjob.wait(raise_error=True)
