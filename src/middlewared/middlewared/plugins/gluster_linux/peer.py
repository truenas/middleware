from glustercli.cli import peer
from middlewared.async_validators import resolve_hostname
from middlewared.schema import Dict, Str
from middlewared.service import (accepts, private, job,
                                 CallError, Service,
                                 ValidationErrors)
from .utils import GlusterConfig, run_method

import subprocess
import xml.etree.ElementTree as ET


GLUSTER_JOB_LOCK = GlusterConfig.CLI_LOCK.value


class GlusterPeerService(Service):

    class Config:
        namespace = 'gluster.peer'

    @private
    def _parse_peer(self, p):

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
    def _parse_peer_status_xml(self, data):

        peers = []
        for _ in data.findall('peerStatus/peer'):
            try:
                peers.append(self._parse_peer(_))
            except Exception as e:
                raise CallError(
                    f'Failed parsing peer information with error: {e}'
                )

        return peers

    @private
    async def resolve_host_or_ip(self, hostname, verrors):

        args = (self.middleware, verrors, 'resolve_host_or_ip', hostname)
        return await resolve_hostname(*args)

    @private
    def common_validation(self, hostname=None):

        verrors = ValidationErrors()

        if hostname:
            self.middleware.call_sync(
                'gluster.peer.resolve_host_or_ip', hostname, verrors)

        verrors.check()

    @accepts(
        Dict(
            'probe_peer_create',
            Str('hostname', required=True, max_length=253)
        )
    )
    @job(lock=GLUSTER_JOB_LOCK)
    def create(self, job, data):
        """
        Add peer to the Trusted Storage Pool.

        `hostname` can be an IP(v4/v6) address or DNS name.
        """

        hostname = data.get('hostname')

        self.common_validation(hostname=hostname)

        return run_method(peer.attach, hostname)

    @accepts(
        Dict(
            'probe_peer_delete',
            Str('hostname', required=True, max_length=253)
        )
    )
    @job(lock=GLUSTER_JOB_LOCK)
    def delete(self, job, data):
        """
        Remove peer of `hostname` from the Trusted Storage Pool.
        """

        hostname = data.get('hostname')

        self.common_validation(hostname=hostname)

        return run_method(peer.detach, hostname)

    @accepts()
    def status(self):
        """
        List the status of peers in the Trusted Storage Pool
        excluding localhost.
        """

        return run_method(peer.status)

    @accepts()
    def pool(self):
        """
        List the status of peers in the Trusted Storage Pool
        including localhost.
        """

        final = None

        # get the local viewpoint of the remote peers in the TSP
        if local_view := run_method(peer.status):
            remote_node = None
            # need to pull out a remote peer (that's connected)
            for i in local_view:
                if i['connected'] == 'Connected' and i['hostname'] != 'localhost':
                    remote_node = i['hostname']
                    break

            if remote_node is None:
                raise CallError('All remote peers are disconnected.')

            # now we need to run the same command as `run_method(peer.status)`
            # but specifying a remote peer to get the "remote_local_view"
            command = [
                'gluster',
                f'--remote-host={remote_node}',
                'peer', 'status', '--xml'
            ]
            cp = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )
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
            remote_local_view = ET.fromstring(cp.stdout)
            remote_local_view = self._parse_peer_status_xml(remote_local_view)

            # now we compare the 2 "viewpoints" and deduce which IP address
            # is our own
            final = local_view.copy()

            # this should only ever produce 1 entry
            our_ip = [i for i in remote_local_view if i not in local_view]
            if len(our_ip) != 1:
                raise CallError(
                    f'Remote peer: {remote_node} sees these peers: '
                    f'{remote_local_view}'
                    f'The local peer sees these peers: {local_view}.'
                    'The local and remote peers should be the same quantity.'
                )

            final.append(our_ip[0])

        return list(final)

    @accepts()
    async def ips_available(self):
        """
        List of IPv4/v6 addresses available that can be used
        as the `peer_name` when creating a gluster volume.

        NOTE:
            This will only return statically assigned IPs.
            If this is an HA system, this will only return
            the VIP addresses that have been configured on
            the system.
        """

        return [
            d['address'] for d in await self.middleware.call(
                'interface.ip_in_use', {'static': True}
            )
        ]
