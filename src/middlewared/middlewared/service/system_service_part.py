import typing

from .config_service_part import ConfigServicePart
from .service_mixin import ServiceChangeMixin

__all__ = ("SystemServicePart",)


ServiceVerb = typing.Literal['reload', 'restart']


class SystemServicePart[E](ConfigServicePart[E], ServiceChangeMixin):
    __slots__ = ()

    _service: str = NotImplemented
    _service_verb: ServiceVerb = 'reload'
    _service_verb_sync: bool = True

    async def _update_service(
        self, row_id: int, new: dict, verb: ServiceVerb | None = None, options: dict | None = None
    ):
        await self.middleware.call(
            'datastore.update',
            self._datastore,
            row_id,
            new,
            {'prefix': self._datastore_prefix},
        )

        fut = self._service_change(self._service, verb or self._service_verb, options)
        if self._service_verb_sync:
            await fut
        else:
            self.middleware.create_task(fut)
