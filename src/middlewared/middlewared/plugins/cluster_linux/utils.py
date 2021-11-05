import os
import asyncio
import enum
import time
from ipaddress import ip_address
from dns import asyncresolver

from middlewared.service import Service, job, ValidationErrors
from middlewared.service_exception import CallError


class ClusterUtils(Service):
    class Config:
        namespace = 'cluster.utils'
        private = True

    async def _resolve_hostname(self, hostname):
        try:
            ip = ip_address(hostname)
            # we will return the IP address so long as it's not loopback address
            # else we'll return an empty list so that the caller of this raises
            # a validation error
            return [ip.compressed] if not ip.is_loopback else []
        except ValueError:
            # means it's a hostname so we need to try and resolve
            pass

        lifetime = 6  # total amount of time to try and resolve `hostname`
        timeout = lifetime // 3  # time to wait before moving on to next entry in resolv.conf

        ar = asyncresolver.Resolver()
        ar.lifetime = lifetime
        ar.timeout = timeout

        try:
            ans = [i.to_text() for i in (await ar.resolve(hostname)).response.answer[0].items]
        except Exception:
            ans = []

        # check the resolved IP addresses to make sure they're not loopback addresses
        # idk...shouldn't happen but be sure
        for ip in ans[:]:
            if ip_address(ip).is_loopback:
                ans.remove(ip)

        return ans

    async def resolve_hostnames(self, hostnames):
        """
        Takes a list of hostnames to be asynchronously resolved to their respective IP address.
        """
        hostnames = list(set(hostnames))
        verrors = ValidationErrors()

        results = await asyncio.gather(*[self._resolve_hostname(host) for host in hostnames])

        ips = []
        for host, result in zip(hostnames, results):
            if not result:
                verrors.add(f'resolve_hostname.{host}', 'Failed to resolve hostname')
            else:
                ips.extend(result)

        # if any hostnames failed to be resolved it will be raised here
        verrors.check()

        return list(set(ips))

    async def time_callback(self, prefix):
        my_time = time.clock_gettime(time.CLOCK_REALTIME)
        my_node = await self.middleware.call('ctdb.general.pnn')
        key = f'{prefix}_cluster_time_req_{my_node}'
        tz = (await self.middleware.call('datastore.config', 'system.settings'))['stg_timezone']
        ntp_peer = await self.middleware.call('system.ntpserver.peers', [('status', '$', 'PEER')])
        payload = {
            "clock_realtime": my_time,
            "tz": tz,
            "node": my_node,
            "ntp_peer": ntp_peer[0] if ntp_peer else None
        }
        await self.middleware.call('clustercache.put', key, payload)

    @job("cluster_time_info")
    async def time_info(self, job):
        nodes = await self.middleware.call('ctdb.general.status')
        for node in nodes:
            if not node['flags_str'] == 'OK':
                raise CallError(f'Cluster node {node["pnn"]} is unhealthy. Unable to retrieve time info.')
            if node['this_node']:
                my_node = node['pnn']

        tz = (await self.middleware.call('datastore.config', 'system.settings'))['stg_timezone']

        cl_job = await self.middleware.call('clusterjob.submit', 'cluster.utils.time_callback', my_node)
        ntp_peer = await self.middleware.call('system.ntpserver.peers', [('status', '$', 'PEER')])
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


class FuseConfig(enum.Enum):
    """
    Various configuration settings used for FUSE mounting
    the gluster volumes locally.
    """
    FUSE_PATH_BASE = '/cluster'
    FUSE_PATH_SUBST = 'CLUSTER:'


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
    CTDB_LOCAL_MOUNT = os.path.join(LOCAL_MOUNT_BASE, CTDB_VOL_NAME)
    GM_RECOVERY_FILE = os.path.join(CTDB_LOCAL_MOUNT, REC_FILE)
    GM_PRI_IP_FILE = os.path.join(CTDB_LOCAL_MOUNT, PRIVATE_IP_FILE)
    GM_PUB_IP_FILE = os.path.join(CTDB_LOCAL_MOUNT, PUBLIC_IP_FILE)

    # ctdb etc config
    CTDB_ETC = '/etc/ctdb'
    ETC_GEN_FILE = os.path.join(CTDB_ETC, GENERAL_FILE)
    ETC_REC_FILE = os.path.join(CTDB_ETC, REC_FILE)
    ETC_PRI_IP_FILE = os.path.join(CTDB_ETC, PRIVATE_IP_FILE)
    ETC_PUB_IP_FILE = os.path.join(CTDB_ETC, PUBLIC_IP_FILE)

    # ctdb event scripts directories
    CTDB_ETC_EVENT_SCRIPT_DIR = os.path.join(CTDB_ETC, 'events/legacy')
    CTDB_USR_EVENT_SCRIPT_DIR = '/usr/share/ctdb/events/legacy/'
