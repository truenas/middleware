from .config_service import ConfigService
from .decorators import private


class SystemServiceService(ConfigService, no_config=True):
    """
    System service class

    Meant for services that manage system services configuration.
    """

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
