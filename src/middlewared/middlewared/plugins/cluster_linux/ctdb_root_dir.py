import errno
import json
import os

from pathlib import Path
from pyglfs import GLFSError
from time import sleep
from uuid import uuid4

from middlewared.service import accepts, Service, CallError, job
from middlewared.schema import Bool, Dict, Int, IPAddr, List, Ref, returns, Str
from middlewared.plugins.cluster_linux.utils import CTDBConfig, FuseConfig
from middlewared.plugins.gluster_linux.utils import get_parsed_glusterd_uuid as get_glusterd_uuid
from middlewared.validators import UUID


MOUNT_UMOUNT_LOCK = CTDBConfig.MOUNT_UMOUNT_LOCK.value
CRE_OR_DEL_LOCK = CTDBConfig.CRE_OR_DEL_LOCK.value
LEGACY_CTDB_VOL_NAME = CTDBConfig.LEGACY_CTDB_VOL_NAME.value
CTDB_VOL_INFO_FILE = CTDBConfig.CTDB_VOL_INFO_FILE.value
CTDB_STATE_DIR = CTDBConfig.CTDB_STATE_DIR.value
MIGRATION_WAIT_TIME = 300


class CtdbRootDirService(Service):

    class Config:
        namespace = 'ctdb.root_dir'
        private = True

    def __get_vol_and_path(self):
        """
        Internal method that determines the gluster volume, path, and
        glfs UUID of the directory holding our clustered state directory.
        """
        vol_names = self.middleware.call_sync('gluster.volume.list')
        if LEGACY_CTDB_VOL_NAME in vol_names:
            self.logger.error(
                'Legacy ctdb_shared_vol is present in gluster volume list. '
                'If this log entry is generated post-deployment, it indicates '
                'that an unsupported upgrade from legacy cluster configuration '
                'was performed.'
            )
            try:
                uuid = self.middleware.call_sync('gluster.filesystem.lookup', {
                    'volume_name': LEGACY_CTDB_VOL_NAME,
                    'path': '.DEPRECATED'
                })['uuid']
            except GLFSError as e:
                if e.errno != errno.ENOENT:
                    raise CallError(
                        'Failed to lookup DEPRECATED sentinel for legacy CTDB '
                        f'shared volume: {e.errmsg}', e.errno
                    )

                # root of glusterfs volume always has uuid of 1
                return {
                    'volume': LEGACY_CTDB_VOL_NAME,
                    'system_dir': '/',
                    'uuid': '00000000-0000-0000-0000-000000000001'
                }

        for vol in vol_names:
            if vol == LEGACY_CTDB_VOL_NAME:
                continue

            try:
                uuid = self.middleware.call_sync('gluster.filesystem.lookup', {
                    'volume_name': vol,
                    'path': CTDB_STATE_DIR
                })['uuid']
            except GLFSError as e:
                if e.errno != errno.ENOENT:
                    raise CallError(
                        'Failed to lookup truenas cluster state dir on '
                        f'volume [{vol}]: {e.errmsg}', e.errno
                    )

                continue

            return {
                'volume': vol,
                'system_dir': CTDB_STATE_DIR,
                'uuid': uuid
            }

        if vol_names:
            """
            This code path will be followed when we create our first gluster volume.
            It ensures that we have a valid clustered system directory available.
            """
            try:
                uuid = self.middleware.call_sync('gluster.filesystem.mkdir', {
                    'volume_name': vol_names[0],
                    'path': CTDB_STATE_DIR,
                    'options': {'mode': 0o700},
                })['uuid']
            except Exception:
                self.logger.error('Failed to create clustered system directory', exc_info=True)
                pass
            else:
                return {
                    'volume': vol_names[0],
                    'system_dir': CTDB_STATE_DIR,
                    'uuid': uuid
                }

        # Legacy versions of TrueCommand would manually call ctdb.shared.volume.create in
        # order to create a dedicated gluster volume for our ctdb configuration. Since this
        # has been deprecated it means that an older version of TrueCommand may fall through
        # to here.
        raise CallError(
            "No clustered state directory configured. This may indicate that a legacy version "
            "of TrueCommand is being used to create the cluster. If this is the case, then "
            "please update to the latest stable version of TrueCommand in order to cleanly build "
            "a new TrueNAS SCALE cluster.",
            errno.ENOENT
        )

    def generate_info(self):
        """
        This method writes a local configuration file that contains
        configuration information about the clustered system directory.
        It is used within middleware and also ctdb event scripts and the
        ctdb recovery lock helper to determine the correct volume and
        path to use.
        """
        conf = self.__get_vol_and_path()

        volume = conf['volume']
        volume_mp = Path(FuseConfig.FUSE_PATH_BASE.value, volume)
        system_dir = conf['system_dir']
        data = {
            'volume_name': volume,
            'volume_mountpoint': str(volume_mp),
            'path': system_dir,
            'mountpoint': str(Path(f'{volume_mp}/{system_dir}')),
            'uuid': conf['uuid']
        }

        tmp_name = f'{CTDB_VOL_INFO_FILE}_{uuid4().hex}.tmp'
        with open(tmp_name, "w") as f:
            f.write(json.dumps(data))
            f.flush()
            os.fsync(f.fileno())

        os.rename(tmp_name, CTDB_VOL_INFO_FILE)
        return data

    @accepts()
    @returns(Dict(
        'root_dir_config',
        Str('volume_name'),
        Str('volume_mountpoint'),
        Str('path'),
        Str('mountpoint'),
        Str('uuid'),
        register=True
    ))
    def config(self):
        info_file = Path(CTDB_VOL_INFO_FILE)
        try:
            return json.loads(info_file.read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            return self.generate_info()

    @job(lock="ctdb_system_volume_update")
    def update(self, job, data):
        """
        update is performed under lock to serialize update ops
        and grant more visibility via jobs queue. ctdb service start
        will wait for any pending update jobs to complete before actually
        starting the service.
        """
        volume = data['name']
        uuid = data['uuid']
        info = self.middleware.call_sync('gluster.volume.exists_and_started', volume)
        if not info['exists']:
            raise CallError(
                f'{volume}: volume does not exist', errno.ENOENT
            )

        if not info['started']:
            self.middleware.call_sync('gluster.volume.start', {'name': volume})

        if self.middleware.call_sync('service.started', 'ctdb'):
            raise CallError(
                'Updates to TrueNAS clustered metadata volume are not '
                'permitted when the ctdb service is started'
            )

        node_uuid = get_glusterd_uuid()
        try:
            self.middleware.call_sync('gluster.filesystem.unlink', {
                'volume_name': volume,
                'parent_uuid': uuid,
                'path': f'.{node_uuid}_UPDATE_IN_PROGRESS'
            })
        except Exception:
            self.logger.warning('Failed to unlink in-progress sentinel', exc_info=True)

        return self.generate_info()

    def __move_ctdb_vol(self, data):
        # do not call this method directly
        try:
            current = self.config()
        except CallError as e:
            if e.errno != errno.ENOENT:
                raise

            self.logger.debug("Failed to detect metadata dir.", exc_info=True)
            current = {'volume_name': None}

        # If we're not moving the location, just make sure our vol file
        # is present
        if current['volume_name'] == data['name']:
            try:
                hdl = self.middleware.call_sync('gluster.filesystem.lookup', {
                    'volume_name': current['volume_name'],
                    'path': current['path']
                })
            except GLFSError as e:
                if e.errno != errno.ENOENT:
                    raise CallError(
                        'Failed to lookup truenas cluster state dir '
                        f'[{current["path"]}] on volume '
                        f'[{current["volume_name"]}]: {e.errmsg}', e.errno
                    )

                hdl = self.middleware.call_sync('gluster.filesystem.mkdir', {
                    'volume_name': current['volume_name'],
                    'path': current['path'],
                    'options': {'mode': 0o700}
                })

            return hdl['uuid']

        elif current['volume_name'] is None:
            hdl = self.middleware.call_sync('gluster.filesystem.mkdir', {
                'volume_name': data['name'],
                'path': CTDB_STATE_DIR,
                'options': {'mode': 0o700}
            })
            return hdl['uuid']

        src_uuid = self.middleware.call_sync('gluster.filesystem.lookup', {
            'volume_name': current['volume_name'],
            'path': current['path']
        })['uuid']

        try:
            dst_uuid = self.middleware.call_sync('gluster.filesystem.lookup', {
                'volume_name': data['name'],
                'path': CTDB_STATE_DIR
            })['uuid']
        except GLFSError as e:
            if e.errno != errno.ENOENT:
                raise

            dst_uuid = self.middleware.call_sync('gluster.filesystem.mkdir', {
                'volume_name': data['name'],
                'path': CTDB_STATE_DIR,
                'options': {'mode': 0o700}
            })['uuid']

        move_job = self.middleware.call_sync('gluster.filesystem.copy_tree', {
            'src_volume_name': current['volume_name'],
            'src_uuid': src_uuid,
            'dst_volume_name': data['name'],
            'dst_uuid': dst_uuid,
            'force': True,
        })
        move_job.wait_sync(raise_error=True)

        rmtree_job = self.middleware.call_sync('gluster.filesystem.rmtree', {
            'volume_name': current['volume_name'],
            'path': current['path']
        })
        rmtree_job.wait_sync()

        # If we've moved away from existing ctdb_shared_vol
        # then set sentinel file indicating it must be skipped.
        if current['volume_name'] == LEGACY_CTDB_VOL_NAME:
            self.middleware.call_sync('gluster.filesystem.create_file', {
                'volume_name': current['volume_name'],
                'path': '.DEPRECATED',
                'options': {'mode': 0o700}
            })

        return dst_uuid

    @job(lock=CRE_OR_DEL_LOCK)
    def migrate(self, job, data):
        """
        WARNING: this method will cause production outage for the entire cluster
        and _must_ only be performed during a maintenance window.

        Within this method we maintain sentinel files indicating that an update
        is in progress. The clustercache plugin may _not_ be used as the cluster
        will be in a degraded state while we move the system files.
        """

        self.logger.debug("Beginning migration to volume %s", data['name'])
        job.set_progress(0, f'Begining migration of cluster system config to {data["name"]} volume')
        if not self.middleware.call_sync('ctdb.general.healthy'):
            raise CallError(
                'CTDB volume configuration may only be initiated with healthy cluster'
            )

        cur_info = self.config()
        job.set_progress(10, f'Begining migration of cluster system config from {cur_info["volume_name"]} to {data["name"]}')
        contents = self.middleware.call_sync('gluster.filesystem.contents', {
            'volume_name': cur_info['volume_name'],
            'uuid': cur_info['uuid'],
        })

        for file in contents:
            if file.endswith('_UPDATE_IN_PROGRESS'):
                peer_uuid = file.strip('_UPDATE_IN_PROGRESS')
                raise CallError(
                    f'{peer_uuid[1:]}: Gluster peer currently in process '
                    'of updating system volume path', errno.EBUSY
                )

        job.set_progress(25, 'Stopping CTDB service on all nodes')

        # We must stop ctdbd fist (will fault cluster)
        self.middleware.call_sync('gluster.localevents.send', {
            'event': 'CTDB_STOP',
            'name': data['name'],
            'forward': True
        })

        # By this point ctdbd is stopped on all nodes
        #
        # The following moves our nodes file and every other
        # ctdb / cluster-config related file to the new volume
        # then removes the originals
        job.set_progress(50, 'Moving system files')
        dst_uuid = self.__move_ctdb_vol(data)

        # Set the sentinel files that will be removed as each node
        # processes the SYSTEM_VOL_CHANGE event. Presence of sentinel
        # means that the cluster node has not finished processing.
        job.set_progress(60, 'Setting update sentinels')
        for peer in self.middleware.call_sync('gluster.peer.query'):
            try:
                self.middleware.call_sync('gluster.filesystem.create_file', {
                    'volume_name': data['name'],
                    'parent_uuid': dst_uuid,
                    'path': f'.{peer["uuid"]}_UPDATE_IN_PROGRESS'
                })
            except Exception:
                # We're already pretty heavily commited at this point
                # and so we'll just hope for the best that things shake out
                # okay.
                self.logger.warning(
                    'Failed to generate sentinel for node %s',
                    peer['hostname'], exc_info=True
                )

        # The event kicks off backgrounded change
        job.set_progress(75, 'Sending command to remote nodes to update config')
        self.middleware.call_sync('gluster.localevents.send', {
            'event': 'SYSTEM_VOL_CHANGE',
            'name': data['name'],
            'uuid': dst_uuid,
            'forward': True
        })

        # The cluster update is a backgrounded job, and may take a small
        # amount of time to complete.
        remaining = MIGRATION_WAIT_TIME
        while remaining > 0:
            contents = self.middleware.call_sync('gluster.filesystem.contents', {
                'volume_name': data['name'],
                'uuid': dst_uuid,
            })
            wait_for_nodes = []
            for file_name in contents:
                if not file_name.endswith('_UPDATE_IN_PROGRESS'):
                    continue

                peer_uuid = file_name.strip('_UPDATE_IN_PROGRESS')
                wait_for_nodes.append(peer_uuid[1:])

            if not wait_for_nodes:
                break

            job.set_progress(80, f'Waiting for peers [{", ".join(wait_for_nodes)}] to finish update.')
            sleep(1)
            remaining -= 1

        # This validates our nodes file and starts ctdb
        job.set_progress(90, 'Finalizing setup')
        self.middleware.call_sync('ctdb.root_dir.setup')

        # It may take up to a few minutes for ctdb to become healthy again
        remaining = MIGRATION_WAIT_TIME
        while remaining > 0:
            status = self.middleware.call_sync('ctdb.general.status')
            if status['all_healthy']:
                break

            job.set_progress(95, 'Waiting for CTDB to become healthy.')
            sleep(1)
            remaining -= 1

        if remaining == 0:
            # This may not necessarily be fatal. Adminstrative action may be required
            # to unban a node.
            self.logger.error("Timed out waiting for CTDB to become healthy post-move")

    async def validate(self, ctdb_vol_name):
        filters = [('id', '=', ctdb_vol_name)]
        ctdb = await self.middleware.call('gluster.volume.query', filters)
        if not ctdb:
            # it's expected that ctdb shared volume exists when
            # calling this method
            raise CallError(f'{ctdb_vol_name} does not exist', errno.ENOENT)

        # This should generate alert rather than exception
        if ctdb[0]['type'] == 'DISTRIBUTE':
            msg = (
                f'{ctdb_vol_name}: volume hosting cluster system files is '
                'configured as DISTRIBUTE type. Lack of redundancy for this volume '
                'means that failure of single node will result in total production '
                'outage.'
            )
            await self.middleware.call(
                'alert.oneshot_create',
                'ClusteredConfigRedundancy',
                {'errmsg': msg}
            )
        else:
            await self.middleware.call('alert.oneshot_delete', 'ClusteredConfigRedundancy', None)

    @accepts(Dict(
        'ctdb_nodes_update',
        List('new_nodes', items=[
            Dict(
                'ctdb_node_info',
                IPAddr('ip', required=True),
                Str('node_uuid', validators=[UUID()], required=True),
            )
        ], unique=True)
    ))
    @returns(Dict(
        'ctdb_configuration',
        Ref('root_dir_config'),
        List('private_ips', items=[
            Dict(
                'ctdb_private_ip',
                Int('id'),
                Int('pnn'),
                Str('address'),
                Bool('enabled'),
                Bool('this_node'),
                Str('node_uuid')
            )
        ]),
        register=True
    ))
    @job(lock=CRE_OR_DEL_LOCK)
    async def setup(self, job, data):
        """
        Configure the gluster volume that houses CTDB configuration.
        This may be called in the following situations:

        1) When the cluster is initially created this method is called by
        cluster.management.cluster_create with a payload containing
        `ctdb_node_info` for all proposed cluster nodes.

        2) When new cluster node is added. In this case the list of
        `ctdb_node_info` will only contain information for the new node.

        3) After the volume containing CTDB configuration details has moved.
        In this case the `ctdb_node_info` list will be empty.

        Each list entry contains the following items:

        `ip` - private IP address of the node to be added

        `node_uuid` - gluster peer UUID associated with the IP address

        This method ensures the following:
        a) we have a valid system volume information file (ctdb.root_dir.config)
        b) the volume specified in file (a) is started and mounted
        c) validates that we have 1-1 ratio of gluster peers to nodes file entries
        """
        config = await self.middleware.call('ctdb.root_dir.config')
        vol = config['volume_name']
        info = await self.middleware.call('gluster.volume.exists_and_started', vol)
        ip_info = data.get('new_nodes', {})

        # make sure the shared volume is configured properly to prevent
        # possibility of split-brain/data corruption with ctdb service
        await self.middleware.call('ctdb.root_dir.validate', vol)

        if not info['started']:
            # start it if we get here
            await self.middleware.call('gluster.volume.start', {'name': vol})

        # try to mount it locally and send a request
        # to all the other peers in the TSP to also
        # FUSE mount it
        await self.middleware.call('gluster.localevents.send', {
            'event': 'VOLUME_START', 'name': vol, 'forward': True
        })

        # we need to wait on the local FUSE mount job since
        # ctdb daemon config is dependent on it being mounted
        fuse_mount_job = await self.middleware.call('core.get_jobs', [
            ('method', '=', 'gluster.fuse.mount'),
            ('arguments.0.name', '=', vol),
            ('state', '=', 'RUNNING')
        ])
        if fuse_mount_job:
            wait_id = await self.middleware.call('core.job_wait', fuse_mount_job[0]['id'])
            await wait_id.wait()

        # Setup the ctdb daemon config. Without ctdb daemon running, none of the
        # sharing services (smb/nfs) will work in an active-active setting.
        priv_ctdb_ips = await self.middleware.call('ctdb.private.ips.query')
        gluster_peers = await self.middleware.call('gluster.peer.query')
        private_ips_nodes_uuid = set([x['node_uuid'] for x in priv_ctdb_ips])
        gluster_peers_uuid = set([x['uuid'] for x in gluster_peers])

        if not ip_info and not priv_ctdb_ips:
            raise CallError(
                'No private IPs were specified in payload and no private IPs are currently '
                'set within the CTDB system directory.'
            )
        elif not ip_info:
            private_ips_nodes_uuid = set([x['node_uuid'] for x in priv_ctdb_ips])
            gluster_peers_uuid = set([x['uuid'] for x in gluster_peers])

            if (missing := gluster_peers_uuid - private_ips_nodes_uuid):
                raise CallError(
                    'No private IP information has been configured for following '
                    f'gluster nodes: {", ".join(missing)}'
                )
        else:
            ip_info_uuids = set([x['node_uuid'] for x in ip_info])

            if (overlap := ip_info_uuids & private_ips_nodes_uuid):
                raise CallError(
                    f'Private IP entries already exist for the following gluster peer(s): {", ".join(overlap)}'
                )

            if (missing := gluster_peers_uuid - (ip_info_uuids | private_ips_nodes_uuid)):
                raise CallError(
                    f'No private IP was specified for the following gluster peer(s): {", ".join(missing)}'
                )

        for entry in ip_info:
            ip_add_job = await self.middleware.call('ctdb.private.ips.create', entry)
            try:
                await ip_add_job.wait(raise_error=True)
            except CallError as e:
                if e.errno == errno.EEXIST:
                    # This private IP has already been added. We can safely continue.
                    continue

                raise

        # this sends an event telling all peers in the TSP (including this system)
        # to start the ctdb service
        data = {'event': 'CTDB_START', 'name': vol, 'forward': True}
        await self.middleware.call('gluster.localevents.send', data)

        if ip_info:
            # If we changed the nodes files here, then issue command to all nodes
            # to reload the file
            await self.middleware.call('ctdb.private.ips.reload')

        final_ips = await self.middleware.call('ctdb.private.ips.query')
        return {'root_dir_config': config, 'private_ips': final_ips}

    @job(lock=CRE_OR_DEL_LOCK)
    async def teardown(self, job, force=False):
        """
        If this method is called, it's expected that the end-user knows what they're doing. They
        also expect that this will _PERMANENTLY_ delete all the ctdb configuration information. We
        also disable the glusterd service since that's what SMB service uses to determine if the
        system is in a "clustered" state. This method _MUST_ be called on each node in the cluster
        to fully "teardown" the cluster config.

        `force`: boolean, when True will forcefully stop all relevant cluster services before
            wiping the configuration.

        NOTE: THERE IS NO COMING BACK FROM THIS.
        """
        config = await self.middleware.call('ctdb.root_dir.config')
        if not force:
            for vol in await self.middleware.call('gluster.volume.query'):
                if vol['name'] != config['volume_name']:
                    # If someone calls this method, we expect that all other gluster volumes
                    # have been destroyed
                    raise CallError(f'{vol["name"]!r} must be removed before deleting {config["volume_name"]!r}')
        else:
            # we have to stop gluster service because it spawns a bunch of child processes
            # for the ctdb shared volume. This also stops ctdb, smb and unmounts all the
            # FUSE mountpoints.
            job.set_progress(50, 'Stopping cluster services')
            await self.middleware.call('service.stop', 'glusterd')

        job.set_progress(75, 'Removing cluster related configuration files and directories.')
        wipe_config_job = await self.middleware.call('cluster.utils.wipe_config')
        await wipe_config_job.wait()

        job.set_progress(99, 'Disabling cluster service')
        await self.middleware.call('service.update', 'glusterd', {'enable': False})
        await self.middleware.call('smb.reset_smb_ha_mode')

        job.set_progress(100, 'CTDB root directory teardown complete.')
