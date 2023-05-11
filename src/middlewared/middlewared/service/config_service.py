import asyncio
import copy

from middlewared.schema import accepts, Dict, Patch, returns

from .base import ServiceBase
from .decorators import private
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
                ('TDBWrapConfigService', ('ConfigService',)),
            )
        ):
            return klass

        namespace = klass._config.namespace.replace('.', '_')
        config_entry_key = f'{namespace}_entry'

        if klass.ENTRY == NotImplementedError:
            klass.ENTRY = Dict(config_entry_key, additional_attrs=True)

        config_entry_key = klass.ENTRY.name

        config_entry = copy.deepcopy(klass.ENTRY)
        config_entry.register = True
        klass.config = returns(config_entry)(klass.config)

        if hasattr(klass, 'do_update'):
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

    @accepts()
    async def config(self):
        options = {}
        options['extend'] = self._config.datastore_extend
        options['extend_context'] = self._config.datastore_extend_context
        options['prefix'] = self._config.datastore_prefix
        return await self._get_or_insert(self._config.datastore, options)

    async def update(self, data):
        rv = await self.middleware._call(
            f'{self._config.namespace}.update', self, self.do_update, [data]
        )
        await self.middleware.call_hook(f'{self._config.namespace}.post_update', rv)
        return rv

    @private
    async def _get_or_insert(self, datastore, options):
        try:
            return await self.middleware.call('datastore.config', datastore, options)
        except IndexError:
            async with get_or_insert_lock:
                try:
                    return await self.middleware.call('datastore.config', datastore, options)
                except IndexError:
                    await self.middleware.call('datastore.insert', datastore, {})
                    return await self.middleware.call('datastore.config', datastore, options)
