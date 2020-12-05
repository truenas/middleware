from glustercli.cli import peer
from glustercli.cli.utils import GlusterCmdException

from middlewared.async_validators import resolve_hostname
from middlewared.schema import Dict, Str
from middlewared.service import (accepts, private, job,
                                 CallError, CRUDService,
                                 ValidationErrors)

from .utils import GlusterConfig

import subprocess
import xml.etree.ElementTree as ET


GLUSTER_JOB_LOCK = GlusterConfig.CLI_LOCK.value


class GlusterPeerService(CRUDService):

    class Config:
        namespace = 'gluster.peer'

    def __peer_wrapper(self, method, host=None):

        result = b''

        try:
            result = method(host) if host else method()
        except GlusterCmdException as e:
            # the gluster cli utility will return stderr
            # to stdout and vice versa on certain failures.
            # account for this and decode appropriately
            rc, out, err = e.args[0]
            err = err if err else out
            if isinstance(err, bytes):
                err = err.decode()
            raise CallError(f'{err.strip()}')
        except Exception:
            raise

        if isinstance(result, bytes):
            return result.decode().strip()

        return result

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

    def _parse_peer_status_xml(self, data):

        peers = []
        for _ in data.findall('peerStatus/peer'):
            try:
                peers.append(self._parse_peer(_))
            except Exception as e:
                raise CallError(f'{e}')

        return peers

    @private
    def remove_peer_from_cluster(self, hostname):

        return self.__peer_wrapper(peer.detach, host=hostname)

    @private
    def add_peer_to_cluster(self, hostname):

        return self.__peer_wrapper(peer.attach, host=hostname)

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
    def do_create(self, job, data):
        """
        Add peer to the Trusted Storage Pool.

        `hostname` can be an IP(v4/v6) address or DNS name.
        """

        hostname = data.get('hostname')

        self.common_validation(hostname=hostname)

        result = self.add_peer_to_cluster(hostname)

        return result

    @accepts(
        Dict(
            'probe_peer_delete',
            Str('hostname', required=True, max_length=253)
        )
    )
    @job(lock=GLUSTER_JOB_LOCK)
    def do_delete(self, job, data):
        """
        Remove peer of `hostname` from the Trusted Storage Pool.
        """

        hostname = data.get('hostname')

        self.common_validation(hostname=hostname)

        result = self.remove_peer_from_cluster(hostname)

        return result

    @accepts()
    @job(lock=GLUSTER_JOB_LOCK)
    def status(self, job):
        """
        List the status of peers in the Trusted Storage Pool
        excluding localhost.
        """

        return self.__peer_wrapper(peer.status)

    @accepts()
    @job(lock=GLUSTER_JOB_LOCK)
    def pool(self, job):
        """
        List the status of peers in the Trusted Storage Pool
        including localhost.
        """

        # get the local viewpoint of the remote peers in the TSP
        local_view = self.__peer_wrapper(peer.status)
        if not local_view:
            return local_view

        # need to pull out a remote peer (that's connected)
        remote_node = None
        for i in local_view:
            if i['connected'] == 'Connected' and i['hostname'] != 'localhost':
                remote_node = i['hostname']
                break

        if remote_node is None:
            raise CallError('All remote peers are disconnected.')

        # now we need to run the same command as `__peer_wrapper(peer.status)`
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
            raise CallError(f'{err.strip()}')

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
        return final
