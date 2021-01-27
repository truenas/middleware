import xml.etree.ElementTree as ET
from glustercli.cli import peer

from middlewared.utils import filter_list, run
from middlewared.schema import Dict, Str, Bool
from middlewared.service import (accepts, private, job, filterable,
                                 CallError, CRUDService)
from .utils import GlusterConfig


GLUSTER_JOB_LOCK = GlusterConfig.CLI_LOCK.value


class GlusterPeerService(CRUDService):

    class Config:
        namespace = 'gluster.peer'

    @filterable
    async def query(self, filters=None, options=None):
        peers = []
        if await self.middleware.call('service.started', 'glusterd'):
            peers = await self.middleware.call('gluster.peer.status')
            peers = list(map(lambda i: dict(i, id=i['uuid']), peers))

        return filter_list(peers, filters, options)

    @private
    async def _parse_peer(self, p):
        data = {
            'uuid': p.find('uuid').text,
            'hostname': p.find('hostname').text,
            'connected': p.find('connected').text,
        }

        if data['connected'] == '1':
            data['connected'] = 'Connected'
        else:
            data['connected'] = 'Disconnected'

        return data

    @private
    async def _parse_peer_status_xml(self, data):
        peers = []
        for _ in data.findall('peerStatus/peer'):
            try:
                peers.append(await self._parse_peer(_))
            except Exception as e:
                raise CallError(
                    f'Failed parsing peer information with error: {e}'
                )

        return peers

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

        await self.middleware.call('gluster.method.run', peer.attach, {'args': (data['hostname'],)})
        return await self.middleware.call('gluster.peer.query', [('hostname', '=', data['hostname'])])

    @accepts(Str('id'))
    @job(lock=GLUSTER_JOB_LOCK)
    async def do_delete(self, job, id):
        """
        Remove peer of `id` from the Trusted Storage Pool.

        `id` String representing the uuid of the peer
        """

        await self.middleware.call(
            'gluster.method.run', peer.detach, {'args': ((await self.get_instance(id))['hostname'],)})

    @accepts(Dict(
        'peer_status',
        Bool('localhost', default=True),
    ))
    async def status(self, data):
        """
        List the status of peers in the Trusted Storage Pool.

        `localhost` Boolean if True, include localhost else exclude localhost
        """

        peers = await self.middleware.call('gluster.method.run', peer.status)
        if not data['localhost']:
            return peers

        try:
            remote_node = next(i['hostname'] for i in peers if i['connected'] == 'Connected')
        except StopIteration:
            raise CallError('All remote peers are disconnected.')

        # this is the same as running `gluster.method.run, peer.status` but
        # running it on the `remote_node` so that we can get 2 different
        # "views" of the peers in the TSP.
        command = ['gluster', f'--remote-host={remote_node}', 'peer', 'status', '--xml']
        cp = await run(command, check=False)
        if cp.returncode:
            # the gluster cli utility will return stderr
            # to stdout and vice versa on certain failures.
            # account for this and decode appropriately
            err = cp.stderr if cp.stderr else cp.stdout
            if isinstance(err, bytes):
                err = err.decode()
            raise CallError(
                f'Failed running remote peer status with error: {err.strip()}'
            )

        # build our data structure by parsing the xml
        remote_local_view = ET.fromstring(cp.stdout.decode())
        remote_local_view = await self._parse_peer_status_xml(remote_local_view)

        # this should only ever produce 1 entry
        our_ip = [i for i in remote_local_view if i not in peers]
        if len(our_ip) != 1:
            raise CallError(
                f'Remote peer: {remote_node} sees these peers: {remote_local_view}'
                f'The local peer sees these peers: {peers}.'
                'The local and remote peers should be the same quantity.'
            )

        peers.append(our_ip[0])

        return peers

    @accepts()
    async def ips_available(self):
        """
        Return list of VIP(v4/v6) addresses available on the system
        """

        return [
            d['address'] for d in await self.middleware.call(
                'interface.ip_in_use', {'static': True}
            )
        ]
