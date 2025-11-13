# Copyright (c) - iXsystems Inc. dba TrueNAS
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

import asyncio
import os
import time
import contextlib
import threading
import logging
import errno
from collections import defaultdict

from middlewared.utils import filter_list
from middlewared.service import Service, job
from middlewared.service_exception import CallError
from middlewared.plugins.docker.state_utils import Status as DockerStatus
# from middlewared.plugins.failover_.zpool_cachefile import ZPOOL_CACHE_FILE
from middlewared.plugins.failover_.event_exceptions import AllZpoolsFailedToImport, IgnoreFailoverEvent, FencedError
from middlewared.plugins.failover_.scheduled_reboot_alert import WATCHDOG_ALERT_FILE
from middlewared.plugins.virt.utils import VirtGlobalStatus as VirtStatus
from middlewared.plugins.pwenc import PWENC_FILE_SECRET

logger = logging.getLogger('failover')
FAILOVER_LOCK_NAME = 'vrrp_event'

# When we get to the point of transitioning to MASTER or BACKUP
# we wrap the associated methods (`vrrp_master` and `vrrp_backup`)
# in a job (lock) so that we can protect the failover event.
#
# This does a few things:
#
#    1. protects us if we have an interface that has a
#        rapid succession of state changes
#
#    2. if we have a near simultaneous amount of
#        events get triggered for all interfaces
#        --this can happen on external network failure
#        --this happens when one node reboots
#        --this happens when keepalived service is restarted
#
# If any of the above scenarios occur, we want to ensure
# that only one thread is trying to run fenced or import the
# zpools.


