import asyncio
from gluster.cli import peer
from gluster.cli.utils import GlusterCmdException

from middlewared.async_validators import resolve_hostname
from middlewared.schema import Dict, Str, Int
from middlewared.service import (accepts, private, job,
                                 CallError, CRUDService,
                                 ValidationErrors)
import middlewared.sqlalchemy as sa


class GlusterPeerModel(sa.Model):
    __tablename__ = 'gluster_peers'

    id = sa.Column(sa.Integer(), primary_key=True)
    uuid = sa.Column(sa.String(36))
    hostname = sa.Column(sa.String(39))
    connected = sa.Column(sa.String(50))


class GlusterPeerService(CRUDService):

    class Config:
        namespace = 'gluster.peer'
        datastore = 'gluster_peers'

    @private
    def remove_peer_from_db(self, id):

        try:
            self.middleware.call_sync(
                'datastore.delete',
                self._config.datastore, [('id', '=', id)])
        except Exception as e:
            raise CallError(f'{e}')

    @private
    def add_peer_to_db(self, hostname):

        status = self.pool()
        rv = [i for i in status if i['hostname'] == hostname]

        try:
            self.middleware.call_sync(
                'datastore.insert', self._config.datastore, rv[0])
        except Exception as e:
            raise CallError(f'{e}')

    @private
    def remove_peer_from_cluster(self, hostname):

        result = ''
        try:
            result = peer.detach(hostname)
        except GlusterCmdException as e:
            rc, out, err = e.args[0]
            err = err if err else out
            raise CallError(f'{err.decode().strip()}')

        if isinstance(result, bytes):
            return result.decode().strip()

        return result

    @private
    def add_peer_to_cluster(self, hostname):

        result = ''
        try:
            result = peer.probe(hostname)
        except GlusterCmdException as e:
            rc, out, err = e.args[0]
            err = err if err else out
            raise CallError(f'{err.decode().strip()}')

        if isinstance(result, bytes):
            return result.decode().strip()

        return result

    @private
    def is_peer_in_cluster(self, hostname):

        curr = self.pool()

        result = [i.get('hostname') for i in curr if i['hostname'] in hostname]

        if result:
            return True

        return False

    @private
    def is_peer_in_db(self, hostname):

        result = self.middleware.call_sync('datastore.query',
            self._config.datastore, [('hostname', '=', hostname)])

        if result:
            return True

        return False

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

        in_cluster = self.is_peer_in_cluster(hostname)
        in_db = self.is_peer_in_db(hostname)

        if in_cluster:
            verrors.add(
                f'common_validation',
                f'{hostname} already exists in the cluster')

        if in_db:
            verrors.add(
                f'common_validation',
                f'{hostname} already exists in the database')

        verrors.check()

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

        added_to_cluster = self.add_peer_to_cluster(hostname)

        if added_to_cluster:
            if 'localhost not needed' not in added_to_cluster:
                try:
                    self.add_peer_to_db(hostname)
                except CallError:
                    try:
                        self.remove_peer_from_cluster(hostname)
                    except Exception:
                        self.logger.warning(
                            f'Failed to remove {hostname} from cluster'
                            'on rollback operation')
                        raise
            else:
                return added_to_cluster
        else:
            return  # should never get here

        status = self.pool()

        new_peer = [i for i in status if i['hostname'] == hostname]

        return new_peer[0]

    @accepts(Int('id'))
    @job(lock='probe_peer_delete')
    def do_delete(self, job, id):
        """
        Remove peer of `id` from the Trusted Storage Pool.
        """

        verrors = ValidationErrors()

        data = self.middleware.call_sync('datastore.query',
                    self._config.datastore,
                    [('id', '=', id)])

        if data:
            db_hostname = data[0].get('hostname')

            status = self.pool()

            in_cluster = [i.get('hostname') for i in status
                          if i['hostname'] == db_hostname]

            if in_cluster:
                self.remove_peer_from_cluster(db_hostname)

            self.remove_peer_from_db(id)
        else:
            verrors.add(
                f'delete_peer',
                f'entry with id {id} was not found in the database')

        verrors.check()

    @accepts()
    def status(self):
        """
        List the status of peers in the cluster excluding localhost.
        """
        result = []
        try:
            result = peer.status()
        except GlusterCmdException as e:
            rc, out, err = e.args[0]
            err = err if err else out
            raise CallError(f'{err.decode().strip()}')

        return result

    @accepts()
    def pool(self):
        """
        List the status of peers in the cluster including localhost.
        """
        result = []
        try:
            result = peer.pool()
        except GlusterCmdException as e:
            rc, out, err = e.args[0]
            err = err if err else out
            raise CallError(f'{err.decode().strip()}')

        return result
