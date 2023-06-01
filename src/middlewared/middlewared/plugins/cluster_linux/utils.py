import asyncio
import enum
import errno
import os
import shutil
import time
from ipaddress import ip_address

from dns.exception import DNSException

from middlewared.plugins.gluster_linux.utils import GlusterConfig
from middlewared.schema import Bool, returns
from middlewared.service import (Service, ValidationErrors, accepts, job,
                                 private)
from middlewared.service_exception import CallError
from middlewared.utils import MIDDLEWARE_RUN_DIR
from middlewared.utils.path import CLUSTER_PATH_PREFIX


class ClusterUtils(Service):

    class Config:
        namespace = 'cluster.utils'
        cli_namespace = 'service.cluster.utils'

    @accepts()
    @returns(Bool('is_clustered'))
    async def is_clustered(self):
        """
        Returns a boolean value on whether this system is clustered.
        `True` means this system is clustered
        `False` means this system is not clustered.
        """
        return (await self.middleware.call(
            'service.query',
            [('service', '=', 'glusterd')],
            {'get': True, 'extra': {'include_state': False}}
        ))['enable']

    @private
    async def _resolve_hostname(self, host, avail_ips):
        result = {'ip': '', 'error': ''}
        try:
            ip = ip_address(host)
            if ip.is_loopback:
                result['error'] = 'Loopback addresses are not allowed'
            else:
                result['ip'] = ip.compressed
            return result
        except ValueError:
            if host.find('/') != -1:
                # gives a clear(er) error to the caller
                result['error'] = 'Invalid character "/" detected'
                return result
            else:
                # means it's a hostname so we need to try and resolve
                pass

        try:
            ans = [i['address'] for i in await self.middleware.call('dnsclient.forward_lookup', {"names": [host], 'record_types': ['A']})]
        except DNSException as e:
            # failed to resolve the hostname
            result['error'] = e.msg
        else:
            if not ans:
                # this shouldn't happen....but paranoia plagues me
                result['error'] = 'No IP addresses detected'
            elif len(ans) > 1:
                # Duplicate IPs aren't supported anywhere in the cluster stack
                result['error'] = f'Duplicate IPs detected: {", ".join(ans)!r}'
            else:
                result['ip'] = ans[0]

        return result

    @private
    async def resolve_hostnames(self, hostnames):
        """
        Takes a list of hostnames to be asynchronously resolved to their respective IP address.
        """
        hostnames = list(set(hostnames))
        verrors = ValidationErrors()
        avail_ips = await self.middleware.call('gluster.peer.ips_available')
        results = await asyncio.gather(*[self._resolve_hostname(host, avail_ips) for host in hostnames])

        ips = []
        for host, result in zip(hostnames, results):
            if result['error']:
                verrors.add(f'resolve_hostname.{host}', result['error'])
            else:
                ips.append(result['ip'])

        verrors.check()

        return list(set(ips))

    @private
    async def time_callback(self, prefix):
        my_time = time.clock_gettime(time.CLOCK_REALTIME)
        my_node = await self.middleware.call('ctdb.general.pnn')
        key = f'{prefix}_cluster_time_req_{my_node}'
        tz = (await self.middleware.call('datastore.config', 'system.settings'))['stg_timezone']
        try:
            ntp_peer = await self.middleware.call('system.ntpserver.peers', [('active', '=', True)])
        except CallError as e:
            if e.errno != errno.ECONNREFUSED:
                raise

            ntp_peer = None
            self.logger.debug('Failed to determine NTP peers', exc_info=True)

        payload = {
            "clock_realtime": my_time,
            "tz": tz,
            "node": my_node,
            "ntp_peer": ntp_peer[0] if ntp_peer else None
        }
        await self.middleware.call('clustercache.put', key, payload)

    @private
    @job("cluster_time_info")
    async def time_info(self, job):
        nodes = (await self.middleware.call('ctdb.general.status'))['nodemap']['nodes']
        for node in nodes:
            if node['flags_raw'] != 0:
                raise CallError(f'Cluster node {node["pnn"]} is unhealthy. Unable to retrieve time info.')
            if node['this_node']:
                my_node = node['pnn']

        tz = (await self.middleware.call('datastore.config', 'system.settings'))['stg_timezone']

        cl_job = await self.middleware.call('clusterjob.submit', 'cluster.utils.time_callback', my_node)
        ntp_peer = await self.middleware.call('system.ntpserver.peers', [('active', '=', True)])
        my_time = time.clock_gettime(time.CLOCK_REALTIME)
        await cl_job.wait(raise_error=True)

        key_prefix = f'{my_node}_cluster_time_req_'
        responses = []
        for node in nodes:
            if node['this_node']:
                continue

            node_resp = await self.middleware.call('clustercache.pop', f'{key_prefix}{node["pnn"]}')
            responses.append(node_resp)

        responses.append({
            "clock_realtime": my_time,
            "tz": tz,
            "node": my_node,
            "ntp_peer": ntp_peer[0] if ntp_peer else None
        })
        return responses

    @private
    def state_to_be_removed(self):
        """
        This methods purpose is to consolidate the various gluster and ctdb
        files/dirs that must be removed when a cluster is "torn down".
        """
        files = CTDBConfig.CTDB_FILES_TO_REMOVE.value
        dirs = CTDBConfig.CTDB_DIRS_TO_REMOVE.value

        files.extend(GlusterConfig.FILES_TO_REMOVE.value.copy())

        interest = (f'.system/{CTDBConfig.CTDB_VOL_NAME.value}', '.system/glusterd')
        mount_info = self.middleware.call_sync('filesystem.mount_info')
        for i in filter(lambda x: x['mount_source'].endswith(interest), mount_info):
            dirs.append(i['mountpoint'])

        return files, dirs

    @private
    @job(lock='wipe_config', lock_queue_size=1)
    def wipe_config(self, job):
        """
        This can be called on its own after all the gluster volumes
        have been stopped and deleted (including the ctdb shared volume).
        NOTE: this is called by ctdb.shared.volume.teardown to maintain
        backwards compatbility with TrueCommand.
        """
        files, dirs = self.state_to_be_removed()
        for _file in files:
            try:
                os.remove(_file)
            except FileNotFoundError:
                pass
            except Exception:
                self.logger.error('Failed removing %r', _file, exc_info=True)

        for _dir in dirs:
            with os.scandir(_dir) as contents:
                for item in contents:
                    try:
                        shutil.rmtree(item.path) if item.is_dir() else os.remove(item.path)
                    except FileNotFoundError:
                        pass
                    except Exception:
                        self.logger.error('Failed removing %r', item.path, exc_info=True)


