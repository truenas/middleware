from middlewared.service import job, Service, CallError, accepts
from middlewared.utils import run
from middlewared.plugins.cluster_linux.utils import CTDBConfig, JOB_LOCK

import os
import pathlib
import subprocess


class CtdbSharedVolumeService(Service):

    class Config:
        namespace = 'ctdb.shared.volume'

    CTDB_VOL_NAME = CTDBConfig.CTDB_VOL_NAME.value

    async def construct_gluster_ctdb_api_request(self, peers):

        payload = {}

        # get the system dataset location
        ctdb_sysds_path = (await self.middleware.call('systemdataset.config'))['path']
        ctdb_sysds_path = os.path.join(ctdb_sysds_path, self.CTDB_VOL_NAME)

        bricks = []
        for i in peers:
            bricks.append({
                'peer_name': i,
                'peer_path': ctdb_sysds_path,
            })

        payload = {
            'name': self.CTDB_VOL_NAME,
            'bricks': bricks,
            'replica': len(peers),
            'force': True,
        }

        return payload

    async def shared_volume_exists_and_started(self):

        exists = started = False
        v = await self.middleware.call('gluster.volume.status', self.CTDB_VOL_NAME)
        await v.wait()
        if v.error:
            raise CallError(f'{v.error}')
        elif v.result:
            vol = v.result[0]
            if vol['type'] != 'REPLICATE':
                raise CallError(
                    f'A volume with the name "{self.CTDB_VOL_NAME}" already exists '
                    'but is not a REPLICATE type volume. Please delete or rename '
                    'this volume and try again.'
                )
            elif vol['replica'] < 3 or vol['num_bricks'] < 3:
                raise CallError(
                    f'A volume with the name "{self.CTDB_VOL_NAME}" already exists '
                    'but is configured in a way that could cause split-brain. '
                    'Please delete or rename this volume and try again.'
                )
            elif vol['status'] != 'Started':
                exists = True
                start = await self.middleware.call('gluster.volume.start', self.CTDB_VOL_NAME)
                await start.wait()
                if start.error:
                    raise CallError(f'{start.error}')
                started = True
            else:
                exists = started = True

        return exists, started

    @accepts()
    @job(lock='ctdb_create_lock')
    async def create(self, job):

        """
        Create and mount the shared volume to be used
        by ctdb daemon.
        """

        # check if ctdb shared volume already exists and started
        exists, started = await self.shared_volume_exists_and_started()
        if exists and started:
            return

        if not exists:
            # get the peers in the TSP
            peers = await self.middleware.call('gluster.peer.pool')
            await peers.wait()
            if peers.error:
                raise CallError(f'{peers.error}')
            elif not peers.result:
                raise CallError('No peers detected')

            # shared storage volume requires 3 nodes, minimally, to
            # prevent the dreaded split-brain
            con_peers = [i['hostname'] for i in peers.result if i['connected'] == 'Connected']
            if len(con_peers) < 3:
                raise CallError(
                    '3 peers must be present and connected before the ctdb '
                    'shared volume can be created.'
                )

            # create the ctdb shared volume
            req = await self.construct_gluster_ctdb_api_request(con_peers)
            create = await self.middleware.call('gluster.volume.create', req)
            await create.wait()
            if create.error:
                raise CallError(f'{create.error}')

        if not started:
            # start it if we get here
            start = await self.middleware.call('gluster.volume.start', self.CTDB_VOL_NAME)
            await start.wait()
            if start.error:
                raise CallError(f'{start.error}')

        # try to mount it locally
        mount = await self.middleware.call('ctdb.shared.volume.mount')
        await mount.wait()
        if mount.error:
            raise CallError(f'{mount.error}')

        return 'SUCCESS'

    @accepts()
    @job(lock='ctdb_delete_lock')
    async def delete(self, job):

        """
        Delete and unmount the shared volume used by ctdb daemon.
        """

        # nothing to delete if it doesn't exist
        exists, started = await self.shared_volume_exists_and_started()
        if not exists:
            return

        # umount it first
        umount = await self.middleware.call('ctdb.shared.volume.umount')
        await umount.wait()
        if umount.error:
            raise CallError(f'{umount.error}')

        if started:
            # stop the volume
            force = {'force': True}
            stop = await self.middleware.call('gluster.volume.stop', self.CTDB_VOL_NAME, force)
            await stop.wait()
            if stop.error:
                raise CallError(f'{stop.error}')

        # now delete it
        data = {'name': self.CTDB_VOL_NAME}
        delete = await self.middleware.call('gluster.volume.delete', data)
        await delete.wait()
        if delete.error:
            raise CallError(f'{delete.error}')

        return 'SUCCESS'

    @accepts()
    @job(lock=JOB_LOCK)
    async def mount(self, job):

        """
        Mount the ctdb shared volume locally.
        """

        # We call this method on startup so if we were
        # to add a call to the `create` method then all
        # nodes in the cluster would try to create the
        # shared volume which is unnecessary and will
        # cause lots of errors since only 1 node in the
        # cluster needs to create the volume and it gets
        # propagated to the peers that were specified
        # during the creation of the shared volume.
        #
        # In summary....dont try to be fancy and call the
        # create method in here or it's going to cause
        # headaches.
        exists, started = await self.shared_volume_exists_and_started()
        if not exists or not started:
            raise CallError(
                'The ctdb shared volume does not exist or '
                'is not started.'
            )

        path = pathlib.Path(CTDBConfig.CTDB_LOCAL_MOUNT.value)
        try:
            # make sure the dirs are there
            path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise CallError(f'{e}')

        # try to mount it
        if not path.is_mount():
            try:
                command = [
                    'mount', '-t', 'glusterfs',
                    'localhost:/' + path.name, path.as_posix(),
                ]
                cp = await run(command)
                if cp.returncode:
                    raise CallError(f'{cp.stderr.decode().strip()}')
            except subprocess.CalledProcessError as e:
                raise CallError(f'{e.stderr.decode().strip()}')

        return 'SUCCESS'

    @accepts()
    @job(lock=JOB_LOCK)
    async def umount(self, job):

        """
        Unmount the locally mounted ctdb shared volume.
        """

        path = pathlib.Path(CTDBConfig.CTDB_LOCAL_MOUNT.value)
        if path.is_mount():
            try:
                cp = await run([
                    'umount', '-R', path.as_posix()
                ])
                if cp.returncode:
                    raise CallError(f'{cp.stderr.decode().strip()}')
            except subprocess.CalledProcessError as e:
                raise CallError(f'{e.stderr.decode().strip()}')

        return 'SUCCESS'
