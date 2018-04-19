from middlewared.schema import accepts, Bool, Dict, Int, Str, Patch
from middlewared.service import ValidationErrors, CRUDService, private
from freenasUI.common.system import test_ntp_server


class NTPServerService(CRUDService):
    class Config:
        namespace = 'system.ntpserver'
        datastore = 'system.ntpserver'
        datastore_prefix = 'ntp_'

    @accepts(Dict(
        'ntp_create',
        Str('address'),
        Bool('burst', default=False),
        Bool('iburst', default=True),
        Bool('prefer', default=False),
        Int('minpoll', default=6),
        Int('maxpoll', default=10),
        Bool('force'),
        register=True
    ))
    async def do_create(self, data):
        print(data)
        await self.clean(data, 'ntpserver_create')

        data['id'] = await self.middleware.call(
            'datastore.insert', self._config.datastore, data,
            {'prefix': self._config.datastore_prefix})

        await self.middleware.call('service.start', 'ix-ntpd')
        await self.middleware.call('service.restart', 'ntpd')

        return data

    @accepts(
        Int('id'),
        Patch(
            'ntp_create',
            'ntp_update',
            ('attr', {'update': True})
        )
    )
    async def do_update(self, id, data):
        old = await self.middleware.call(
            'datastore.query', self._config.datastore, [('id', '=', id)],
            {'extend': self._config.datastore_extend,
             'prefix': self._config.datastore_prefix,
             'get': True})

        new = old.copy()
        new.update(data)

        await self.clean(new, 'ntpserver_update')

        await self.middleware.call(
            'datastore.update', self._config.datastore, id, new,
            {'prefix': self._config.datastore_prefix})

        await self.middleware.call('service.start', 'ix-ntpd')
        await self.middleware.call('service.restart', 'ntpd')

        return new

    @accepts(Int('id'))
    async def do_delete(self, id):
        return await self.middleware.call(
            'datastore.delete', self._config.datastore, id)

    @private
    async def clean(self, data, schema_name):
        verrors = ValidationErrors()
        maxpoll = data['maxpoll']
        minpoll = data['minpoll']
        force = data.pop('force', False)
        usable = True if test_ntp_server(data['address']) else False

        if not force and not usable:
            verrors.add(f'{schema_name}.address',
                        'Server could not be reached. Check "Force" to '
                        'continue regardless.'
                        )

        if not maxpoll > minpoll:
            verrors.add(f'{schema_name}.maxpoll',
                        'Max Poll should be higher than Min Poll')

        if verrors:
            raise verrors

        return data
