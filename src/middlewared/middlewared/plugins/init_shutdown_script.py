from middlewared.schema import Bool, Dict, File, Int, Patch, Str, ValidationErrors, accepts
from middlewared.service import CRUDService, private


class InitShutdownScriptService(CRUDService):

    class Config:
        datastore = 'tasks.initshutdown'
        datastore_prefix = 'ini_'
        datastore_extend = 'initshutdownscript.init_shutdown_script_extend'

    @accepts(Dict(
        'init_shutdown_script_create',
        Str('type', enum=['COMMAND', 'SCRIPT']),
        Str('command'),
        File('script'),
        Str('when', enum=['PREINIT', 'POSTINIT', 'SHUTDOWN']),
        Bool('enabled'),
        register=True,
        ))
    async def do_create(self, data):
        await self.validate(data, 'init_shutdown_script_create')

        await self.init_shutdown_script_compress(data)

        data["id"] = await self.middleware.call('datastore.insert', self._config.datastore, data,
                                                {'prefix': self._config.datastore_prefix})

        await self.init_shutdown_script_extend(data)

        return data

    @accepts(Int('id'), Patch(
        'init_shutdown_script_create',
        'init_shutdown_script_update',
        ('attr', {'update': True}),
    ))
    async def do_update(self, id, data):
        old = await self.middleware.call('datastore.query', self._config.datastore, [('id', '=', id)],
                                         {'extend': self._config.datastore_extend,
                                          'prefix': self._config.datastore_prefix,
                                          'get': True})

        new = old.copy()
        new.update(data)

        await self.validate(data, 'init_shutdown_script_update')

        await self.init_shutdown_script_compress(data)

        await self.middleware.call('datastore.update', self._config.datastore, id, data,
                                   {'prefix': self._config.datastore_prefix})

        await self.init_shutdown_script_extend(new)

        return new

    @accepts(Int('id'))
    async def do_delete(self, id):
        return await self.middleware.call('datastore.delete', self._config.datastore, id)

    @private
    async def init_shutdown_script_extend(self, init_shutdown_script):
        init_shutdown_script["type"] = init_shutdown_script["type"].upper()
        init_shutdown_script["when"] = init_shutdown_script["when"].upper()
        return init_shutdown_script

    @private
    async def init_shutdown_script_compress(self, init_shutdown_script):
        init_shutdown_script["type"] = init_shutdown_script["type"].lower()
        init_shutdown_script["when"] = init_shutdown_script["when"].lower()
        return init_shutdown_script

    @private
    async def validate(self, init_shutdown_script, schema_name):
        verrors = ValidationErrors()

        if init_shutdown_script["type"] == "COMMAND":
            if not init_shutdown_script["command"]:
                verrors.add("%s.command" % schema_name, "This field is required")

        if init_shutdown_script["type"] == "SCRIPT":
            if not init_shutdown_script["script"]:
                verrors.add("%s.script" % schema_name, "This field is required")

        if verrors:
            raise verrors
