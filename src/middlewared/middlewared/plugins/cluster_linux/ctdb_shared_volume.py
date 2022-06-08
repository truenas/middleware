import errno
import os
from pathlib import Path
from glustercli.cli import volume

from middlewared.service import Service, CallError, job
from middlewared.plugins.cluster_linux.utils import CTDBConfig


MOUNT_UMOUNT_LOCK = CTDBConfig.MOUNT_UMOUNT_LOCK.value
CRE_OR_DEL_LOCK = CTDBConfig.CRE_OR_DEL_LOCK.value
CTDB_VOL_NAME = CTDBConfig.CTDB_VOL_NAME.value
CTDB_LOCAL_MOUNT = CTDBConfig.CTDB_LOCAL_MOUNT.value


class CtdbSharedVolumeService(Service):

    class Config:
        namespace = 'ctdb.shared.volume'
        private = True

    async def validate(self):
        filters = [('id', '=', CTDB_VOL_NAME)]
        ctdb = await self.middleware.call('gluster.volume.query', filters)
        if not ctdb:
            # it's expected that ctdb shared volume exists when
            # calling this method
            raise CallError(f'{CTDB_VOL_NAME} does not exist', errno.ENOENT)

        for i in ctdb:
            err_msg = f'A volume named "{CTDB_VOL_NAME}" already exists '
            if i['type'] != 'REPLICATE':
                err_msg += (
                    'but is not a "REPLICATE" type volume. '
                    'Please delete or rename this volume and try again.'
                )
                raise CallError(err_msg)
            elif i['replica'] < 3 or i['num_bricks'] < 3:
                err_msg += (
                    'but is configured in a way that '
                    'could cause data corruption. Please delete '
                    'or rename this volume and try again.'
                )
                raise CallError(err_msg)

    @job(lock=CRE_OR_DEL_LOCK)
    async def create(self, job):
        """
        Create and mount the shared volume to be used
        by ctdb daemon.
        """
        # check if ctdb shared volume already exists and started
        info = await self.middleware.call('gluster.volume.exists_and_started', CTDB_VOL_NAME)
        if not info['exists']:
            # get the peers in the TSP
            peers = await self.middleware.call('gluster.peer.query')
            if not peers:
                raise CallError('No peers detected')

            # shared storage volume requires 3 nodes, minimally, to
            # prevent the dreaded split-brain
            con_peers = [i['hostname'] for i in peers if i['connected'] == 'Connected']
            if len(con_peers) < 3:
                raise CallError(
                    '3 peers must be present and connected before the ctdb '
                    'shared volume can be created.'
                )

            # get the system dataset location
            ctdb_sysds_path = (await self.middleware.call('systemdataset.config'))['path']
            ctdb_sysds_path = str(Path(ctdb_sysds_path).joinpath(CTDB_VOL_NAME))

            bricks = []
            for i in con_peers:
                bricks.append(i + ':' + ctdb_sysds_path)

            options = {'args': (CTDB_VOL_NAME, bricks,)}
            options['kwargs'] = {'replica': len(con_peers), 'force': True}
            await self.middleware.call('gluster.method.run', volume.create, options)

        # make sure the shared volume is configured properly to prevent
        # possibility of split-brain/data corruption with ctdb service
        await self.middleware.call('ctdb.shared.volume.validate')

        if not info['started']:
            # start it if we get here
            await self.middleware.call('gluster.volume.start', {'name': CTDB_VOL_NAME})

        # try to mount it locally and send a request
        # to all the other peers in the TSP to also
        # FUSE mount it
        data = {'event': 'VOLUME_START', 'name': CTDB_VOL_NAME, 'forward': True}
        await self.middleware.call('gluster.localevents.send', data)

        # we need to wait on the local FUSE mount job since
        # ctdb daemon config is dependent on it being mounted
        fuse_mount_job = await self.middleware.call('core.get_jobs', [
            ('method', '=', 'gluster.fuse.mount'),
            ('arguments.0.name', '=', 'ctdb_shared_vol'),
            ('state', '=', 'RUNNING')
        ])
        if fuse_mount_job:
            wait_id = await self.middleware.call('core.job_wait', fuse_mount_job[0]['id'])
            await wait_id.wait()

        # The peers in the TSP could be using dns names while ctdb
        # only accepts IP addresses. This means we need to resolve
        # the hostnames of the peers in the TSP to their respective
        # IP addresses so we can write them to the ctdb private ip file.
        names = [i['hostname'] for i in await self.middleware.call('gluster.peer.query')]
        ips = await self.middleware.call('cluster.utils.resolve_hostnames', names)
        if len(names) != len(ips):
            # this means the gluster peers hostnames resolved to the same
            # ip address which is bad....in theory, this shouldn't occur
            # since adding gluster peers has it's own validation and would
            # cause it to fail way before this gets called but it's better
            # to be safe than sorry
            raise CallError('Duplicate gluster peer IP addresses detected.')

        # Setup the ctdb daemon config. Without ctdb daemon running, none of the
        # sharing services (smb/nfs) will work in an active-active setting.
        priv_ctdb_ips = [i['address'] for i in await self.middleware.call('ctdb.private.ips.query')]
        for ip_to_add in [i for i in ips if i not in [j for j in priv_ctdb_ips]]:
            ip_add_job = await self.middleware.call('ctdb.private.ips.create', {'ip': ip_to_add})
            await ip_add_job.wait()

        # this sends an event telling all peers in the TSP (including this system)
        # to start the ctdb service
        data = {'event': 'CTDB_START', 'name': CTDB_VOL_NAME, 'forward': True}
        await self.middleware.call('gluster.localevents.send', data)

        return await self.middleware.call('gluster.volume.query', [('name', '=', CTDB_VOL_NAME)])

    @job(lock=CRE_OR_DEL_LOCK)
    async def teardown(self, job):
        if await self.middleware.call('service.started', 'cifs'):
            job.set_progress(25, 'Stopping SMB')
            await self.middleware.call('service.stop', 'cifs')

        job.set_progress(50, 'Stopping ctdb')
        await self.middleware.call('service.stop', 'ctdb')

        def __remove_config():
            # keep this inner method so it doesn't get (mis)used anywhere else.
            symlinked_files = [
                CTDBConfig.ETC_REC_FILE.value,
                CTDBConfig.ETC_PRI_IP_FILE.value,
                CTDBConfig.ETC_PUB_IP_FILE.value,
            ]
            fuse_mount_files = [
                CTDBConfig.GM_RECOVERY_FILE.value,
                CTDBConfig.GM_PRI_IP_FILE.value,
                CTDBConfig.GM_PUB_IP_FILE.value,
            ]
            for i in symlinked_files + fuse_mount_files:
                try:
                    os.remove(i)
                except FileNotFoundError:
                    pass
                except Exception:
                    self.logger.warning('Failed to remove %r', i, exc_info=True)

            persistent_data_dirs = [
                CTDBConfig.PER_DB_DIR.value,
                CTDBConfig.STA_DB_DIR.value,
            ]
            for _dir in persistent_data_dirs:
                try:
                    for _file in Path(_dir).iterdir():
                        try:
                            _file.unlink(missing_ok=True)
                        except Exception:
                            self.logger.warning('Failed to remove %r', _file, exc_info=True)
                except FileNotFoundError:
                    pass
                except Exception:
                    self.logger.warning('Failed to remove contents of %r', _dir, exc_info=True)

        job.set_progress(75, 'Removing ctdbd configuration data')
        await self.middleware.run_in_thread(__remove_config)

        job.set_progress(85, f'Umounting {CTDB_VOL_NAME!r} fuse filesystem')
        fuse_job = await self.middleware.call('gluster.fuse.umount', {'name': CTDB_VOL_NAME})
        await fuse_job.wait()

        # TODO: This is a stop-gap work-around. ctdb owns the public ip address(es) 100%
        # and will remove said IP address(es) from the interface(s) when the service is stopped.
        # This is expected behavior. TC is expecting the user to configure public IP address(es)
        # via our API and then assign the IP address(es) to the ctdb config. This is wrong design
        # and will be fixed in next major release.
        job.set_progress(99, 'Resyncing network interfaces')
        await self.middleware.call('interface.sync')

        job.set_progress(100, 'CTDB shared volume teardown complete.')

    @job(lock=CRE_OR_DEL_LOCK)
    async def delete(self, job):
        """
        Delete and unmount the shared volume used by ctdb daemon.
        """
        # nothing to delete if it doesn't exist
        info = await self.middleware.call('gluster.volume.exists_and_started', CTDB_VOL_NAME)
        if not info['exists']:
            return

        # stop the gluster volume
        if info['started']:
            options = {'args': (CTDB_VOL_NAME,), 'kwargs': {'force': True}}
            job.set_progress(33, f'Stopping gluster volume {CTDB_VOL_NAME!r}')
            await self.middleware.call('gluster.method.run', volume.stop, options)

        # finally, we delete it
        job.set_progress(66, f'Deleting gluster volume {CTDB_VOL_NAME!r}')
        await self.middleware.call('gluster.method.run', volume.delete, {'args': (CTDB_VOL_NAME,)})
        job.set_progress(100, f'Successfully deleted {CTDB_VOL_NAME!r}')
