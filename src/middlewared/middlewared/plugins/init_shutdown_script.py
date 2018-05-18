from middlewared.schema import (Bool, Dict, File, Int, Patch, Str,
                                ValidationErrors, accepts)
from middlewared.service import CRUDService, private


class InitShutdownScriptService(CRUDService):

    class Config:
        datastore = 'tasks.initshutdown'
        datastore_prefix = 'ini_'
        datastore_extend = 'initshutdownscript.init_shutdown_script_extend'

    @accepts(Dict(
        'init_shutdown_script_create',
        Str('type', enum=['COMMAND', 'SCRIPT'], required=True),
        Str('command'),
        File('script'),
        Str('when', enum=['PREINIT', 'POSTINIT', 'SHUTDOWN'], required=True),
        Bool('enabled', default=True),
        register=True,
    ))
    async def do_create(self, data):
        await self.validate(data, 'init_shutdown_script_create')

        await self.init_shutdown_script_compress(data)

        data['id'] = await self.middleware.call(
            'datastore.insert',
            self._config.datastore,
            data,
            {'prefix': self._config.datastore_prefix}
        )

        await self.init_shutdown_script_extend(data)

        return await self._get_instance(data['id'])

    @accepts(Int('id'), Patch(
        'init_shutdown_script_create',
        'init_shutdown_script_update',
        ('attr', {'update': True}),
    ))
    async def do_update(self, id, data):
        old = await self._get_instance(id)
        new = old.copy()
        new.update(data)

        await self.validate(new, 'init_shutdown_script_update')

        await self.init_shutdown_script_compress(new)

        await self.middleware.call(
            'datastore.update',
            self._config.datastore,
            id,
            data,
            {'prefix': self._config.datastore_prefix}
        )

        await self.init_shutdown_script_extend(new)

        return await self._get_instance(new['id'])

    @accepts(Int('id'))
    async def do_delete(self, id):
        return await self.middleware.call(
            'datastore.delete',
            self._config.datastore,
            id
        )

    @private
    async def init_shutdown_script_extend(self, data):
        data['type'] = data['type'].upper()
        data['when'] = data['when'].upper()

        return data

    @private
    async def init_shutdown_script_compress(self, data):
        data['type'] = data['type'].lower()
        data['when'] = data['when'].lower()

        return data

    @private
    async def validate(self, data, schema_name):
        verrors = ValidationErrors()

        if data['type'] == 'COMMAND':
            if not data.get('command'):
                verrors.add(f'{schema_name}.command', 'This field is required')

        if data['type'] == 'SCRIPT':
            if not data.get('script'):
                verrors.add(f'{schema_name}.script', 'This field is required')

        if verrors:
            raise verrors
