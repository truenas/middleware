from .config_service import get_or_insert_lock
from .part import ServicePart

__all__ = ("ConfigServicePart",)


class ConfigServicePart[E](ServicePart):
    __slots__ = ()

    _datastore: str = NotImplemented
    _datastore_extend: str | None = None
    _datastore_extend_context: str | None = None
    _datastore_extend_fk: str | None = None
    _datastore_prefix: str = ''
    _entry: type[E] = NotImplemented

    async def config(self) -> E:
        options = {}
        options['extend'] = self._datastore_extend
        options['extend_context'] = self._datastore_extend_context
        options['extend_fk'] = self._datastore_extend_fk
        options['prefix'] = self._datastore_prefix
        return await self._get_or_insert(self._datastore, options)

    async def _get_or_insert(self, datastore, options):
        rows = await self.middleware.call('datastore.query', datastore, [], options)
        if not rows:
            async with get_or_insert_lock:
                # We do this again here to avoid TOCTOU as we don't want multiple calls inserting records
                # and we ending up with duplicates again
                # Earlier we were doing try/catch on IndexError and using datastore.config directly
                # however that can be misleading because when we do a query and we have any extend in
                # place which raises the same IndexError or MatchNotFound, we would catch it assuming
                # we don't have a row available whereas the row was there but the service's extend
                # had errored out with that exception and we would misleadingly insert another duplicate
                # record
                rows = await self.middleware.call('datastore.query', datastore, [], options)
                if not rows:
                    await self.middleware.call('datastore.insert', datastore, {})
                    rows = [await self.middleware.call('datastore.config', datastore, options)]

        rows[0] = self._entry(**rows[0])

        return rows[0]