class FuseConfig(enum.Enum):
    """
    Various configuration settings used for FUSE mounting
    the gluster volumes locally.
    """
    FUSE_PATH_BASE = '/cluster'
    FUSE_PATH_SUBST = CLUSTER_PATH_PREFIX


class CTDBConfig(enum.Enum):
    """
    Various configuration settings used to configure ctdb.
    """

    # locks used by the create/delete/mount/umount methods
    BASE_LOCK = 'ctdb_'
    MOUNT_UMOUNT_LOCK = BASE_LOCK + 'mount_or_umount_lock'
    CRE_OR_DEL_LOCK = BASE_LOCK + 'create_or_delete_lock'
    PRI_LOCK = BASE_LOCK + 'private_ip_lock'
    PUB_LOCK = BASE_LOCK + 'public_ip_lock'

    # local nodes ctdb related config
    SMB_BASE = '/var/db/system/samba4'
    PER_DB_DIR = os.path.join(SMB_BASE, 'ctdb_persistent')
    STA_DB_DIR = os.path.join(SMB_BASE, 'ctdb_state')

    # local nodes volatile ctdb db directory
    # (keep this on tmpfs for drastic performance improvements)
    VOL_DB_DIR = '/var/run/ctdb/volatile'

    # name of the recovery file used by ctdb cluster nodes
    REC_FILE = '.CTDB-lockfile'

    # name of the file that ctdb uses for the "private" ips of the
    # nodes in the cluster
    PRIVATE_IP_FILE = 'nodes'

    # name of the file that ctdb uses for the "public" ips of the
    # nodes in the cluster
    PUBLIC_IP_FILE = 'public_addresses'

    # name of the file that ctdb uses for the "general" portion
    # of the config
    GENERAL_FILE = 'ctdb.conf'

    # local gluster fuse client mount related config
    LOCAL_MOUNT_BASE = FuseConfig.FUSE_PATH_BASE.value
    CTDB_VOL_NAME = 'ctdb_shared_vol'
    CTDB_VOL_INFO_FILE = f'{MIDDLEWARE_RUN_DIR}/ctdb_vol_info'
    CTDB_LOCAL_MOUNT = os.path.join(LOCAL_MOUNT_BASE, CTDB_VOL_NAME)

    CLUSTERED_SERVICES = '.clustered_services'

    # ctdb etc config
    CTDB_ETC = '/etc/ctdb'
    ETC_GEN_FILE = os.path.join(CTDB_ETC, GENERAL_FILE)
    ETC_REC_FILE = os.path.join(CTDB_ETC, REC_FILE)
    ETC_PRI_IP_FILE = os.path.join(CTDB_ETC, PRIVATE_IP_FILE)
    ETC_PUB_IP_FILE = os.path.join(CTDB_ETC, PUBLIC_IP_FILE)

    # ctdb event scripts directories
    CTDB_ETC_EVENT_SCRIPT_DIR = os.path.join(CTDB_ETC, 'events/legacy')
    CTDB_USR_EVENT_SCRIPT_DIR = '/usr/share/ctdb/events/legacy/'

    # used in the ctdb.shared.volume.teardown method
    CTDB_FILES_TO_REMOVE = [
        ETC_GEN_FILE,
        ETC_REC_FILE,
        ETC_PRI_IP_FILE,
        ETC_PUB_IP_FILE,
    ]

    # used in the ctdb.shared.volume.teardown method
    # ctdb daemon will core dump immediately if someone tears down the cluster
    # and then tries to recreate one without rebooting (the contents of this dir are on tmpfs)
    # ctdb, in this scenario, sees that the files aren't empty and then hits an assert
    CTDB_DIRS_TO_REMOVE = [
        '/var/run/ctdb/',
    ]
