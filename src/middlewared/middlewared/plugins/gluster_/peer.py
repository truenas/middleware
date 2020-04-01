import asyncio
from gluster.cli import peer
from gluster.cli.utils import GlusterCmdException

from middlewared.async_validators import resolve_hostname
from middlewared.schema import Dict, Str
from middlewared.service import (accepts, private, job,
                                 CallError, CRUDService,
                                 ValidationErrors)


class GlusterPeerService(CRUDService):

    class Config:
        namespace = 'gluster.peer'
        datastore = 'gluster_peers'

    def __peer_wrapper(self, method, host=None):

        result = ''
        try:
            result = method(host) if host else method()
        except GlusterCmdException as e:
            rc, out, err = e.args[0]
            err = err if err else out
            raise CallError(f'{err.decode().strip()}')
        except Exception as e:
            raise e

        if isinstance(result, bytes):
            return result.decode().strip()

        return result

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
    def common_validation(self, hostname):

        verrors = ValidationErrors()

        loop = self.middleware.loop
        try:
            asyncio.run_coroutine_threadsafe(
                    self.resolve_host_or_ip(hostname, verrors), loop).result()
        except Exception:
            if verrors:
                raise verrors
            raise

    @accepts(
        Dict(
            'probe_peer_create',
            Str('hostname', required=True, max_length=253)
        )
    )
    @job(lock='probe_peer_create')
    def do_create(self, job, data):
        """
        Add peer to the Trusted Storage Pool.

        `hostname` can be an IP(v4/v6) address or DNS name.
        """

        hostname = data.get('hostname')

        self.common_validation(hostname)

        result = self.add_peer_to_cluster(hostname)

        if 'localhost not needed' in result:
            return result

        return result

    @accepts(
        Dict(
            'probe_peer_delete',
            Str('hostname', required=True, max_length=253)
        )
    )
    @job(lock='probe_peer_delete')
    def do_delete(self, job, data):
        """
        Remove peer of `hostname` from the Trusted Storage Pool.
        """

        hostname = data.get('hostname')

        self.common_validation(hostname)

        result = self.remove_peer_from_cluster(hostname)

        if 'is localhost' in result:
            return result

        return result

    @accepts()
    def status(self):
        """
        List the status of peers in the Trusted Storage Pool
        excluding localhost.
        """

        return self.__peer_wrapper(peer.status)

    @accepts()
    def pool(self):
        """
        List the status of peers in the Trusted Storage Pool
        including localhost.
        """

        return self.__peer_wrapper(peer.pool)
