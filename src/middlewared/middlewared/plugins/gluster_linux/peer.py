import subprocess
import xml.etree.ElementTree as ET
from glustercli.cli import peer

from middlewared.utils import filter_list
from middlewared.schema import accepts, Bool, Dict, List, Ref, returns, Str
from middlewared.service import private, job, filterable, CallError, CRUDService, ValidationErrors
from middlewared.plugins.cluster_linux.utils import CTDBConfig
from .utils import GlusterConfig


CTDB_VOL = CTDBConfig.CTDB_VOL_NAME.value
GLUSTER_JOB_LOCK = GlusterConfig.CLI_LOCK.value
MAX_PEERS = GlusterConfig.MAX_PEERS.value


class GlusterPeerService(CRUDService):

    class Config:
        namespace = 'gluster.peer'
        cli_namespace = 'service.gluster.peer'

    ENTRY = Dict(
        'gluster_peer_entry',
        Str('id', required=True),
        Str('uuid', required=True),
        Str('hostname', required=True),
        Str('connected', required=True),
        Str('state', required=True),
        Str('status', required=True)
    )

    @filterable
    async def query(self, filters, options):
        peers = []
        if await self.middleware.call('service.started', 'glusterd'):
            peers = await self.middleware.call('gluster.peer.status')
            peers = list(map(lambda i: dict(i, id=i['uuid']), peers))

        return filter_list(peers, filters, options)

    @private
    def parse_peer(self, p):
        data = {
            'uuid': p.find('uuid').text,
            'hostname': p.find('hostname').text,
            'connected': p.find('connected').text,
            'state': p.find('state').text,
            'status': p.find('stateStr').text,
        }

        if data['connected'] == '1':
            data['connected'] = 'Connected'
        else:
            data['connected'] = 'Disconnected'

        return data

    @private
    def parse_peer_status_xml(self, data):
        peers = []
        for _ in data.findall('peerStatus/peer'):
            try:
                peers.append(self.parse_peer(_))
            except Exception as e:
                raise CallError(
                    f'Failed parsing peer information with error: {e}'
                )

        return peers

    @private
    async def common_validation(self, schema):
        # TODO: adding or removing a peer to/from an existing TSP is not supported at
        # this time since it requires expanding the ctdb_shared_vol. This is an
        # involved process and will require proper design/implementation.
        verrors = ValidationErrors()
        if (await self.middleware.call('gluster.volume.exists_and_started', CTDB_VOL))['exists']:
            verbiage = 'Adding to' if schema == 'gluster.peer.create' else 'Removing from'
            verrors.add(schema, f'{verbiage} an existing trusted storage pool is not allowed at this time.')

        if schema == 'gluster.peer.create' and len(await self.query()) == MAX_PEERS:
            verrors.add(schema, 'Maximum number of peers met ({MAX_PEERS})')

        verrors.check()

    @accepts(Dict(
        'peer_create',
        Str('hostname', required=True, max_length=253)
    ))
    @job(lock=GLUSTER_JOB_LOCK)
    async def do_create(self, job, data):
        """
        Add peer to the Trusted Storage Pool.

        `hostname` String representing an IP(v4/v6) address or DNS name
        """
        await self.middleware.call('gluster.peer.common_validation', 'gluster.peer.create')

        # we need to verify that we can resolve the hostname to an IP address
        # or clustering, in general, is going to fail in spectacular ways
        await self.middleware.call('cluster.utils.resolve_hostnames', [data['hostname']])

        await self.middleware.call('gluster.method.run', peer.attach, {'args': (data['hostname'],)})
        return await self.middleware.call('gluster.peer.query', [('hostname', '=', data['hostname'])])

    @accepts(Str('id'))
    @returns()
    @job(lock=GLUSTER_JOB_LOCK)
    async def do_delete(self, job, id):
        """
        Remove peer of `id` from the Trusted Storage Pool.

        `id` String representing the uuid of the peer
        """
        await self.middleware.call('gluster.peer.common_validation', 'gluster.peer.delete')

        await self.middleware.call(
            'gluster.method.run', peer.detach, {'args': ((await self.get_instance(id))['hostname'],)})

    @accepts(Dict(
        'peer_status',
        Bool('localhost', default=True),
    ))
    @returns(List('peers', items=[Ref('gluster_peer_entry')]))
    def status(self, data):
        """
        List the status of peers in the Trusted Storage Pool.

        `localhost` Boolean if True, include localhost else exclude localhost
        """

        raw_xml = subprocess.run(
            ['gluster', 'peer', 'status', '--xml'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        if raw_xml.returncode:
            # the gluster cli utility will return stderr
            # to stdout and vice versa on certain failures.
            # account for this
            err = raw_xml.stderr if raw_xml.stderr else raw_xml.stdout
            raise CallError(f'Failed to run gluster peer status locally: {err.strip()}')

        local_peers = ET.fromstring(raw_xml.stdout)
        local_peers = self.parse_peer_status_xml(local_peers)
        if not data['localhost']:
            return local_peers

        rem_node = None
        for i in local_peers:
            # gluster has _very_ deceiving statuses for a peer
            # being a part of the cluster, being connected, and
            # being "healthy"
            state = i['state'] == '3'
            conn = i['connected'] == 'Connected'
            status = i['status'] == 'Peer in Cluster'
            healthy = state & conn & status
            if healthy:
                rem_node = i['hostname']
                break

        if rem_node is None:
            # this means that all the peers in the cluster are
            # "Disconnected" or "Peer Rejected" so return early
            # here since running the command on a remote peer
            # will produce no output
            return local_peers

        # this is the same as running `raw_xml` subprocess above but
        # running it on the `rem_node` so that we can get 2 different
        # "views" of the peers in the TSP.
        command = ['gluster', f'--remote-host={rem_node}', 'peer', 'status', '--xml']
        cp = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        if cp.returncode:
            # the gluster cli utility will return stderr
            # to stdout and vice versa on certain failures.
            # account for this
            err = cp.stderr if cp.stderr else cp.stdout
            raise CallError(f'Failed running remote peer status with error: {err.strip()}')

        rem_peers = ET.fromstring(cp.stdout)
        rem_peers = self.parse_peer_status_xml(rem_peers)

        local_peers.extend([i for i in rem_peers if i not in local_peers])

        return local_peers

    @accepts()
    @returns(List('ips', items=[Str('address', required=True)]))
    async def ips_available(self):
        """
        Return list of VIP(v4/v6) addresses available on the system
        """
        return [d['address'] for d in await self.middleware.call('interface.ip_in_use', {'static': True})]

    @accepts(Dict(
        'init_as_replacement',
        Str('zpool', required=True),
        Str('gvol', required=True),
    ))
    @private
    @job(lock='init_lock')
    async def initialize_as_replacement(self, job, data):
        """
        Initialize this peer as a node that will be replacing another
        node in a cluster. It is expected that this is called explicitly
        by end-user.
        `zpool` str: the name of the zpool on this node to create the brick
            ---must match the zpool name of the node that is being replaced
        `gvol` str: the name of the gluster volume
            ---must match the gluster volume name of the node that is being
                replaced
        """
        hiearchy = f'{data["zpool"]}/.glusterfs/{data["gvol"]}/brick0'
        info = {
            'name': hiearchy,
            'type': 'FILESYSTEM',
            'create_ancestors': True,
            'properties': {'acltype': 'posix'}
        }
        self.middleware.call_sync('zfs.dataset.create', info)
        self.middleware.call_sync('zfs.dataset.mount', hiearchy)
