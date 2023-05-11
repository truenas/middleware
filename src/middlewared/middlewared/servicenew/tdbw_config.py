import copy
import time

from middlewared.schema import accepts
from middlewared.service_exception import CallError

from .config_service import ConfigService
from .decorators import private


class TDBWrapConfigService(ConfigService):
    """
    Config service with optional clustered backend

    `tdb_defaults` - returned if cluster unhealthy or version mismatch
    `cluster_healthy_fn` - method used to determine cluster health
    `is_clustered_fn` - method used to determine whether server is clustered
    `status` - result of last cluster health check
    `last_check` - timestamp of last health check
    `time_offset` - length of time in seconds to return last health check results

    Note: CallError will be raised on update() if cluster is unhealthy,
    version mismatch, or failure to attach tdb file.
    """
    service_version = {"major": 0, "minor": 1}
    tdb_defaults = {}
    cluster_healthy_fn = 'ctdb.general.healthy'
    is_clustered_fn = NotImplemented
    status = None
    last_check = 0
    time_offset = 30

    tdb_options = {
        "cluster": True,
        "tdb_type": "CONFIG",
        "read_backoff": 1,
        "service_version": service_version
    }

    @private
    async def _default_cluster_check(self):
        ha_mode = await self.middleware.call('smb.get_smb_ha_mode')
        return ha_mode == "CLUSTERED"

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
        constanting hitting `cluster_healthy_fn`.
        """
        now = time.monotonic()
        if self.last_check + self.time_offset > now:
            return self.status

        try:
            status = await self.middleware.call(self.cluster_healthy_fn)
        except Exception:
            self.logger.warning("%s: cluster health check [%s] failed.",
                                self._config.namespace, self.cluster_healthy_fn, exc_info=True)
            status = False

        self.status = status
        self.last_check = now

        return status

    @private
    async def db_healthy(self):
        try:
            health = await self.middleware.call("tdb.health", {
                "name": self._config.service,
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

    @accepts()
    async def config(self):
        is_clustered = await self.is_clustered()
        if not is_clustered:
            return await super().config()

        if not await self.cluster_healthy() and not await self.db_healthy():
            return copy.deepcopy(self.tdb_defaults)

        tdb_config = await self.middleware.call("tdb.config", {
            "name": self._config.service,
            "tdb-options": self.tdb_options.copy(),
        })
        version = tdb_config['version']
        data = tdb_config['data']

        if data is None:
            data = copy.deepcopy(self.tdb_defaults)

        if version and self.service_version != version:
            self.logger.error(
                "%s: Service version mismatch. Service update migration is required. "
                "Returning default values.", self._config.namespace
            )
            data = copy.deepcopy(self.tdb_defaults)

        if not self._config.datastore_extend:
            return data

        return await self.middleware.call(self._config.datastore_extend, data)

    @private
    async def direct_update(self, data):
        is_clustered = await self.is_clustered()
        if not is_clustered:
            id = data.pop("id", 1)
            await self.middleware.call(
                'datastore.update',
                self._config.datastore,
                id,
                data,
                {"prefix": self._config.datastore_prefix}
            )
            return await self.config()

        if not await self.cluster_healthy():
            raise CallError("Clustered configuration may not be altered while cluster is unhealthy.")

        old = await self.middleware.call("tdb.config", {
            "name": self._config.service,
            "tdb-options": self.tdb_options.copy(),
        })
        version = old['version']
        new = old['data']
        if new is None:
            new = copy.deepcopy(self.tdb_defaults)

        new.update(data)
        payload = {"version": self.service_version, "data": new}
        try:
            await self.middleware.call('tdb.config_update', {
                "name": self._config.service,
                "payload": payload,
                "tdb-options": self.tdb_options.copy(),
            })
        except ValueError:
            raise CallError(
                f'{self._config.namespace}: service version mismatch. '
                f'Node: {self.service_version["major"]}.{self.service_version["minor"]}'
                f'cluster: {version["major"]}.{version["minor"]}'
            )

        tdb_config = await self.middleware.call("tdb.config", {
            "name": self._config.service,
            "tdb-options": self.tdb_options.copy(),
        })

        if not self._config.datastore_extend:
            return tdb_config["data"]

        return await self.middleware.call(self._config.datastore_extend, tdb_config["data"])

    async def do_update(self, data):
        res = await self.direct_update(data)
        return res
