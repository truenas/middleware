import asyncio
import itertools

from middlewared.schema import returns
from middlewared.service import Service, job

CHUNK_SIZE = 20
RETRY_SECONDS = 5
HA_TARGET_SETTLE_SECONDS = 10
GET_UNIT_STATE_SECONDS = 2


class iSCSITargetAluaService(Service):
    """
    Support iSCSI ALUA configuration.

    The ALUA mechanism is based up DLM support baked into SCST, along with other
    potions of middleware (dlm, iscsi.targets, etc ) to handle the coordination
    between the two nodes in a HA pair.  This is performed in response to
    cluster_mode being set on target extents.

    However, when a LARGE number of extents(/targets) are present it becomes
    impractical to leave/enter lockspaces on scst startup.

    To avoid this, SCST on the ACTIVE will start without cluster_mode being
    set on extents.  Likewise on the STANDBY node, so the targets there will be
    present but disabled.  However, the STANDBY will then initiate a job to
    (gradually) enable cluster_mode on the ACTIVE and react.
    """
    class Config:
        private = True
        namespace = 'iscsi.alua'

    # See HA_PROPAGATE in event.py.  Not only required when running command
    # on MASTER, and don't want it to propagate.
    HA_PROPAGATE = {'ha_propagate': False}

    def __init__(self, middleware):
        super().__init__(middleware)
        self.enabled = set()
        self.standby_starting = False

        # scst.conf.mako will check the below value to determine whether it
        # should write cluster_mode = 1, even if then value in /sys is zero
        # (i.e. extent not listed in iscsi.target.clustered_extents)
        self._all_cluster_mode = False

        # Likewise
        self._standby_write_empty_config = True

    async def before_start(self):
        if await self.middleware.call('iscsi.global.alua_enabled'):
            if await self.middleware.call('failover.status') == 'BACKUP':
                self._standby_write_empty_config = True
                await self.middleware.call('etc.generate', 'scst')

    async def after_start(self):
        if await self.middleware.call('iscsi.global.alua_enabled'):
            if await self.middleware.call('failover.status') == 'BACKUP':
                await self.middleware.call('iscsi.alua.standby_after_start')

    async def before_stop(self):
        self._all_cluster_mode = False
        self.standby_starting = False

    async def standby_enable_devices(self, devices):
        await self.middleware.call('iscsi.target.login_ha_targets')
        extents = await self.middleware.call('iscsi.extent.logged_in_extents')
        asked = set(devices)
        if extents and devices and asked.issubset(set(extents)):
            tochange = [extents[name] for name in devices]
            await self.middleware.call('iscsi.scst.set_devices_cluster_mode', tochange, 1)
            # We could expose the targets as we go along, but will just wait until the end.
            # await self.middleware.call('service.reload', 'iscsitarget')
            return True
        else:
            return False

    def all_cluster_mode(self):
        return self._all_cluster_mode

    async def standby_write_empty_config(self, value=None):
        if value is not None:
            self._standby_write_empty_config = value
        return self._standby_write_empty_config

    @returns()
    @job(lock='active_elected', transient=True, lock_queue_size=1)
    async def active_elected(self, job):
        self.standby_starting = False
        job.set_progress(0, 'Start ACTIVE node ALUA reset on election')
        self.logger.debug('Start ACTIVE node ALUA reset on election')
        if await self.middleware.call('iscsi.global.alua_enabled'):
            if await self.middleware.call('failover.status') == 'MASTER':
                await self.middleware.call('dlm.local_reset', False)
                job.set_progress(50, 'ACTIVE node ALUA local reset done')

                await self.middleware.call('iscsi.target.logout_ha_targets')
                job.set_progress(100, 'ACTIVE node ALUA reset completed')
                self.logger.debug('ACTIVE node ALUA reset completed')
                return
        job.set_progress(100, 'ACTIVE node ALUA reset NOOP')
        self.logger.debug('ACTIVE node ALUA reset NOOP')

    @returns()
    @job(lock='standby_after_start', transient=True, lock_queue_size=1)
    async def standby_after_start(self, job):
        job.set_progress(0, 'ALUA starting on STANDBY')
        self.logger.debug('ALUA starting on STANDBY')
        self.standby_starting = True
        self.enabled = set()
        self._standby_write_empty_config = False

        # First we ensure we're not joined to any lockspaces.  Zero things
        await self.middleware.call('dlm.local_reset')
        job.set_progress(5, 'Cleaned local lockspaces')

        # Next ensure the ACTIVE lockspaces are reset
        # It's OK if we wait here more or less indefinitely.
        while self.standby_starting:
            try:
                await self.middleware.call('failover.call_remote', 'dlm.local_reset', [False])
                break
            except Exception:
                await asyncio.sleep(RETRY_SECONDS)
        if not self.standby_starting:
            job.set_progress(10, 'Abandoned job.')
            return
        else:
            job.set_progress(10, 'Asked to reset remote lockspaces')

        max_retries = 120
        while self.standby_starting and max_retries:
            try:
                if len(await self.middleware.call('failover.call_remote', 'dlm.lockspaces')) == 0:
                    break
                await asyncio.sleep(1)
                max_retries -= 1
            except Exception:
                await asyncio.sleep(RETRY_SECONDS)
        if not self.standby_starting:
            job.set_progress(15, 'Abandoned job.')
            return
        else:
            job.set_progress(15, 'Reset remote lockspaces')

        # We are the STANDBY node.  Tell the ACTIVE it can logout any HA targets it had left over
        # We set a low number of retries as it doesn't really matter if these are in place.  This is
        # just tidy up.
        max_retries = 5
        while self.standby_starting and max_retries:
            try:
                max_retries -= 1
                iqns = await self.middleware.call('failover.call_remote', 'iscsi.target.logged_in_iqns')
                if not iqns:
                    break
                await self.middleware.call('failover.call_remote', 'iscsi.target.logout_ha_targets')
                await asyncio.sleep(1)
            except Exception:
                await asyncio.sleep(RETRY_SECONDS)
        if not self.standby_starting:
            job.set_progress(20, 'Abandoned job.')
            return
        else:
            job.set_progress(20, 'Logged out HA targets (remote node)')

        # We may want to ensure that the iSCSI service on the remote node is fully
        # up.  Since we have switched it systemd_async_start asking get_unit_state
        while self.standby_starting:
            try:
                state = await self.middleware.call('failover.call_remote', 'service.get_unit_state', ['iscsitarget'])
                if state == 'active':
                    break
                await asyncio.sleep(GET_UNIT_STATE_SECONDS)
            except Exception as e:
                # This is a fail-safe exception catch.  Should never occur.
                self.logger.warning('standby_start job: %r', e, exc_info=True)
                await asyncio.sleep(RETRY_SECONDS)
        if not self.standby_starting:
            job.set_progress(22, 'Abandoned job.')
            return
        else:
            job.set_progress(22, 'Remote iscsitarget is active')

        # Next login the HA targets.
        reload_remote_retries = 5
        while self.standby_starting:
            try:
                while self.standby_starting:
                    try:
                        before_iqns = await self.middleware.call('iscsi.target.logged_in_iqns')
                        await self.middleware.call('iscsi.target.login_ha_targets')
                        after_iqns = await self.middleware.call('iscsi.target.logged_in_iqns')
                        if before_iqns != after_iqns:
                            await asyncio.sleep(HA_TARGET_SETTLE_SECONDS)
                        active_targets = await self.middleware.call('iscsi.target.active_targets')
                        if len(active_targets) != len(after_iqns):
                            job.set_progress(23, 'Detected missing HA targets')
                            if reload_remote_retries > 0:
                                await self.middleware.call('failover.call_remote', 'service.reload', ['iscsitarget', self.HA_PROPAGATE])
                                reload_remote_retries -= 1
                            await asyncio.sleep(HA_TARGET_SETTLE_SECONDS)
                            continue
                        break
                    except Exception:
                        if reload_remote_retries > 0:
                            await self.middleware.call('failover.call_remote', 'service.reload', ['iscsitarget', self.HA_PROPAGATE])
                            reload_remote_retries -= 1
                        await asyncio.sleep(RETRY_SECONDS)
                if not self.standby_starting:
                    job.set_progress(25, 'Abandoned job.')
                    return
                else:
                    job.set_progress(25, 'Logged in HA targets')

                # Now that we've logged in the HA targets, regenerate the config so that the
                # dev_disk DEVICEs are present (we cleared _standby_write_empty_config above).
                # We will need these, so that then we can switch them to cluster_mode
                await self.middleware.call('service.reload', 'iscsitarget')
                job.set_progress(30, 'Non cluster_mode config written')

                # Sanity check that all the targets surfaced up thru SCST okay.
                devices = list(itertools.chain.from_iterable([x for x in after_iqns.values() if x is not None]))
                if await self.middleware.call('iscsi.scst.check_cluster_mode_paths_present', devices):
                    break

                self.logger.debug('Detected missing cluster_mode.  Retrying.')
                await self.middleware.call('iscsi.target.logout_ha_targets')
                await self.middleware.call('service.reload', 'iscsitarget')
                job.set_progress(20, 'Logged out HA targets (local node)')
            except Exception as e:
                self.logger.warning('Failed to login and surface HA targets: %r', e, exc_info=True)

        # Now that the ground is cleared, start enabling cluster_mode on extents
        local_requires_reload = False
        remote_requires_reload = False
        while self.standby_starting:
            try:
                # We'll refetch the extents each time round the loop in case more have been added
                extents = set(extent['name'] for extent in await self.middleware.call('iscsi.extent.query', [], {'select': ['name']}))

                # Choose the next batch of extents to enable.
                to_enable = set(itertools.islice(extents - self.enabled, CHUNK_SIZE))

                if to_enable:

                    # First we will ensure they are in cluster_mode on the ACTIVE
                    while self.standby_starting:
                        try:
                            remote_clustered_extents = set(await self.middleware.call('failover.call_remote', 'iscsi.target.clustered_extents'))
                            todo_remote = to_enable - remote_clustered_extents
                            if todo_remote:
                                remote_requires_reload = True
                                await self.middleware.call('failover.call_remote', 'iscsi.scst.set_devices_cluster_mode', [list(todo_remote), 1])
                            else:
                                break
                        except Exception:
                            await asyncio.sleep(RETRY_SECONDS)

                    # Enable on STANDBY.  If we fail here, we'll still go back around the main loop.
                    ok = False
                    enable_retries = 10
                    while not ok and enable_retries:
                        ok = await self.middleware.call('iscsi.alua.standby_enable_devices', list(to_enable))
                        if not ok:
                            await asyncio.sleep(1)
                        enable_retries -= 1
                    if not ok:
                        self.logger.error('Failed to enable cluster mode on devices: %r', to_enable)
                    else:
                        local_requires_reload = True

                    # Update progress
                    self.enabled.update(to_enable)
                    progress = 20 + (80 * (len(self.enabled) / len(extents)))
                    job.set_progress(progress, f'Enabled {len(self.enabled)} extents')
                    self.logger.info('Set cluster_mode on for %r extents', len(self.enabled))
                else:
                    break
            except Exception as e:
                # This is a fail-safe exception catch.  Should never occur.
                self.logger.warning('standby_start job: %r', e, exc_info=True)
                await asyncio.sleep(RETRY_SECONDS)

        if not self.standby_starting:
            job.set_progress(100, 'Abandoned job.')
            return

        if remote_requires_reload:
            try:
                if local_requires_reload:
                    await self.middleware.call('failover.call_remote', 'service.reload', ['iscsitarget'])
                else:
                    await self.middleware.call('failover.call_remote', 'service.reload', ['iscsitarget', self.HA_PROPAGATE])
            except Exception as e:
                self.logger.warning('Failed to reload iscsitarget: %r', e, exc_info=True)
        elif local_requires_reload:
            await self.middleware.call('service.reload', 'iscsitarget')

        job.set_progress(100, 'All targets in cluster_mode')
        self.standby_starting = False
        self._all_cluster_mode = True
        self.logger.debug('ALUA started on STANDBY')
