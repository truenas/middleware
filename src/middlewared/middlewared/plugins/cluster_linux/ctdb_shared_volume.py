from middlewared.service import Service, CallError, accepts, private, job
from middlewared.plugins.cluster_linux.utils import CTDBConfig
from middlewared.plugins.gluster_linux.utils import run_method
from glustercli.cli import volume

import os
import pathlib
import subprocess


MOUNT_UMOUNT_LOCK = CTDBConfig.MOUNT_UMOUNT_LOCK.value
CRE_OR_DEL_LOCK = CTDBConfig.CRE_OR_DEL_LOCK.value
CTDB_VOL_NAME = CTDBConfig.CTDB_VOL_NAME.value
CTDB_LOCAL_MOUNT = CTDBConfig.CTDB_LOCAL_MOUNT.value


class CtdbSharedVolumeService(Service):

    class Config:
        namespace = 'ctdb.shared.volume'

    @private
    def construct_gluster_volume_create_data(self, peers):

        payload = {}

        # get the system dataset location
        ctdb_sysds_path = self.middleware.call_sync('systemdataset.config')['path']
        ctdb_sysds_path = os.path.join(ctdb_sysds_path, CTDB_VOL_NAME)

        bricks = []
        for i in peers:
            peer = i
            path = ctdb_sysds_path
            brick = peer + ':' + path
            bricks.append(brick)

        payload = {
            'bricks': bricks,
            'replica': len(peers),
            'force': True,
        }

        return payload

    @private
    def shared_volume_exists_and_started(self):

        exists = started = False
        rv = {'volname': CTDB_VOL_NAME, 'group_subvols': True}
        if vol := run_method(volume.status_detail, **rv):
            if vol[0]['type'] != 'REPLICATE':
                raise CallError(
                    f'A volume with the name "{CTDB_VOL_NAME}" already exists '
                    'but is not a REPLICATE type volume. Please delete or rename '
                    'this volume and try again.'
                )
            elif vol[0]['replica'] < 3 or vol[0]['num_bricks'] < 3:
                raise CallError(
                    f'A volume with the name "{CTDB_VOL_NAME}" already exists '
                    'but is configured in a way that could cause split-brain. '
                    'Please delete or rename this volume and try again.'
                )
            elif vol[0]['status'] != 'Started':
                exists = True
                run_method(volume.start, CTDB_VOL_NAME)
                started = True
            else:
                exists = started = True

        return exists, started

    @accepts()
    @job(lock=CRE_OR_DEL_LOCK)
    def create(self, job):
        """
        Create and mount the shared volume to be used
        by ctdb daemon.
        """

        # check if ctdb shared volume already exists and started
        exists, started = self.shared_volume_exists_and_started()
        if exists and started:
            return

        if not exists:
            # get the peers in the TSP
            peers = self.middleware.call_sync('gluster.peer.pool')
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

            # create the ctdb shared volume
            req = self.construct_gluster_volume_create_data(con_peers)
            run_method(volume.create, CTDB_VOL_NAME, req.pop('bricks'), **req)

        if not started:
            # start it if we get here
            run_method(volume.start, CTDB_VOL_NAME)

        # try to mount it locally
        mount_job = self.middleware.call_sync('ctdb.shared.volume.mount')
        mount_job.wait_sync(raise_error=True)

        return 'SUCCESS'

    @accepts()
    @job(lock=CRE_OR_DEL_LOCK)
    def delete(self, job):
        """
        Delete and unmount the shared volume used by ctdb daemon.
        """

        # nothing to delete if it doesn't exist
        exists, started = self.shared_volume_exists_and_started()
        if not exists:
            return

        # umount it first
        umount_job = self.middleware.call_sync('ctdb.shared.volume.umount')
        umount_job.wait_sync(raise_error=True)

        if started:
            # stop the volume
            force = {'force': True}
            run_method(volume.stop, CTDB_VOL_NAME, **force)

        # now delete it
        run_method(volume.delete, CTDB_VOL_NAME)

        return 'SUCCESS'

    @accepts()
    @job(lock=MOUNT_UMOUNT_LOCK)
    def mount(self, job):
        """
        Mount the ctdb shared volume locally.
        """

        mounted = False

        # if you try to mount without the service being started,
        # the mount utility simply returns a msg to stderr stating
        # "Mounting glusterfs on /cluster/ctdb_shared_vol failed" which is
        # expected since the service isn't running
        if not self.middleware.call_sync('service.started', 'glusterd'):
            self.logger.warning('The "glusterd" service is not running. Not mounting.')
            return mounted

        try:
            # make sure the dirs are there
            pathlib.Path(CTDB_LOCAL_MOUNT).mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise CallError(f'Failed creating directory with error: {e}')

        cmd = ['mount', '-t', 'glusterfs', 'localhost:/' + CTDB_VOL_NAME, CTDB_LOCAL_MOUNT]
        cp = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if cp.returncode:
            if b'is already mounted' in cp.stderr:
                mounted = True
            else:
                errmsg = cp.stderr.decode().strip()
                self.logger.error(f'Failed to mount {CTDB_LOCAL_MOUNT} with error: {errmsg}')
        else:
            mounted = True

        return mounted

    @accepts()
    @job(lock=MOUNT_UMOUNT_LOCK)
    def umount(self, job):
        """
        Unmount the locally mounted ctdb shared volume.
        """

        umounted = False

        cmd = ['umount', '-R', CTDB_LOCAL_MOUNT]
        cp = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if cp.returncode:
            if b'not mounted' in cp.stderr:
                umounted = True
            else:
                errmsg = cp.stderr.decode().strip()
                self.logger.error(f'Failed to umount {CTDB_LOCAL_MOUNT} with error: {errmsg}')
        else:
            umounted = True

        return umounted