class FailoverEventsService(Service):

    class Config:
        private = True
        namespace = 'failover.events'

    # represents if a failover event was successful or not
    FAILOVER_RESULT = None

    # list of critical services that get restarted first
    # before the other services during a failover event
    CRITICAL_SERVICES = ['iscsitarget', 'cifs', 'nfs', 'nvmet']

    # list of services that use service.become_active instead of
    # service.restart during a failover on the MASTER node.
    BECOME_ACTIVE_SERVICES = ['iscsitarget', 'nvmet']

    # option to be given when changing the state of a service
    # during a failover event, we do not want to replicate
    # the state of a service to the other controller since
    # that's being handled by us explicitly
    HA_PROPAGATE = {'ha_propagate': False}

    # this is the time limit we place on exporting the
    # zpool(s) when becoming the BACKUP node
    ZPOOL_EXPORT_TIMEOUT = 4  # seconds

    async def restart_service(self, service, timeout):
        logger.info('Restarting %s', service)
        return await (await self.middleware.call('service.control', 'RESTART', service, self.HA_PROPAGATE)).wait(timeout=timeout)

    async def become_active_service(self, service, timeout):
        logger.info('Become active %s', service)
        return await asyncio.wait_for(
            self.middleware.create_task(self.middleware.call('service.become_active', service)),
            timeout=timeout,
        )

    async def restart_services(self, data):
        """
        Concurrently restart services during a failover
        master event.

        `data` is a dictionary accepting 2 keys
            `critical` Boolean when True will only restart the
            critical services.
            `timeout` Integer representing the maximum amount
            of time to wait for a given service to (re)start.
        """
        data.setdefault('critical', False)
        data.setdefault('timeout', 15)
        to_restart = await self.middleware.call('datastore.query', 'services_services')
        to_restart = [i['srv_service'] for i in to_restart if i['srv_enable']]
        if data['critical']:
            to_restart = [i for i in to_restart if i in self.CRITICAL_SERVICES]
        else:
            to_restart = [i for i in to_restart if i not in self.CRITICAL_SERVICES]

        # Certain services on TrueNAS need to have correct nameserver information.
        # We are seeing a situation where the active controller is being
        # configured while the standby is in a non-functional state. So this
        # exposes a gap in our service bring up on a master event. So we're going
        # to synchronize the DNS information written in the db to the OS.
        try:
            self.logger.debug('Synchronizing DNS')
            await self.middleware.call('dns.sync')
            self.logger.debug('Done synchronizing DNS')
        except Exception:
            self.logger.exception('Unexpected failure synchronizing DNS')

        exceptions = await asyncio.gather(
            *[
                self.become_active_service(svc, data['timeout'])
                if svc in self.BECOME_ACTIVE_SERVICES
                else self.restart_service(svc, data['timeout'])
                for svc in to_restart
            ],
            return_exceptions=True
        )
        for svc, exc in zip(to_restart, exceptions):
            if isinstance(exc, asyncio.TimeoutError):
                logger.error(
                    'Failed to restart service "%s" after %d seconds',
                    svc, data['timeout']
                )

    async def refresh_failover_status(self, jobid, event):
        # this is called in a background task so we need to make sure that
        # we wait on the current failover job to complete before we try
        # and update the failover status
        try:
            wait_id = await self.middleware.call('core.job_wait', jobid)
            await wait_id.wait(raise_error=True)
        except (CallError, KeyError):
            # `CallError` means the failover job didn't complete successfully
            # but we still want to refresh status in this scenario
            # `KeyError` shouldn't be possible but there exists a hypothetical
            # race condition...but we still want to refresh status
            pass
        except Exception:
            self.logger.error('Unhandled failover status exception', exc_info=True)
            return

        # update HA status on this controller
        await self.middleware.call('failover.status_refresh')
        if event == 'BACKUP':
            try:
                # we need to refresh status on the active node since webui subscribes
                # to failover.disabled.reasons which is responsible for showing the
                # various components on the dashboard as well as the HA status icon
                await self.middleware.call('failover.call_remote', 'failover.status_refresh')
            except Exception:
                self.logger.warning('Failed to refresh failover status on active node')

    def run_call(self, method, *args, job=False):
        try:
            result = self.middleware.call_sync(method, *args)
            if job:
                result = result.wait_sync(raise_error=True, raise_error_forward_classes=(Exception,))
            return result
        except IgnoreFailoverEvent:
            # `self.validate()` calls this method
            raise
        except Exception:
            raise

    def event(self, ifname, event):

        refresh, job = True, None
        try:
            job = self._event(ifname, event)
            return job
        except IgnoreFailoverEvent:
            refresh = False
        except Exception:
            self.logger.error('Unhandled exception processing failover event', exc_info=True)
        finally:
            # refreshing the failover status can cause delays in failover
            # there is no reason to refresh it if the event has been ignored
            if refresh and job is not None:
                self.middleware.create_task(self.refresh_failover_status(job.id, event))

    def _export_zpools(self, volumes):

        # export the zpool(s)
        try:
            for vol in volumes:
                if vol['status'] != 'OFFLINE':
                    self.middleware.call_sync('zfs.pool.export', vol['name'], {'force': True})
                    logger.info('Exported "%s"', vol['name'])
        except Exception as e:
            # catch any exception that could be raised
            # We sleep for 5 seconds here because this is
            # in its own thread. The calling thread waits
            # for self.ZPOOL_EXPORT_TIMEOUT and if this
            # thread is_alive(), then we violently reboot
            # the node
            logger.error('Error exporting "%s" with error %s', vol['name'], e)
            time.sleep(self.ZPOOL_EXPORT_TIMEOUT + 1)

    def generate_failover_data(self):

        # only care about name, guid, and status
        volumes = self.run_call(
            'pool.query', [], {
                'select': ['name', 'guid', 'status']
            }
        )

        failovercfg = self.run_call('failover.config')
        interfaces = self.run_call('interface.query')
        internal_ints = self.run_call('failover.internal_interfaces')

        data = {
            'disabled': failovercfg['disabled'],
            'master': failovercfg['master'],
            'timeout': failovercfg['timeout'],
            'groups': defaultdict(list),
            'volumes': volumes,
            'non_crit_interfaces': [
                i['id'] for i in filter_list(interfaces, [
                    ('failover_critical', '!=', True),
                ])
            ],
            'internal_interfaces': internal_ints,
        }

        for i in filter_list(interfaces, [('failover_critical', '=', True)]):
            data['groups'][i['failover_group']].append(i['id'])

        return data

    def validate(self, ifname, event):
        """
        When a failover event is generated we need to account for a few
        scenarios.

            1. if we are currently processing a failover event and then
                receive another event and the new event is a _different_
                event than the current one, we will wait for the current
                job to finish. Once that job is finished, we'll begin to
                process the next job that came in behind it. This is
                particularly important when an HA system is booted up for
                the first time (both controllers) OR if one controller is
                powered off and only one is powered on. In either of these
                scenarios, keepalived will send a BACKUP event and then 2
                seconds middlewared updates the config and reloads keepalived
                which sends another BACKUP event and then finally another 2
                seconds later, a MASTER event will be sent. In testing,
                the BACKUP event had not finished when we received the MASTER
                event so we ignored it therefore leaving the controller(s) in
                a busted state (both are BACKUP or the single controller would
                never promote itself)

            2. if we are currently processing a failover event and then
                receive another event and the new event is the _same_
                event as the current one, we log an informational message
                and raise an `IgnoreFailoverEvent` exception.
        """
        current_events = self.run_call(
            'core.get_jobs', [
                ('OR', [
                    ('method', '=', 'failover.events.vrrp_master'),
                    ('method', '=', 'failover.events.vrrp_backup')
                ]),
            ]
        )
        for i in current_events:
            cur_iface = i['arguments'][1]
            if i['state'] == 'RUNNING' and i['arguments'][2] == event:
                msg = f'Received {event!r} event for {ifname!r} but '
                msg += f'a duplicate event is currently running for {cur_iface!r}. Ignoring.'
                logger.info(msg)
                raise IgnoreFailoverEvent()

    def _event(self, ifname, event):

        # generate data to be used during the failover event
        fobj = self.generate_failover_data()

        if event != 'forcetakeover':
            if fobj['disabled'] and not fobj['master']:
                # if forcetakeover is false, and failover is disabled
                # and we're not set as the master controller, then
                # there is nothing we need to do.
                logger.warning('Failover is disabled but this node is marked as the BACKUP node. Assuming BACKUP.')
                raise IgnoreFailoverEvent()
            elif fobj['disabled']:
                raise IgnoreFailoverEvent()

            # If there is a state change on a non-critical interface then
            # ignore the event and return
            for i in fobj['non_crit_interfaces']:
                if i == ifname:
                    logger.warning('Ignoring state change on non-critical interface "%s".', ifname)
                    raise IgnoreFailoverEvent()

            needs_imported = False
            for pool in self.run_call('pool.query', [('name', 'in', [i['name'] for i in fobj['volumes']])]):
                if pool['status'] == 'OFFLINE':
                    needs_imported = True
                    break

            # means all zpools are already imported
            if fobj['volumes'] and event == 'MASTER' and not needs_imported:
                logger.warning(
                    'Received a MASTER event on %r but zpools are already imported, ignoring.',
                    ifname
                )
                raise IgnoreFailoverEvent()

        # if we get here then the last verification step that
        # we need to do is ensure there aren't any current ongoing failover events
        self.run_call('failover.events.validate', ifname, event)

        # start the MASTER failover event
        if event in ('MASTER', 'forcetakeover'):
            return self.run_call('failover.events.vrrp_master', fobj, ifname, event)

        # start the BACKUP failover event
        elif event == 'BACKUP':
            return self.run_call('failover.events.vrrp_backup', fobj, ifname, event)

    def fenced_start_loop(self, max_retries=4):
        # When active node is rebooted administratively from shell, the
        # fenced process will continue running on the node until systemd
        # finishes terminating services and actually reboots. Hence, we may
        # need to retry a few times before fenced goes away on the remote
        # node. NOTE: fenced waits for ~11 or so seconds to see if the
        # reservation keys change.
        total_time_waited = 0
        for i in range(1, max_retries + 1):
            start = time.time()
            fenced_error = self.run_call('failover.fenced.start')
            if fenced_error != 2:
                break
            else:
                total_time_waited += int(time.time() - start)
                retrying = ', retrying.' if i < max_retries else ''
                logger.warning(
                    'Fenced is running on remote node after waiting %d seconds%s',
                    total_time_waited,
                    retrying
                )

        return fenced_error

    def iscsi_cleanup_alua_state(self):
        """
        Cleanup iSCSI ALUA state if we are now becoming ACTIVE node, and
        previously were STANDBY node.
        """
        # We will suspend iSCSI and then close any existing iSCSI sessions
        # to avoid inflight I/O interfering with the LUN replacement during
        # become_active.  Suspending iSCSI means BUSY will be returned.
        suspended = cleaned = False
        try:
            try:
                logger.info('Suspending iSCSI')
                self.run_call('iscsi.scst.suspend', 30)
                suspended = True
                logger.info('Suspended iSCSI')
            except FileNotFoundError:
                # This can occur if we are booting into ACTIVE node
                # rather than becoming ACTIVE from STANDBY.
                logger.info('Did not suspend iSCSI')
            else:
                logger.info('Closing iSCSI sessions')
                self.run_call('iscsi.alua.force_close_sessions')
                logger.info('Closed iSCSI sessions')
                logger.info('calling iscsi ALUA active elected')
                self.run_call('iscsi.alua.active_elected')
                logger.info('done calling iscsi ALUA active elected')
                cleaned = True
        except Exception:
            logger.exception('Unexpected failure setting up iscsi')
        return (suspended, cleaned)

    @job(lock=FAILOVER_LOCK_NAME, read_roles=['READONLY_ADMIN'])
    def vrrp_master(self, job, fobj, ifname, event):

        # vrrp does the "election" for us. If we've gotten this far
        # then the specified timeout for NOT receiving an advertisement
        # has elapsed. Setting the progress to ELECTING is to prevent
        # extensive API breakage with the platform indepedent failover plugin
        # as well as the front-end (webUI) even though the term is misleading
        # in this use case
        job.set_progress(None, description='ELECTING')

        # Attach NVMe/RoCE - wait up to 10 seconds
        logger.info('Start bring up of NVMe/RoCE')
        try:
            # Request fenced_reload just in case the job does not complete in time
            jbof_job = self.run_call('jbof.configure_job', True)
            jbof_job.wait_sync(timeout=60)
            if jbof_job.error:
                logger.error(f'Error attaching JBOFs: {jbof_job.error}')
            elif jbof_job.result['failed']:
                logger.error(f'Failed to attach JBOFs:{jbof_job.result["message"]}')
            else:
                logger.info(jbof_job.result['message'])
        except TimeoutError:
            logger.error('Timed out attaching JBOFs.  Retrying')
            try:
                jbof_job.wait_sync(timeout=60)
            except TimeoutError:
                logger.error('Timed out attaching JBOFs.')
            else:
                logger.info('Done bring up of NVMe/RoCE')
        except Exception:
            logger.error('Unexpected error', exc_info=True)
        else:
            logger.info('Done bring up of NVMe/RoCE')

        fenced_error = None
        if event == 'forcetakeover':
            # reserve the disks forcefully ignoring if the other node has the disks
            logger.warning('Forcefully taking over as the MASTER node.')

            # need to stop fenced just in case it's running already
            logger.warning('Forcefully stopping fenced')
            self.run_call('failover.fenced.stop')
            logger.warning('Done forcefully stopping fenced')

            logger.warning('Forcefully starting fenced')
            fenced_error = self.run_call('failover.fenced.start', True)
            logger.warning('Done forcefully starting fenced')
        else:
            # if we're here then we need to check a couple things before we start fenced
            # and start the process of becoming master
            #
            #   1. if the interface that we've received a MASTER event for is
            #       in a failover group with other interfaces and ANY of the
            #       other members in the failover group are still BACKUP,
            #       then we need to ignore the event.
            #
            #   TODO: Not sure how keepalived and laggs operate so need to test this
            #           (maybe the event only gets triggered if the lagg goes down)
            #
            logger.info('Checking VIP failover groups')
            _, backups, offline = self.run_call(
                'failover.vip.check_failover_group', ifname, fobj['groups']
            )
            logger.info('Done checking VIP failover groups')

            if offline:
                # this isn't common but we're very verbose in this file so let's
                # log the offline interfaces while we're here
                logger.warning('Offline interfaces detected: %r', ', '.join(offline))

            # this means that we received a master event and the interface was
            # in a failover group. And in that failover group, there were other
            # interfaces that were still in the BACKUP state which means the
            # other node has them as MASTER so ignore the event.
            if backups:
                logger.warning(
                    'Received MASTER event for %r, but other '
                    'interfaces (%s) are still working on the '
                    'MASTER node. Ignoring event.', ifname, ', '.join(backups),
                )

                job.set_progress(None, description='IGNORED')
                raise IgnoreFailoverEvent()

            logger.warning('Entering MASTER on "%s".', ifname)

            # need to stop fenced just in case it's running already
            logger.warning('Stopping fenced')
            self.run_call('failover.fenced.stop')
            logger.warning('Done stopping fenced')

            logger.warning('Restarting fenced')
            fenced_error = self.fenced_start_loop()
            logger.warning('Done restarting fenced')

        # starting fenced daemon failed....which is bad
        # emit an error and exit
        if fenced_error != 0:
            if fenced_error == 1:
                logger.error('Failed to register keys on disks, exiting!')
            elif fenced_error == 2:
                logger.error('Fenced is running on the remote node, exiting!')
            elif fenced_error == 3:
                logger.error('10% or more of the disks failed to be reserved, exiting!')
            elif fenced_error == 5:
                logger.error('Fenced encountered an unexpected fatal error, exiting!')
            else:
                logger.error(f'Fenced exited with code "{fenced_error}" which should never happen, exiting!')

            job.set_progress(None, description='ERROR')
            raise FencedError()

        # fenced is now running, so we *are* the ACTIVE/MASTER node

        # if 2x interfaces are in the same failover group and 1 of them goes
        # down, the VIP will float to the other controller. However, a failover
        # won't happen because the other interface is still UP on the master.
        # If the down'ed interface comes back online, the VIP needs to float
        # back to the original master controller. Reloading keepalived service
        # re-generates the configuration file which ensures the config has the
        # right priority set.
        logger.info('Pausing failover event processing')
        self.run_call('vrrpthread.pause_events')
        logger.info('Taking ownership of all VIPs')
        self.run_call('service.control', 'RELOAD', 'keepalived', self.HA_PROPAGATE, job=True)
        logger.info('Unpausing failover event processing')
        self.run_call('vrrpthread.unpause_events')
        logger.info('Done unpausing failover event processing')

        # Kick off a job to clean up any left-over ALUA state from when we were STANDBY/BACKUP.
        logger.info('Verifying iSCSI service')
        iscsi_suspended = iscsi_cleaned = False
        if self.run_call('service.started_or_enabled', 'iscsitarget'):
            logger.info('Checking if ALUA is enabled')
            handle_alua = self.run_call('iscsi.global.alua_enabled')
            logger.info('Done checking if ALUA is enabled')
            if handle_alua:
                iscsi_suspended, iscsi_cleaned = self.iscsi_cleanup_alua_state()
        else:
            handle_alua = False
        logger.info('Done verifying iSCSI service')

        if not fobj['volumes']:
            # means we received a master event but there are no zpools to import
            # (happens when the box is initially licensed for HA and being setup)
            # there is nothing else to do so just log a warning and return early
            logger.warning('No zpools to import, exiting failover event')
            self.FAILOVER_RESULT = 'INFO'
            return self.FAILOVER_RESULT

        # unlock SED disks
        logger.info('Unlocking all SED disks (if any)')
        maybe_unlocked = False
        try:
            maybe_unlocked = self.run_call('disk.sed_unlock_all', True)
        except Exception as e:
            # failing here doesn't mean the zpool won't import
            # we could have failed on only 1 disk so log an
            # error and move on
            logger.error('Failed to unlock SED disk(s) with error: %r', e)

        if maybe_unlocked:
            logger.info('Done unlocking all SED disks (if any)')
            try:
                logger.info('Retasting disks on standby node')
                self.run_call('failover.call_remote', 'disk.retaste', [], {'raise_connect_error': False})
                logger.info('Done retasting disks on standby node')
            except Exception:
                logger.exception('Unexpected failure retasting disks on standby node')

        # setup the zpool cachefile  TODO: see comment below about cachefile usage
        # self.run_call('failover.zpool.cachefile.setup', 'MASTER')

        # set the progress to IMPORTING
        job.set_progress(None, description='IMPORTING')

        failed = []
        options = {'altroot': '/mnt'}
        import_options = {'missing_log': True}
        any_host = True
        # TODO: maintaing zpool cachefile is very fragile and can
        # ruin the ability to successfully import a zpool on failover
        # event.... Until we can truly dig into this problem, we'll
        # ignore the cache file for now
        # cachefile = ZPOOL_CACHE_FILE
        new_name = cachefile = None
        for vol in fobj['volumes']:
            logger.info('Importing %r', vol['name'])

            # import the zpool(s)
            try_again = False
            try:
                self.run_call(
                    'zfs.pool.import_pool', vol['guid'], options, any_host, cachefile, new_name, import_options
                )
            except Exception as e:
                if e.errno == errno.ENOENT:
                    try_again = True
                    # logger.warning('Failed importing %r using cachefile so trying without it.', vol['name'])
                    logger.warning('Failed importing %r with ENOENT.', vol['name'])
                else:
                    vol['error'] = str(e)
                    failed.append(vol)
                    continue
            else:
                logger.info('Successfully imported %r', vol['name'])

            if try_again:
                # means the cachefile is "stale" or invalid which will prevent
                # an import so let's try to import without it
                logger.warning('Retrying import of %r', vol['name'])
                try:
                    self.run_call(
                        'zfs.pool.import_pool', vol['guid'], options, any_host, None, new_name, import_options
                    )
                except Exception as e:
                    vol['error'] = str(e)
                    failed.append(vol)
                    continue
                else:
                    logger.info('Successful retry import of %r', vol['name'])

                # TODO: come back and fix this once we figure out how to properly manage zpool cachefile
                # (i.e. we need a cachefile per zpool, and not a global one)
                """
                try:
                    # make sure the zpool cachefile property is set appropriately
                    self.run_call(
                        'zfs.pool.update', vol['name'], {'properties': {'cachefile': {'value': ZPOOL_CACHE_FILE}}}
                    )
                except Exception:
                    logger.warning('Failed to set cachefile property for %r', vol['name'], exc_info=True)
                """

            # If root dataset was encrypted, it would not be mounted at this point regardless of it being
            # key/passphrase encrypted - so we make sure that nothing at this point in time is mounted beneath it
            # if that pool has datasets which are unencrypted
            logger.info('Handling unencrypted datasets on import (if any) for %r', vol['name'])
            self.run_call('pool.handle_unencrypted_datasets_on_import', vol['name'])
            logger.info('Successfully handled unencrypted datasets on import (if any) for %r', vol['name'])

            # try to unlock the zfs datasets (if any)
            logger.info('Unlocking zfs datasets (if any) for %r', vol['name'])
            unlock_job = self.run_call('failover.unlock_zfs_datasets', vol['name'])
            unlock_job.wait_sync()
            if unlock_job.error:
                logger.error(f'Error unlocking ZFS encrypted datasets: {unlock_job.error}')
            elif unlock_job.result['failed']:
                logger.error('Failed to unlock %s ZFS encrypted dataset(s)', ','.join(unlock_job.result['failed']))
            else:
                logger.info('Successfully completed unlock for %r', vol['name'])

        # if we fail to import all zpools then alert the user because nothing
        # is going to work at this point
        if len(failed) == len(fobj['volumes']):
            for i in failed:
                logger.error(
                    'Failed to import volume with name %r with guid %r with error:\n %r',
                    i['name'], i['guid'], i['error'],
                )

            logger.error('All volumes failed to import!')
            job.set_progress(None, description='ERROR')
            raise AllZpoolsFailedToImport()
        elif len(failed):
            # if we fail to import any of the zpools then alert the user but continue the process
            for i in failed:
                logger.error(
                    'Failed to import volume with name %r with guid %r with error:\n %r',
                    i['name'], i['guid'], i['error'],
                )
                logger.error(
                    'However, other zpools imported so the failover process continued.'
                )
        else:
            logger.info('Volume imports complete')

        # Now that the volumes have been imported, get a head-start on activating extents.
        if handle_alua and iscsi_cleaned:
            logger.info('Activating ALUA extents')
            self.run_call('iscsi.alua.activate_extents')
            logger.info('Done activating ALUA extents')

        # need to make sure failover status is updated in the middleware cache
        logger.info('Refreshing failover status')
        self.run_call('failover.status_refresh')
        logger.info('Done refreshing failover status')

        # this enables all necessary services that have been enabled by the user
        logger.info('Enabling necessary services')
        self.run_call('etc.generate', 'rc')
        logger.info('Done enabling necessary services')

        logger.info('Configuring system dataset')
        self.run_call('systemdataset.setup')
        logger.info('Done configuring system dataset')

        # now we restart the services, prioritizing the "critical" services
        logger.info('Restarting critical services.')
        self.run_call('failover.events.restart_services', {'critical': True})
        logger.info('Done restarting critical services')

        # setup directory services. This is backgrounded job
        logger.info('Starting background job for directoryservices.setup')
        self.run_call('directoryservices.setup')
        logger.info('Done starting background job for directoryservices.setup')

        logger.info('Starting background job for prefetching DDT for zpools')
        self.middleware.create_task(self.middleware.call('zfs.pool.ddt_prefetch_pools'))

        logger.info('Allowing network traffic.')
        fw_accept_job = self.run_call('failover.firewall.accept_all')
        fw_accept_job.wait_sync()
        if fw_accept_job.error:
            logger.error(f'Error allowing network traffic: {fw_accept_job.error}')
        else:
            logger.info('Done allowing network traffic.')

        logger.info('Critical portion of failover is now complete')

        # regenerate cron
        logger.info('Regenerating cron')
        self.run_call('etc.generate', 'cron')
        logger.info('Done regenerating cron')

        # sync disks is disabled on passive node
        logger.info('Syncing disks')
        self.run_call('disk.sync_all', {'zfs_guid': True})
        logger.info('Done syncing disks')

        if handle_alua:
            try:
                if iscsi_suspended:
                    logger.info('Clearing iSCSI suspend')
                    if self.run_call('iscsi.scst.clear_suspend'):
                        logger.info('Cleared iSCSI suspend')
                # Kick off a job to start clearing up HA targets from when we were STANDBY
                self.run_call('iscsi.alua.reset_active')
            except Exception:
                logger.exception('Failed to complete iSCSI bringup')

        # restart the remaining "non-critical" services
        logger.info('Restarting remaining services')
        self.run_call('failover.events.restart_services', {'critical': False, 'timeout': 60})
        logger.info('Done restarting remaining services')

        logger.info('Restarting reporting metrics')
        self.run_call('service.control', 'RESTART', 'netdata', job=True)
        logger.info('Done restarting reporting metrics')

        logger.info('Updating replication tasks')
        self.run_call('zettarepl.update_tasks')
        logger.info('Done updating replication tasks')

        logger.info('Temporarily blocking failover alerts')
        self.run_call('alert.block_failover_alerts')
        logger.info('Done temporarily blocking failover alerts')

        logger.info('Initializing alert system')
        self.run_call('alert.initialize', False)
        logger.info('Done initializing alert system')

        logger.info('Initializing task to renew certs if necessary')
        self.middleware.create_task(self.middleware.call('certificate.renew_certs'))
        logger.info('Done initializing task to renew certs if necessary')

        logger.info('Starting truecommand service (if necessary)')
        self.run_call('truecommand.start_truecommand_service')
        logger.info('Done starting truecommand service (if necessary)')

        logger.info('Configuring TrueNAS Connect Service (if necessary)')
        self.run_call('tn_connect.state.check')
        logger.info('Configuring TrueNAS Connect Service (if necessary)')

        # The system, while it was in BACKUP state, might have failed to contact the remote node and reached a
        # conclusion that the other node needs to be rebooted. Let's clean this up.
        self.run_call('failover.reboot.discard_unbound_remote_reboot_reasons')

        kmip_config = self.run_call('kmip.config')
        if kmip_config and kmip_config['enabled']:
            logger.info('Syncing encryption keys with KMIP server')

            # Even though we keep keys in sync, it's best that we do this as well
            # to ensure that the system is up to date with the latest keys available
            # from KMIP. If it's unaccessible, the already synced memory keys are used
            # meanwhile.
            self.run_call('kmip.initialize_keys')
            logger.info('Done syncing encryption keys with KMIP server')

        self.start_vms()
        self.start_apps()
        self.start_virt()

        logger.info('Migrating interface information (if required)')
        self.run_call('interface.persist_link_addresses')
        logger.info('Done migrating interface information (if required)')

        try:
            logger.info('Updating HA reboot info')
            self.run_call('failover.reboot.info')
        except Exception:
            logger.warning('Failed to update reboot info', exc_info=True)
        else:
            logger.info('Done updating HA reboot info')

        logger.info('Failover event complete.')

        # clear the description and set the result
        job.set_progress(None, description='SUCCESS')

        self.FAILOVER_RESULT = 'SUCCESS'

        return self.FAILOVER_RESULT

    @job(lock=FAILOVER_LOCK_NAME, read_roles=['READONLY_ADMIN'])
    def vrrp_backup(self, job, fobj, ifname, event):

        # we need to check a couple things before we stop fenced
        # and start the process of becoming backup
        #
        #   1. if the interface that we've received a BACKUP event for is
        #       in a failover group with other interfaces and ANY of the
        #       other members in the failover group are still MASTER,
        #       then we need to ignore the event.
        #
        #   TODO: Not sure how keepalived and laggs operate so need to test this
        #           (maybe the event only gets triggered if the lagg goes down)
        #
        masters, _, offline = self.run_call(
            'failover.vip.check_failover_group', ifname, fobj['groups']
        )

        if offline:
            # this isn't common but we're very verbose in this file so let's
            # log the offline interfaces while we're here
            logger.warning('Offline interfaces detected: %r', ', '.join(offline))

        # this means that we received a BACKUP event and the interface was
        # in a failover group. And in that failover group, there were other
        # interfaces that were still in the MASTER state so ignore the event.
        if masters:
            logger.warning(
                'Received BACKUP event for %r, but other '
                'interfaces (%s) are still working. '
                'Ignoring event.', ifname, ', '.join(masters),
            )

            job.set_progress(None, description='IGNORED')
            raise IgnoreFailoverEvent()

        logger.warning('Entering BACKUP on "%s".', ifname)

        # We will try to give some time to docker to gracefully stop before zpools will be forcefully
        # exported. This is to avoid any potential data corruption.
        stop_docker_thread = threading.Thread(
            target=self.stop_apps,
            name='failover_stop_docker',
        )
        stop_docker_thread.start()
        stop_vm_thread = threading.Thread(target=self.stop_vms, name='failover_stop_vms')
        stop_vm_thread.start()

        # We will try to give some time to containers to gracefully stop before zpools will be forcefully
        # exported. This is to avoid any potential data corruption.
        stop_virt_thread = threading.Thread(
            target=self.stop_virt,
            name='failover_stop_virt',
        )
        stop_virt_thread.start()

        # We stop netdata before exporting pools because otherwise we might have erroneous stuff
        # getting logged and causing spam
        logger.info('Stopping reporting metrics')
        self.run_call('service.control', 'STOP', 'netdata', self.HA_PROPAGATE, job=True)

        logger.info('Blocking network traffic.')
        fw_drop_job = self.run_call('failover.firewall.drop_all')
        fw_drop_job.wait_sync()
        if fw_drop_job.error:
            logger.error(f'Error blocking network traffic: {fw_drop_job.error}')

        # restarting keepalived sends a priority 0 advertisement
        # which means any VIP that is on this controller will be
        # migrated to the other controller
        logger.info('Pausing failover event processing')
        self.run_call('vrrpthread.pause_events')
        logger.info('Transitioning all VIPs off this node')
        self.run_call('service.control', 'STOP', 'keepalived', self.HA_PROPAGATE, job=True)

        # ticket 23361 enabled a feature to send email alerts when an unclean reboot occurrs.
        # TrueNAS HA, by design, has a triggered unclean shutdown.
        # If a controller is demoted to standby, we set a 4 sec countdown using watchdog.
        # If the zpool(s) can't export within that timeframe, we use watchdog to violently reboot the controller.
        # When this occurrs, the customer gets an email about an "Unauthorized system reboot".
        # The idea for creating a new sentinel file for watchdog related panics,
        # is so that we can send an appropriate email alert.
        # So if we panic here, middleware will check for this file and send an appropriate email.
        # ticket 39114
        with contextlib.suppress(Exception):
            with open(WATCHDOG_ALERT_FILE, 'w') as f:
                f.write(f'{time.time()}')
                f.flush()  # be sure it goes straight to disk
                os.fsync(f.fileno())  # be EXTRA sure it goes straight to disk

        # setup the zpool cachefile
        # self.run_call('failover.zpool.cachefile.setup', 'BACKUP')

        # export zpools in a thread and set a timeout to
        # to `self.ZPOOL_EXPORT_TIMEOUT`.
        # if we can't export the zpool(s) in this timeframe,
        # we send the 'b' character to the /proc/sysrq-trigger
        # to trigger an immediate reboot of the system
        # https://www.kernel.org/doc/html/latest/admin-guide/sysrq.html
        export_thread = threading.Thread(
            target=self._export_zpools,
            name='failover_export_zpools',
            args=(fobj['volumes'], )
        )
        export_thread.start()
        export_thread.join(timeout=self.ZPOOL_EXPORT_TIMEOUT)
        if export_thread.is_alive():
            # have to enable the "magic" sysrq triggers
            with open('/proc/sys/kernel/sysrq', 'w') as f:
                f.write('1')

            # now violently reboot
            with open('/proc/sysrq-trigger', 'w') as f:
                f.write('b')

        # Pools are now exported and so we can make disks available to other controller
        logger.warning('Stopping fenced')
        self.run_call('failover.fenced.stop')

        # In the rare case where the pwenc_secret file doesn't match, we'll
        # copy over the secret seed file from the active and reinitialize
        try:
            self.run_call(
                'failover.call_remote',
                'failover.send_small_file',
                [PWENC_FILE_SECRET],
                {'raise_connect_error': False}
            )
        except Exception:
            self.logger.error('Failed to reinitialize pwenc', exc_info=True)

        # Now that fenced is stopped, attach NVMe/RoCE.
        logger.info('Start bring up of NVMe/RoCE')
        try:
            # Do not need to wait, nor request fenced_reload
            self.run_call('jbof.configure_job')
        except Exception:
            logger.error('Unexpected error', exc_info=True)

        # We also remove this file here, because on boot we become BACKUP if the other
        # controller is MASTER. So this means we have no volumes to export which means
        # the `self.ZPOOL_EXPORT_TIMEOUT` is honored.
        with contextlib.suppress(Exception):
            os.unlink(WATCHDOG_ALERT_FILE)

        logger.info('Refreshing failover status')
        self.run_call('failover.status_refresh')

        logger.info('Setting up system dataset')
        self.run_call('systemdataset.setup')

        logger.info('Regenerating cron')
        self.run_call('etc.generate', 'cron')

        self.run_call('truecommand.stop_truecommand_service')

        logger.info('Stopping NFS mountd service')
        self.run_call('service.control', 'STOP', 'mountd', job=True)

        # we keep SSH running on both controllers (if it's enabled by user)
        filters = [['srv_service', '=', 'ssh']]
        options = {'get': True}
        if self.run_call('datastore.query', 'services.services', filters, options)['srv_enable']:
            logger.info('Restarting SSH')
            self.run_call('service.control', 'RESTART', 'ssh', self.HA_PROPAGATE, job=True)

        if self.run_call('iscsi.global.alua_enabled'):
            if self.run_call('service.started_or_enabled', 'iscsitarget'):
                logger.info('Starting iSCSI for ALUA')
                # Rewrite the scst.conf config to a clean slate state
                self.run_call('iscsi.alua.standby_write_empty_config', True)
                self.run_call('etc.generate', 'scst')

                # The most likely situation is that scst is not running
                if self.run_call('iscsi.scst.is_kernel_module_loaded'):
                    self.run_call('service.control', 'RESTART', 'iscsitarget', self.HA_PROPAGATE, job=True)
                else:
                    self.run_call('service.control', 'START', 'iscsitarget', self.HA_PROPAGATE, job=True)

        if self.run_call('nvmet.global.ana_active') and self.run_call('service.started_or_enabled', 'nvmet'):
            if self.run_call('nvmet.global.running'):
                logger.info('Reloading NVMe-oF target for ANA')
                self.run_call('service.control', 'RELOAD', 'nvmet', self.HA_PROPAGATE, job=True)
            else:
                logger.info('Starting NVMe-oF target for ANA')
                self.run_call('service.control', 'START', 'nvmet', self.HA_PROPAGATE, job=True)
        elif self.run_call('nvmet.global.running'):
            logger.info('Stopping NVMe-oF target')
            self.run_call('service.control', 'STOP', 'nvmet', self.HA_PROPAGATE, job=True)
        else:
            logger.info('No changes required for NVMe-oF target')

        logger.info('Syncing encryption keys from MASTER node (if any)')
        try:
            self.run_call('failover.call_remote', 'failover.sync_keys_to_remote_node', [],
                          {'raise_connect_error': False})
        except Exception:
            logger.warning('Unhandled exception syncing keys from MASTER node', exc_info=True)

        try:
            self.run_call('failover.call_remote', 'interface.persist_link_addresses', [],
                          {'raise_connect_error': False})
        except Exception:
            logger.warning('Unhandled exception persisting network interface link addresses on MASTER node',
                           exc_info=True)

        logger.info('Starting VRRP daemon')
        self.run_call('service.control', 'START', 'keepalived', self.HA_PROPAGATE, job=True)
        logger.info('Unpausing failover event processing')
        self.run_call('vrrpthread.unpause_events')

        logger.info('Retasting disks (if required)')
        self.run_call('disk.retaste')
        logger.info('Done retasting disks (if required)')

        logger.info('Activating directory services')
        try:
            self.run_call('directoryservices.connection.activate_standby', None)
        except Exception:
            logger.warning('Failed to activate directory services', exc_info=True)
        logger.info('Done activating directory services')

        logger.info('Successfully became the BACKUP node.')
        self.FAILOVER_RESULT = 'SUCCESS'

        return self.FAILOVER_RESULT

    def start_vms(self):
        logger.info('Starting VMs which are set to start on boot')
        self.middleware.create_task(self.middleware.call('vm.start_on_boot'))

    def stop_vms(self):
        logger.info('Trying to gracefully stop VMs')
        try:
            self.run_call('vm.handle_shutdown')
        except Exception:
            logger.error('Failed to gracefully stop VMs', exc_info=True)

    def start_apps(self):
        self.start_apps_impl()

    def start_apps_impl(self):
        pool = self.run_call('docker.config')['pool']
        if not pool:
            self.middleware.call_sync('docker.state.set_status', DockerStatus.UNCONFIGURED.value)
            logger.info('Skipping starting apps as they are not configured')
            return

        logger.info('Going to initialize apps plugin as %r pool is configured for apps', pool)
        try:
            self.run_call('docker.state.start_service', True)
        except Exception:
            logger.error('Failed to start docker service', exc_info=True)
        else:
            logger.info('Docker service started successfully')

    def stop_apps(self):
        if not self.middleware.call_sync('docker.config')['dataset']:
            return

        logger.info('Trying to gracefully stop docker service')
        try:
            self.run_call('service.control', 'STOP', 'docker', job=True)
        except Exception:
            logger.error('Failed to stop docker service gracefully', exc_info=True)
        else:
            logger.info('Docker service stopped gracefully')

    def start_virt(self):
        logger.info('Going to initialize virt plugin')
        job = self.run_call('virt.global.setup')
        job.wait_sync(timeout=10)
        if job.error:
            logger.info('Failed to setup virtualization: %r', job.error)
        else:
            config = self.run_call('virt.global.config')
            if config['state'] == VirtStatus.INITIALIZED.value:
                logger.info('Virtualization initalized.')
            elif config['state'] != VirtStatus.NO_POOL.value:
                logger.warning('Virtualization failed to initialize with state %r.', config['state'])

    def stop_virt(self):
        logger.info('Going to stop virt plugin')
        job = self.run_call('virt.global.reset')
        # virt instances have a timeout of 10 seconds to stop
        job.wait_sync(timeout=15)
        if job.error:
            logger.warning('Failed to reset virtualization state.')
        else:
            logger.info('Virtualization has been successfully resetted.')


async def vrrp_fifo_hook(middleware, data):
    ifname = data['ifname']
    event = data['event']
    middleware.send_event(
        'failover.vrrp_event',
        'CHANGED',
        fields={
            'ifname': ifname,
            'event': event,
        }
    )

    await middleware.call('failover.events.event', ifname, event)


def setup(middleware):
    middleware.event_register('failover.vrrp_event', 'Sent when a VRRP state changes.')
    middleware.register_hook('vrrp.fifo', vrrp_fifo_hook)
