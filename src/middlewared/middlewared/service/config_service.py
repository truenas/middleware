import asyncio
from typing import Annotated

from pydantic import create_model, Field

from middlewared.api import api_method
from middlewared.api.base.model import BaseModel

from .base import ServiceBase
from .decorators import pass_app, private
from .service import Service
from .service_mixin import ServiceChangeMixin


get_or_insert_lock = asyncio.Lock()


def config_args(entry: type[BaseModel]) -> type[BaseModel]:
    return create_model(
        entry.__name__.removesuffix("Entry") + 'ConfigArgs',
        __base__=(BaseModel,),
        __module__=entry.__module__,
    )


def config_result(entry: type[BaseModel]) -> type[BaseModel]:
    return create_model(
        entry.__name__.removesuffix('Entry') + 'ConfigResult',
        __base__=(BaseModel,),
        __module__=entry.__module__,
        result=Annotated[entry, Field()],
    )


class ConfigServiceMetabase(ServiceBase):

    def __new__(cls, name, bases, attrs):
        klass = super().__new__(cls, name, bases, attrs)
        # Skip public config method for ConfigService and SystemServiceService
        if any(
            name == c_name and len(bases) == len(c_bases) and all(
                b.__name__ == c_b for b, c_b in zip(bases, c_bases)
            )
            for c_name, c_bases in (
                ('ConfigService', ('ServiceChangeMixin', 'Service', 'Generic')),
                ('SystemServiceService', ('ConfigService',)),
            )
        ):
            return klass

        config = klass._config
        private = config.private
        entry = config.entry
        namespace = config.namespace

        if not private and not config.role_prefix:
            raise ValueError(f'{namespace}: public ConfigService must have role_prefix defined')

        if entry is None:
            if not private:
                raise ValueError(f'{namespace}: public ConfigService must have entry defined')
        else:
            # Decorate config method with api_method
            accepts_model = config_args(entry)
            result_model = config_result(entry)
            klass.config = api_method(
                accepts_model,
                result_model,
                private=private,
                cli_private=config.cli_private,
            )(klass.config)

            # Models must be registered with their factories for backwards compatibility.
            klass._register_models = [
                (accepts_model, config_args, entry.__name__),
                (result_model, config_result, entry.__name__),
            ]

        return klass


class ConfigService[E](ServiceChangeMixin, Service, metaclass=ConfigServiceMetabase):
    """
    Config service abstract class

    Meant for services that provide a single set of attributes which can be
    updated or not.
    """

    async def config(self) -> E:
        options = {}
        options['extend'] = self._config.datastore_extend
        options['extend_context'] = self._config.datastore_extend_context
        options['extend_fk'] = self._config.datastore_extend_fk
        options['prefix'] = self._config.datastore_prefix
        return await self._get_or_insert(self._config.datastore, options)

    @pass_app(message_id=True)
    async def update(self, app, message_id, data) -> E:
        rv = await self.middleware._call(
            f'{self._config.namespace}.update', self, self.do_update, [data], app=app, message_id=message_id,
        )
        await self.middleware.call_hook(f'{self._config.namespace}.post_update', rv)
        return rv

    @private
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

        if self._config.generic:
            rows[0] = self._config.entry(**rows[0])

        return rows[0]
