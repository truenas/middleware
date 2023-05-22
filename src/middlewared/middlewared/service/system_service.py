from middlewared.schema import accepts

from .config_service import ConfigService
from .decorators import private


class SystemServiceService(ConfigService):
    """
    System service class

    Meant for services that manage system services configuration.
    """

    @accepts()
    async def config(self):
        return await self._get_or_insert(
            self._config.datastore, {
                'extend': self._config.datastore_extend,
                'extend_context': self._config.datastore_extend_context,
                'prefix': self._config.datastore_prefix
            }
        )

    @private
    async def _update_service(self, old, new, verb=None, options=None):
        await self.middleware.call(
            'datastore.update', self._config.datastore, old['id'], new, {'prefix': self._config.datastore_prefix}
        )

        fut = self._service_change(self._config.service, verb or self._config.service_verb, options)
        if self._config.service_verb_sync:
            await fut
        else:
            self.middleware.create_task(fut)
