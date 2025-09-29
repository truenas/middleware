import asyncio
import itertools

from middlewared.plugins.fc.utils import wwn_as_colon_hex
from middlewared.service import CallError, Service, job
from middlewared.service_exception import MatchNotFound
from middlewared.utils import run

CHUNK_SIZE = 20
RETRY_SECONDS = 5
SLOW_RETRY_SECONDS = 30
HA_TARGET_SETTLE_SECONDS = 10
GET_UNIT_STATE_SECONDS = 2
RELOAD_REMOTE_QUICK_RETRIES = 10
STANDBY_ENABLE_DEVICES_RETRIES = 10
REMOTE_RELOAD_LONG_DELAY_SECS = 300


def chunker(it, size):
    iterator = iter(it)
    while chunk := list(itertools.islice(iterator, size)):
        yield chunk


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

    # See HA_PROPAGATE in event.py.  Only required when running command
    # on MASTER, and don't want it to propagate.
    HA_PROPAGATE = {'ha_propagate': False}

    def __init__(self, middleware):
        super().__init__(middleware)
        self.enabled = set()
        self.standby_starting = False
        self.standby_alua_ready = False

        self.active_elected_job = None
        self.activate_extents_job = None

        # standby_write_empty_config will be used to control whether the
        # STANDBY node initially writes a minimal scst.conf
        # We initialize it to None here, as we could just be restarting
        # middleware, then in the getter it will query the state of
        # the iscsitarget to decide what the initial value should be
        self._standby_write_empty_config = None

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
        self.standby_starting = False

    async def standby_enable_devices(self, devices):
        await self.middleware.call('iscsi.target.login_ha_targets')
        extents = await self.middleware.call('iscsi.extent.logged_in_extents')
        asked = set(devices)
        if extents and devices and asked.issubset(set(extents)):
            tochange = [extents[name] for name in devices]
            await self.middleware.call('iscsi.scst.set_devices_cluster_mode', tochange, 1)
            # We could expose the targets as we go along, but will just wait until the end.
            # await (await self.middleware.call('service.control', 'RELOAD', 'iscsitarget')).wait(raise_error=True)
            return True
        else:
            return False

    async def standby_write_empty_config(self, value=None):
        if value is not None:
            self._standby_write_empty_config = value
        if self._standby_write_empty_config is None:
            if await self.middleware.call('service.get_unit_state', 'iscsitarget') == 'active':
                self._standby_write_empty_config = False
            else:
                self._standby_write_empty_config = True
        return self._standby_write_empty_config

    @job(lock='active_elected', transient=True, lock_queue_size=1)
    async def active_elected(self, job):
        self.active_elected_job = job
        self.standby_starting = False
        job.set_progress(0, 'Start ACTIVE node ALUA reset on election')
        self.logger.debug('Start ACTIVE node ALUA reset on election')
        if await self.middleware.call('iscsi.global.alua_enabled'):
            # Just do the bare minimum here.  This API will only be called
            # on the new MASTER.
            try:
                await self.middleware.call('dlm.eject_peer')
            except Exception:
                self.logger.warning('Unexpected failure while dlm.eject_peer', exc_info=True)
            job.set_progress(100, 'ACTIVE node ALUA reset completed')
            self.logger.debug('ACTIVE node ALUA reset completed')
            return
        job.set_progress(100, 'ACTIVE node ALUA reset NOOP')
        self.logger.debug('ACTIVE node ALUA reset NOOP')

    @job(lock='activate_extents', transient=True, lock_queue_size=1)
    async def activate_extents(self, job):
        self.activate_extents_job = job
        job.set_progress(0, 'Start activate_extents')

        if self.active_elected_job:
            self.logger.debug('Waiting for active_elected to complete')
            await self.active_elected_job.wait()
            self.logger.debug('Waited for active_elected to complete')
            self.active_elected_job = None

        job.set_progress(10, 'Previous job completed')

        # First get all the currently active extents
        extents = await self.middleware.call('iscsi.extent.query',
                                             [['enabled', '=', True], ['locked', '=', False]],
                                             {'select': ['name', 'id', 'type', 'path', 'disk']})

        # Calculate what we want to do
        todo = []
        for extent in extents:
            if extent['type'] == 'DISK':
                path = f'/dev/{extent["disk"]}'
            else:
                path = extent['path']
            todo.append([extent['name'], extent['type'], path])

        job.set_progress(20, 'Read to activate')

        if todo:
            self.logger.debug(f'Activating {len(todo)} extents')
            retries = 10
            while todo and retries:
                do_again = []
                for item in todo:
                    # Mark them active
                    if not await self.middleware.call('iscsi.scst.activate_extent', *item):
                        self.logger.debug(f'Cannot Activate extent {item}')
                        do_again.append(item)
                if not do_again:
                    break
                await asyncio.sleep(1)
                retries -= 1
                todo = do_again
            self.logger.debug('Activated extents')
            await asyncio.sleep(2)
        else:
            self.logger.debug('No extent to activate')

        job.set_progress(100, 'All extents activated')

    async def become_active(self):
        self.logger.debug('Becoming active upon failover event starting')
        iqn_basename = (await self.middleware.call('iscsi.global.config'))['basename']
        thisnode = await self.middleware.call('failover.node')

        # extents: dict[id] : {id, name, type}
        extents = {ext['id']: ext for ext in await self.middleware.call('iscsi.extent.query',
                                                                        [['enabled', '=', True], ['locked', '=', False]],
                                                                        {'select': ['name', 'id', 'type']})}

        # targets: dict[id]: {'name': name, 'mode': mode}
        targets = {t['id']: t for t in await self.middleware.call('iscsi.target.query',
                                                                  [],
                                                                  {'select': ['id', 'name', 'mode']})}

        # fcports: dict[id]: wwpn
        key = 'wwpn_b' if thisnode == 'B' else 'wwpn'
        fcports = {t['target']['id']: t[key] for t in await self.middleware.call('fcport.query')}

        assocs = await self.middleware.call('iscsi.targetextent.query')

        if self.activate_extents_job:
            self.logger.debug('Waiting for activate to complete')
            await self.activate_extents_job.wait()
            self.logger.debug('Waited for activate to complete')
            self.activate_extents_job = None

        # If we have NOT completed standby_after_start then we cannot just
        # become ready, instead we will need to restart iscsitarget
        if not self.standby_alua_ready:
            self.logger.debug('STANDBY node was not yet ready, skip become_active shortcut')
            await (await self.middleware.call('service.control', 'RESTART', 'iscsitarget')).wait(raise_error=True)
            self.logger.debug('iscsitarget restarted')
            return

        self.logger.debug('Updating LUNs')
        await self.middleware.call('iscsi.scst.suspend', 10)
        self.logger.debug('iSCSI suspended')
        for assoc in assocs:
            extent_id = assoc['extent']
            if extent_id in extents:
                target_id = assoc['target']
                if target_id in targets:
                    target_name = targets[target_id]['name']
                    target_mode = targets[target_id]['mode']
                    if target_mode in ['ISCSI', 'BOTH']:
                        iqn = f'{iqn_basename}:{target_name}'
                        await self.middleware.call('iscsi.scst.replace_iscsi_lun',
                                                   iqn,
                                                   extents[extent_id]['name'],
                                                   assoc['lunid'])
                    if target_mode in ['FC', 'BOTH'] and target_id in fcports:
                        if wwpn := wwn_as_colon_hex(fcports[target_id]):
                            await self.middleware.call('iscsi.scst.replace_fc_lun',
                                                       wwpn,
                                                       extents[extent_id]['name'],
                                                       assoc['lunid'])
        self.logger.debug('Updated LUNs')
        await self.middleware.call('iscsi.scst.set_node_optimized', thisnode)
        self.logger.debug('Switched optimized node')
        if await self.middleware.call('iscsi.scst.clear_suspend'):
            self.logger.debug('iSCSI unsuspended')

    @job(lock='standby_after_start', transient=True, lock_queue_size=1)
    async def standby_after_start(self, job):
        job.set_progress(0, 'ALUA starting on STANDBY')
        self.logger.debug('ALUA starting on STANDBY')
        self.standby_starting = True
        self.standby_alua_ready = False
        self.enabled = set()

        local_requires_reload = False
        remote_requires_reload = False

        # We are the STANDBY node.  Tell the ACTIVE it can logout any HA targets it had left over.
        prefix = await self.middleware.call('iscsi.target.ha_iqn_prefix')
        while self.standby_starting:
            try:
                iqns = (await self.middleware.call('failover.call_remote', 'iscsi.target.logged_in_iqns')).keys()
                ha_iqns = list(filter(lambda iqn: iqn.startswith(prefix), iqns))
                if not ha_iqns:
                    break
                await self.middleware.call('failover.call_remote', 'iscsi.target.logout_ha_targets')
                # If we have logged out targets on the ACTIVE node, then we will want to regenerate
                # the scst.conf (to remove any left-over dev_disk)
                remote_requires_reload = True
                await asyncio.sleep(1)
            except Exception:
                await asyncio.sleep(RETRY_SECONDS)
        if not self.standby_starting:
            job.set_progress(20, 'Abandoned job.')
            return
        else:
            job.set_progress(20, 'Logged out HA targets (remote node)')
            self.logger.debug('Logged out HA targets (remote node)')

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
            self.logger.debug('Remote iscsitarget is active')

        # Next turn off cluster_mode for all the extents.
        # this will avoid "ignore dlm msg because seq mismatch" errors when we reconnect
        # Rather than try to execute in parallel, we will take our time
        cr_opts = {'timeout': 10, 'connect_timeout': 10}
        logged_enomethod = False
        while self.standby_starting:
            try:
                try:
                    devices = await self.middleware.call('failover.call_remote', 'iscsi.scst.cluster_mode_devices_set', [], cr_opts)
                except CallError as e:
                    if e.errno != CallError.ENOMETHOD:
                        raise
                    # We have not yet upgraded the other node
                    if not logged_enomethod:
                        self.logger.debug('Awaiting the ACTIVE node being upgraded.')
                        logged_enomethod = True
                    await asyncio.sleep(SLOW_RETRY_SECONDS)
                    continue
                # We did manage to call cluster_mode_devices_set
                if not devices:
                    break
                for device in devices:
                    await self.middleware.call('failover.call_remote', 'iscsi.scst.set_device_cluster_mode', [device, 0], cr_opts)
            except Exception:
                # This is a fail-safe exception catch.  Should never occur.
                self.logger.warning('Unexpected failure while cleaning up ACTIVE cluster_mode', exc_info=True)
                await asyncio.sleep(RETRY_SECONDS)
        if not self.standby_starting:
            job.set_progress(24, 'Abandoned job.')
            return
        else:
            job.set_progress(24, 'Cleared cluster_mode on ACTIVE node')
            self.logger.debug('Cleared cluster_mode on ACTIVE node')

        # Reload on ACTIVE node.  This will ensure the HA targets are available
        if self.standby_starting:
            try:
                await self.middleware.call(
                    'failover.call_remote', 'service.control', ['RELOAD', 'iscsitarget', self.HA_PROPAGATE],
                    {'job': True},
                )
            except Exception:
                self.logger.warning('Failed to reload ACTIVE iscsitarget', exc_info=True)

        # Next login the HA targets.
        reload_remote_quick_retries = RELOAD_REMOTE_QUICK_RETRIES
        while self.standby_starting:
            try:
                while self.standby_starting:
                    try:
                        # Logout any targets that have no associated LUN (may have been BUSY during login)
                        await self.middleware.call('iscsi.target.logout_empty_ha_targets')
                        # Login any missing targets
                        before_iqns = await self.middleware.call('iscsi.target.logged_in_iqns')
                        await self.middleware.call('iscsi.target.login_ha_targets')
                        after_iqns = await self.middleware.call('iscsi.target.logged_in_iqns')
                        if before_iqns != after_iqns:
                            await asyncio.sleep(HA_TARGET_SETTLE_SECONDS)
                        active_iqns = await self.middleware.call('iscsi.target.active_ha_iqns')
                        after_iqns_set = set(after_iqns.keys())
                        active_iqns_set = set(active_iqns.values())
                        if active_iqns_set.issubset(after_iqns_set):
                            break
                        job.set_progress(23, f'Detected {len(active_iqns_set - after_iqns_set)} missing HA targets')
                        if reload_remote_quick_retries > 0:
                            await self.middleware.call(
                                'failover.call_remote',
                                'service.control',
                                ['RELOAD', 'iscsitarget', self.HA_PROPAGATE],
                                {'job': True},
                            )
                            reload_remote_quick_retries -= 1
                            await asyncio.sleep(HA_TARGET_SETTLE_SECONDS)
                        else:
                            await self.middleware.call(
                                'failover.call_remote',
                                'service.control',
                                ['RELOAD', 'iscsitarget', self.HA_PROPAGATE],
                                {'job': True},
                            )
                            await asyncio.sleep(REMOTE_RELOAD_LONG_DELAY_SECS)
                    except Exception:
                        if reload_remote_quick_retries > 0:
                            await self.middleware.call(
                                'failover.call_remote',
                                'service.control',
                                ['RELOAD', 'iscsitarget', self.HA_PROPAGATE],
                                {'job': True},
                            )
                            reload_remote_quick_retries -= 1
                        await asyncio.sleep(RETRY_SECONDS)
                if not self.standby_starting:
                    job.set_progress(25, 'Abandoned job.')
                    return
                else:
                    job.set_progress(25, 'Logged in HA targets')
                    self.logger.debug('Logged in HA targets')

                # Now that we've logged in the HA targets, regenerate the config so that the
                # dev_disk DEVICEs are present (we cleared _standby_write_empty_config above).
                # We will need these, so that then we can switch them to cluster_mode
                await (await self.middleware.call('service.control', 'RELOAD', 'iscsitarget')).wait(raise_error=True)
                job.set_progress(30, 'Non cluster_mode config written')

                # Sanity check that all the targets surfaced up thru SCST okay.
                devices = list(itertools.chain.from_iterable([x for x in after_iqns.values() if x is not None]))
                if await self.middleware.call('iscsi.scst.check_cluster_mode_paths_present', devices):
                    self.logger.debug(f'cluster_mode surfaced for {devices}')
                    break

                self.logger.debug('Detected missing cluster_mode.  Retrying.')
                self._standby_write_empty_config = False
                await self.middleware.call('iscsi.target.logout_ha_targets')
                await (await self.middleware.call('service.control', 'RELOAD', 'iscsitarget')).wait(raise_error=True)
                job.set_progress(20, 'Logged out HA targets (local node)')
            except Exception:
                self.logger.warning('Failed to login and surface HA targets', exc_info=True)

        # Now that the ground is cleared, start enabling cluster_mode on extents
        while self.standby_starting:
            try:
                # We'll refetch the extents each time round the loop in case more have been added
                extents = set((await self.middleware.call('iscsi.extent.logged_in_extents')).keys())

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
                    enable_retries = STANDBY_ENABLE_DEVICES_RETRIES
                    while not ok and enable_retries:
                        ok = await self.middleware.call('iscsi.alua.standby_enable_devices', list(to_enable))
                        if not ok:
                            await asyncio.sleep(1)
                        enable_retries -= 1
                    if not ok:
                        # This shouldn't ever occur.
                        self.logger.error('Failed to enable cluster mode on devices: %r', to_enable)
                        progress = 30 + (70 * (len(self.enabled) / len(extents)))
                        job.set_progress(progress, 'Failed to enable cluster mode on devices.  Retrying.')
                        await asyncio.sleep(SLOW_RETRY_SECONDS)
                    else:
                        local_requires_reload = True
                        # Update progress
                        self.enabled.update(to_enable)
                        progress = 30 + (70 * (len(self.enabled) / len(extents)))
                        job.set_progress(progress, f'Enabled {len(self.enabled)} extents')
                        self.logger.info('Set cluster_mode on for %r extents', len(self.enabled))
                else:
                    break
            except Exception:
                # This is a fail-safe exception catch.  Should never occur.
                self.logger.warning('standby_start job', exc_info=True)
                await asyncio.sleep(RETRY_SECONDS)

        if not self.standby_starting:
            job.set_progress(100, 'Abandoned job.')
            return

        # No point trying to write a full config until we have HA targets
        self._standby_write_empty_config = False

        if remote_requires_reload:
            try:
                if local_requires_reload:
                    await self.middleware.call(
                        'failover.call_remote', 'service.control', ['RELOAD', 'iscsitarget'], {'job': True},
                    )
                else:
                    await self.middleware.call(
                        'failover.call_remote',
                        'service.control',
                        ['RELOAD', 'iscsitarget', self.HA_PROPAGATE],
                        {'job': True},
                    )
            except Exception as e:
                self.logger.warning('Failed to reload iscsitarget: %r', e, exc_info=True)
        elif local_requires_reload:
            await (await self.middleware.call('service.control', 'RELOAD', 'iscsitarget')).wait(raise_error=True)

        job.set_progress(100, 'All targets in cluster_mode')
        self.standby_starting = False
        self.standby_alua_ready = True
        self.logger.debug('ALUA started on STANDBY')

    @job(lock='standby_delayed_reload', transient=True)
    async def standby_delayed_reload(self, job):
        await asyncio.sleep(30)
        # Verify again that we are ALUA STANDBY
        if await self.middleware.call('iscsi.global.alua_enabled'):
            if await self.middleware.call('failover.status') == 'BACKUP':
                await (
                    await self.middleware.call('service.control', 'RELOAD', 'iscsitarget', {'ha_propagate': False})
                ).wait(raise_error=True)

    @job(lock='standby_fix_cluster_mode', transient=True)
    async def standby_fix_cluster_mode(self, job, devices):
        if self._standby_write_empty_config is not False:
            self.logger.debug('Skipping standby_fix_cluster_mode')
            return
        job.set_progress(0, 'Fixing cluster_mode')
        logged_in_extents = await self.middleware.call('iscsi.extent.logged_in_extents')
        device_to_srcextent = {v: k for k, v in logged_in_extents.items()}
        pruned_devices = [device for device in devices if device in device_to_srcextent]
        need_to_reload = False
        for chunk in chunker(pruned_devices, 10):
            # First wait to ensure cluster_mode paths are present (10 x 0.2 = 2 secs)
            retries = 10
            while retries:
                present = await self.middleware.call('iscsi.scst.check_cluster_mode_paths_present', chunk)
                if present:
                    break
                await asyncio.sleep(0.2)
                retries -= 1
            if not retries:
                self.logger.warning(f'Timed out waiting for cluster_mode to surface for some of {chunk}')
            # Next ensure cluster_mode is enabled on the ACTIVE node
            try:
                rextents = [device_to_srcextent[device] for device in chunk]
                lextents = chunk
            except KeyError:
                # Things may have been logged out since we requested last checked
                logged_in_extents = await self.middleware.call('iscsi.extent.logged_in_extents')
                device_to_srcextent = {v: k for k, v in logged_in_extents.items()}
                rextents = []
                lextents = []
                for device in chunk:
                    if device in device_to_srcextent:
                        rextents.append(device_to_srcextent[device])
                        lextents.append(device)

            if rextents:
                self.logger.debug(f'Setting cluster_mode on ACTIVE node for {rextents}')
                await self.middleware.call('failover.call_remote', 'iscsi.scst.set_devices_cluster_mode', [rextents, 1])

                # Then ensure cluster_mode is enabled on the STANDBY node.  Retry if necessary.
                retries = 10
                while retries:
                    try:
                        self.logger.debug(f'Setting cluster_mode on STANDBY node for {lextents}')
                        await self.middleware.call('iscsi.scst.set_devices_cluster_mode', lextents, 1)
                        break
                    except Exception:
                        self.logger.warning(f'Failed to set cluster_mode on STANDBY node for {lextents}', exc_info=True)
                    retries -= 1
                    await asyncio.sleep(1)
                need_to_reload = True
        if need_to_reload:
            job.set_progress(90, 'Fixed cluster_mode')
            await asyncio.sleep(1)
            # Now that we have enabled cluster_mode, need to reload iscsitarget so that
            # it will now offer the targets to the world.
            await (await self.middleware.call('service.control', 'RELOAD', 'iscsitarget')).wait(raise_error=True)
            job.set_progress(100, 'Reloaded iscsitarget service')
            self.logger.debug(f'Fixed cluster_mode for {len(devices)} extents (reloaded)')
        else:
            job.set_progress(100, 'Fixed cluster_mode')
            self.logger.debug(f'Fixed cluster_mode for {len(devices)} extents')

    async def wait_cluster_mode(self, target_id, extent_id):
        """After we add a target/extent mapping we wish to wait for the ALUA state to settle."""
        self.logger.debug(f'Wait for extent with ID {extent_id}')
        retries = 30
        while retries:
            # Do some basic checks each time round the loop to ensure we're still valid.
            if not await self.middleware.call("iscsi.global.alua_enabled"):
                return
            if not await self.middleware.call('failover.remote_connected'):
                return
            if await self.middleware.call('service.get_unit_state', 'iscsitarget') not in ['active', 'activating']:
                return

            # We can only deal with active targets.  Otherwise we cannot login to the HA target from the STANDBY node.
            targetname = (await self.middleware.call('iscsi.target.query', [['id', '=', target_id]], {'select': ['name']}))[0]['name']
            active_targets = await self.middleware.call('iscsi.target.active_targets')
            if targetname not in active_targets:
                self.logger.debug(f'Target {targetname} is not active (in an ALUA sense)')
                return

            retries -= 1

            # The locked and enabled are already handled by active_targets check
            lextent = (await self.middleware.call('iscsi.extent.query', [['id', '=', extent_id]], {'select': ['name']}))[0]['name']

            # Check to see if the extent is available on the remote node yet
            logged_in_extents = await self.middleware.call('failover.call_remote', 'iscsi.extent.logged_in_extents')
            if lextent not in logged_in_extents:
                self.logger.debug(f'Sleep while we wait for {lextent} to get logged in')
                await asyncio.sleep(1)
                continue

            rextent = logged_in_extents[lextent]

            # Have the dev_handlers surfaced cluster_mode yet:
            # - local
            if not await self.middleware.call('iscsi.scst.check_cluster_mode_paths_present', [lextent]):
                self.logger.debug(f'Sleep while we wait for {lextent} cluster_mode to surface')
                await asyncio.sleep(1)
                continue
            # - remote
            if not await self.middleware.call('failover.call_remote', 'iscsi.scst.check_cluster_mode_paths_present', [[rextent]]):
                self.logger.debug(f'Sleep while we wait for {rextent} cluster_mode to surface')
                await asyncio.sleep(1)
                continue

            # OK, now check whether we've made it into cluster mode yet
            # - local
            if await self.middleware.call('iscsi.scst.get_cluster_mode', lextent) != "1":
                self.logger.debug(f'Sleep while we wait for {lextent} to enter cluster_mode')
                await asyncio.sleep(1)
                continue
            # - remote
            if await self.middleware.call('failover.call_remote', 'iscsi.scst.get_cluster_mode', [rextent]) != "1":
                self.logger.debug(f'Sleep while we wait for {rextent} to enter cluster_mode')
                await asyncio.sleep(1)
                continue

            # If we get here, we're good to go!
            self.logger.debug(f'Completed wait for {lextent}/{rextent} to enter cluster_mode')
            return

    async def removed_target_extent(self, target_name, lun, extent_name):
        """This is called on the STANDBY node to remove an extent from a target."""
        if await self.middleware.call("iscsi.global.alua_enabled") and await self.middleware.call("failover.status") == 'BACKUP':
            try:
                # First we will remove the LUN from the target.  We need to determine whether it
                # is ISCSI, FC, or BOTH
                global_basename = (await self.middleware.call('iscsi.global.config'))['basename']
                try:
                    filters = [['name', '=', target_name]]
                    options = {'select': ['mode', 'id'], 'get': True}
                    attrs = await self.middleware.call('iscsi.target.query', filters, options)

                    # iSCSI
                    if attrs['mode'] in ['ISCSI', 'BOTH']:
                        iqn = f'{global_basename}:{target_name}'
                        try:
                            await self.middleware.call('iscsi.scst.delete_iscsi_lun', iqn, lun)
                            self.logger.debug('Deleted iSCSI LUN %r for target: %r', lun, target_name)
                        except Exception:
                            self.logger.warning('Failed to delete iSCSI LUN %r for target: %r', lun, target_name)

                    # Fibre Channel
                    if attrs['mode'] in ['FC', 'BOTH']:
                        filters = [['target.id', '=', attrs['id']]]
                        options = {'select': ['wwpn', 'wwpn_b']}
                        fcport = await self.middleware.call('fcport.query', filters, options)
                        if fcport:
                            this_node = await self.middleware.call('failover.node')
                            if this_node == 'A':
                                wwpn = fcport[0].get('wwpn')
                            elif this_node == 'B':
                                wwpn = fcport[0].get('wwpn_b')
                            else:
                                wwpn = None
                        if wwpn:
                            wwpn = wwn_as_colon_hex(wwpn)
                            if wwpn:
                                try:
                                    await self.middleware.call('iscsi.scst.delete_fc_lun', wwpn, lun)
                                    self.logger.debug('Deleted Fibre Channel LUN %r for target: %r', lun, target_name)
                                except Exception:
                                    self.logger.warning('Failed to delete Fibre Channel LUN %r for target: %r',
                                                        lun, target_name)
                except MatchNotFound:
                    self.logger.warning('Could not retrieve mode for target: %r', target_name)

                # Next we will disable cluster_mode for the extent
                ha_iqn = f'{global_basename}:HA:{target_name}'
                device = await self.middleware.call('iscsi.extent.logged_in_extent', ha_iqn, lun)
                if device:
                    await self.middleware.call('iscsi.scst.set_devices_cluster_mode', [device], 0)

                # If we have removed a LUN from a target, it'd be nice to think that we could just do one of the following
                # - for i in /sys/class/scsi_device/*/device/rescan ; do echo 1 > $i ; done
                # - iscsiadm -m node -R
                # etc, but (currently) these don't work.  Therefore we'll use a sledgehammer
                await self.middleware.call('iscsi.target.logout_ha_target', target_name)
            finally:
                await (await self.middleware.call('service.control', 'RELOAD', 'iscsitarget')).wait(raise_error=True)

    async def added_target_extent(self, target_name):
        """This is called on the STANDBY node after an extent has been added to a target."""
        if await self.middleware.call("iscsi.global.alua_enabled") and await self.middleware.call("failover.status") == 'BACKUP':
            global_basename = (await self.middleware.call('iscsi.global.config'))['basename']
            iqn = f'{global_basename}:HA:{target_name}'
            try:
                await self.middleware.call("iscsi.target.rescan_iqn", iqn)
            except Exception:
                self.logger.debug('Failed to rescan %r', iqn)

    async def has_active_jobs(self):
        """Return whether any ALUA jobs are running or queued."""
        running_jobs = await self.middleware.call(
            'core.get_jobs', [
                ('method', 'in', [
                    'iscsi.alua.active_elected',
                    'iscsi.alua.activate_extents',
                    'iscsi.alua.standby_after_start',
                    'iscsi.alua.standby_delayed_reload',
                    'iscsi.alua.standby_fix_cluster_mode',
                ]),
                ('state', 'in', ['RUNNING', 'WAITING']),
            ]
        )
        return bool(running_jobs)

    async def settled(self):
        """Check whether the ALUA state is settled"""
        if not await self.middleware.call("iscsi.global.alua_enabled"):
            return True

        # Check local: running & no active ALUA jobs
        if (await self.middleware.call("service.get_unit_state", 'iscsitarget')) != 'active':
            return False
        if await self.middleware.call('iscsi.alua.has_active_jobs'):
            return False

        # Check remote: running & no active ALUA jobs
        try:
            if (await self.middleware.call(
                'failover.call_remote', 'service.get_unit_state', ['iscsitarget']
            )) != 'active':
                return False
            if await self.middleware.call('failover.call_remote', 'iscsi.alua.has_active_jobs'):
                return False
        except Exception:
            # If we fail to communicate with the other node, then we cannot be said to be settled.
            return False
        return True

    async def wait_for_alua_settled(self, sleep_interval=1, retries=10):
        while retries > 0:
            if await self.middleware.call('iscsi.alua.settled'):
                return
            # self.logger.debug('Waiting for ALUA settle')
            await asyncio.sleep(sleep_interval)
            retries -= 1
        self.logger.warning('Gave up waiting for ALUA to settle')

    @job(lock='force_close_sessions', transient=True, lock_queue_size=1)
    async def force_close_sessions(self, job):
        job.set_progress(0, 'Start force-close of iSCSI sessions')
        self.logger.debug('Start force-close of iSCSI sessions')

        await run('scst_util.sh', 'force-close')

        job.set_progress(100, 'Complete force-close of iSCSI sessions')
        self.logger.debug('Complete force-close of iSCSI sessions')

    @job(lock='reset_active', transient=True, lock_queue_size=1)
    async def reset_active(self, job):
        """Job to be run on the ACTIVE node before the STANDBY node will join."""
        job.set_progress(0, 'Start logout HA targets')
        self.logger.debug('Start logout HA targets')

        # This is similar, but not identical to iscsi.target.logout_ha_targets
        # The main difference is these are logged out in series, to allow e.g. cluster_mode settle
        # This is also why it is a job. it may take longer to run.
        iqns = await self.middleware.call('iscsi.target.active_ha_iqns')

        # Check what's already logged in
        existing = await self.middleware.call('iscsi.target.logged_in_iqns')

        # Generate the set of things we want to logout (don't assume every IQN, just the HA ones)
        todo = set(iqn for iqn in iqns.values() if iqn in existing)

        count = 0
        remote_ip = await self.middleware.call('failover.remote_ip')
        while todo and (iqn := todo.pop()):
            try:
                await self.middleware.call('iscsi.target.logout_iqn', remote_ip, iqn)
                count += 1
            except Exception:
                self.logger.warning('Failed to logout %r', iqn, exc_info=True)

        self.logger.debug('Logged out %d HA targets', count)
        job.set_progress(50, 'Logged out HA targets')

        await self.middleware.call('dlm.eject_peer')
        self.logger.debug('Ejected peer')
        job.set_progress(10, 'Ejected peer')
