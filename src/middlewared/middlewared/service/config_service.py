import asyncio
import copy
from typing import Annotated

from pydantic import create_model, Field

from middlewared.api import api_method
from middlewared.api.base.model import BaseModel
from middlewared.schema import accepts, Dict, Patch, returns

from .base import ServiceBase
from .decorators import pass_app, private
from .service import Service
from .service_mixin import ServiceChangeMixin


get_or_insert_lock = asyncio.Lock()


class ConfigServiceMetabase(ServiceBase):

    def __new__(cls, name, bases, attrs):
        klass = super().__new__(cls, name, bases, attrs)
        if any(
            name == c_name and len(bases) == len(c_bases) and all(
                b.__name__ == c_b for b, c_b in zip(bases, c_bases)
            )
            for c_name, c_bases in (
                ('ConfigService', ('ServiceChangeMixin', 'Service')),
                ('SystemServiceService', ('ConfigService',)),
            )
        ):
            return klass

        namespace = klass._config.namespace.replace('.', '_')
        config_entry_key = f'{namespace}_entry'
        config_model_name = f'{namespace.capitalize()}Config'

        if not klass._config.private and not klass._config.role_prefix:
            raise ValueError(f'{klass._config.namespace}: public ConfigService must have role_prefix defined')

        if klass._config.entry is not None and not hasattr(klass.config, 'new_style_accepts'):
            klass.ENTRY = None
            result_model = create_model(
                klass._config.entry.__name__.removesuffix('Entry') + 'ConfigResult',
                __base__=(BaseModel,),
                __module__=klass._config.entry.__module__,
                result=Annotated[klass._config.entry, Field()]
            )
            klass.config = api_method(
                create_model(
                    config_model_name,
                    __base__=(BaseModel,),
                    __module__=klass._config.entry.__module__,
                ),
                result_model
            )(klass.config)
        else:
            if klass.ENTRY == NotImplementedError:
                klass.ENTRY = Dict(config_entry_key, additional_attrs=True)

            config_entry_key = klass.ENTRY.name
            config_entry = copy.deepcopy(klass.ENTRY)
            config_entry.register = True
            if not hasattr(klass.config, 'accepts'):
                klass.config = accepts()(klass.config)
            klass.config = returns(config_entry)(klass.config)

        if hasattr(klass, 'do_update'):
            # We are not going to dynamically update do_update method with new api style
            if klass._config.entry:
                # We are not going to patch do_update with old accepts/returns if entry is already defined
                return klass

            for m_name, decorator in filter(
                lambda m: not hasattr(klass.do_update, m[0]),
                (('returns', returns), ('accepts', accepts))
            ):
                new_name = f'{namespace}_update'
                if m_name == 'returns':
                    new_name += '_returns'
                patch_entry = Patch(config_entry_key, new_name, register=True)
                schema = [patch_entry]
                if m_name == 'accepts':
                    patch_entry.patches.append(('rm', {
                        'name': klass._config.datastore_primary_key,
                        'safe_delete': True,
                    }))
                    patch_entry.patches.append(('attr', {'update': True}))
                klass.do_update = decorator(*schema)(klass.do_update)

        return klass


class ConfigService(ServiceChangeMixin, Service, metaclass=ConfigServiceMetabase):
    """
    Config service abstract class

    Meant for services that provide a single set of attributes which can be
    updated or not.
    """

    ENTRY = NotImplementedError

    async def config(self):
        options = {}
        options['extend'] = self._config.datastore_extend
        options['extend_context'] = self._config.datastore_extend_context
        options['prefix'] = self._config.datastore_prefix
        return await self._get_or_insert(self._config.datastore, options)

    @pass_app(message_id=True, rest=True)
    async def update(self, app, message_id, data):
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
                    return await self.middleware.call('datastore.config', datastore, options)

        return rows[0]
