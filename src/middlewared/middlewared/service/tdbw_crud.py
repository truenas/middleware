import copy
import time

from middlewared.service_exception import CallError
from middlewared.utils import filter_list

from .crud_service import CRUDService
from .decorators import filterable, private


class TDBWrapCRUDService(CRUDService):
    """
    Config service with optional clustered backend

    `cluster_healthy_fn` - method used to determine cluster health
    `is_clustered_fn` - method used to determine whether server is clustered
    `status` - result of last cluster health check
    `last_check` - timestamp of last health check
    `time_offset` - length of time in seconds to return last health check results

    Note: CallError will be raised on update() if cluster is unhealthy,
    version mismatch, or failure to attach tdb file.
    """
    service_version = {'major': 0, 'minor': 1}
    tdb_path = None
    tdb_defaults = []
    cluster_healthy_fn = 'ctdb.general.healthy'
    is_clustered_fn = NotImplemented
    status = None
    last_check = 0
    time_offset = 30

    tdb_options = {
        'cluster': True,
        'tdb_type': 'CRUD',
        'read_backoff': 1,
        'service_version': service_version,
    }

    @private
    async def _default_cluster_check(self):
        ha_mode = await self.middleware.call('smb.get_smb_ha_mode')
        return ha_mode == 'CLUSTERED'

    @private
    async def is_clustered(self):
        if self.is_clustered_fn is NotImplemented:
            return await self._default_cluster_check()

        return await self.middleware.call(self.is_clustered_fn)

    @private
    async def cluster_healthy(self):
        """
        Return cached results for up to `time_offset` seconds.
        This is to provide some backoff so that services aren't
        constantly hitting `cluster_healthy_fn`.
        """
        now = time.monotonic()
        if self.last_check + self.time_offset > now:
            return self.status

        try:
            status = await self.middleware.call(self.cluster_healthy_fn)
        except Exception:
            self.logger.warning(
                '%s: cluster health check [%s] failed.', self._config.namespace,
                self.cluster_healthy_fn, exc_info=True
            )
            status = False

        self.status = status
        self.last_check = now

        return status

    @private
    async def insert_defaults(self):
        payload = []
        for entry in self.tdb_defaults:
            tdb_key = f'{self._config.namespace}_{entry["id"]}'
            val = entry.copy()
            val.pop("id")

            payload.append({
                'action': 'SET',
                'key': tdb_key,
                'val': val,
            })

        await self.middleware.call('tdb.batch_ops', {
            'name': self._config.namespace,
            'ops': payload,
            'tdb-options': self.tdb_options.copy()
        })

    @private
    async def db_healthy(self):
        try:
            health = await self.middleware.call("tdb.health", {
                "name": self._config.namespace,
                "tdb-options": self.tdb_options.copy(),
            })
        except Exception:
            self.logger.warning("%s: ctdb volume health status check failed.",
                                self._config.service, exc_info=True)
        else:
            if health == "OK":
                return True

            self.logger.warning("%s: health status is [%s] returning default value",
                                self._config.service, health)

        return False

    @filterable
    async def query(self, filters, options):
        is_clustered = await self.is_clustered()
        if not is_clustered:
            res = await super().query(filters, options)
            return res

        if not await self.cluster_healthy() and not await self.db_healthy():
            return copy.deepcopy(self.tdb_defaults)

        res = await self.middleware.call('tdb.query', {
            'name': self._config.namespace,
            'tdb-options': self.tdb_options.copy()
        })

        version = res['version']
        data = res['data']

        if data is None:
            return copy.deepcopy(self.tdb_defaults)

        if version and self.service_version != version:
            self.logger.error(
                "%s: Service version mismatch. Service update migration is required. "
                "Returning default values.", self._config.namespace
            )
            return copy.deepcopy(self.tdb_defaults)

        if not self._config.datastore_extend:
            return filter_list(data, filters, options)

        to_filter = []
        for entry in data:
            extended = await self.middleware.call(self._config.datastore_extend, entry)
            to_filter.append(extended)

        if not to_filter and self.tdb_defaults:
            await self.insert_defaults()
            to_filter = copy.deepcopy(self.tdb_defaults)

        return filter_list(to_filter, filters, options)

    @private
    async def direct_create(self, data):
        is_clustered = await self.is_clustered()
        if not is_clustered:
            id_ = await self.middleware.call(
                "datastore.insert",
                self._config.datastore, data,
                {"prefix": self._config.datastore_prefix},
            )
            return id_

        if not await self.cluster_healthy():
            raise CallError("Clustered configuration may not be altered while cluster is unhealthy.")

        try:
            res = await self.middleware.call('tdb.create', {
                'name': self._config.namespace,
                'payload': {"version": self.service_version, "data": data},
                'tdb-options': self.tdb_options.copy()
            })
        except ValueError:
            raise CallError(
                f'{self._config.namespace}: service version mismatch. '
                f'Node: {self.service_version["major"]}.{self.service_version["minor"]}'
            )

        return res

    async def do_create(self, data):
        res = await self.direct_create(data)
        return res

    @private
    async def direct_update(self, id_, data):
        is_clustered = await self.is_clustered()
        if not is_clustered:
            res = await self.middleware.call(
                'datastore.update',
                self._config.datastore, id_, data,
                {'prefix': self._config.datastore_prefix},
            )
            return res

        if not await self.cluster_healthy():
            raise CallError('Clustered configuration may not be altered while cluster is unhealthy.')

        try:
            res = await self.middleware.call('tdb.update', {
                'name': self._config.namespace,
                'id': id_,
                'payload': {'version': self.service_version, 'data': data},
                'tdb-options': self.tdb_options.copy(),
            })
        except ValueError:
            raise CallError(
                f'{self._config.namespace}: service version mismatch. '
                f'Node: {self.service_version["major"]}.{self.service_version["minor"]}'
            )

        return res

    async def do_update(self, id_, data):
        res = await self.direct_update(id_, data)
        return res

    @private
    async def direct_delete(self, id_):
        is_clustered = await self.is_clustered()
        if not is_clustered:
            return await self.middleware.call('datastore.delete', self._config.datastore, id_)

        if not await self.cluster_healthy():
            raise CallError('Clustered configuration may not be altered while cluster is unhealthy.')

        res = await self.middleware.call('tdb.delete', {
            'name': self._config.namespace,
            'id': id_,
            'tdb-options': self.tdb_options.copy(),
        })

        return res

    async def do_delete(self, id_):
        res = await self.direct_delete(id_)
        return res
