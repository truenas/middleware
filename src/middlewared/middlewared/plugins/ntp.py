from middlewared.schema import accepts, Bool, Dict, Int, Str, Patch
from middlewared.service import ValidationErrors, CRUDService, private
import middlewared.sqlalchemy as sa

import ntplib


class NTPModel(sa.Model):
    __tablename__ = 'system_ntpserver'

    id = sa.Column(sa.Integer(), primary_key=True)
    ntp_address = sa.Column(sa.String(120))
    ntp_burst = sa.Column(sa.Boolean(), default=False)
    ntp_iburst = sa.Column(sa.Boolean(), default=True)
    ntp_prefer = sa.Column(sa.Boolean(), default=False)
    ntp_minpoll = sa.Column(sa.Integer(), default=6)
    ntp_maxpoll = sa.Column(sa.Integer(), default=10)


class NTPServerService(CRUDService):
    class Config:
        namespace = 'system.ntpserver'
        datastore = 'system.ntpserver'
        datastore_prefix = 'ntp_'
        cli_namespace = 'system.ntp_server'

    ENTRY = Patch(
        'ntp_create', 'ntp_entry',
        ('rm', {'name': 'force'}),
        ('add', Int('id')),
    )

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
        """
        Add an NTP Server.

        `address` specifies the hostname/IP address of the NTP server.

        `burst` when enabled makes sure that if server is reachable, sends a burst of eight packets instead of one.
        This is designed to improve timekeeping quality with the server command.

        `iburst` when enabled speeds up the initial synchronization, taking seconds rather than minutes.

        `prefer` marks the specified server as preferred. When all other things are equal, this host is chosen
        for synchronization acquisition with the server command. It is recommended that they be used for servers with
        time monitoring hardware.

        `minpoll` is minimum polling time in seconds. It must be a power of 2 and less than `maxpoll`.

        `maxpoll` is maximum polling time in seconds. It must be a power of 2 and greater than `minpoll`.

        `force` when enabled forces the addition of NTP server even if it is currently unreachable.
        """
        await self.clean(data, 'ntpserver_create')

        data['id'] = await self.middleware.call(
            'datastore.insert', self._config.datastore, data,
            {'prefix': self._config.datastore_prefix})

        await self.middleware.call('service.restart', 'ntpd')

        return await self.get_instance(data['id'])

    @accepts(
        Int('id'),
        Patch(
            'ntp_create',
            'ntp_update',
            ('attr', {'update': True})
        )
    )
    async def do_update(self, id, data):
        """
        Update NTP server of `id`.
        """
        old = await self._get_instance(id)

        new = old.copy()
        new.update(data)

        await self.clean(new, 'ntpserver_update')

        await self.middleware.call(
            'datastore.update', self._config.datastore, id, new,
            {'prefix': self._config.datastore_prefix})

        await self.middleware.call('service.restart', 'ntpd')

        return await self.get_instance(id)

    async def do_delete(self, id):
        """
        Delete NTP server of `id`.
        """
        response = await self.middleware.call('datastore.delete', self._config.datastore, id)

        await self.middleware.call('service.restart', 'ntpd')

        return response

    @staticmethod
    @private
    def test_ntp_server(addr):
        client = ntplib.NTPClient()
        server_alive = False
        try:
            response = client.request(addr)
            if response.version:
                server_alive = True
        except Exception:
            pass

        return server_alive

    @private
    async def clean(self, data, schema_name):
        verrors = ValidationErrors()
        maxpoll = data['maxpoll']
        minpoll = data['minpoll']
        force = data.pop('force', False)
        usable = True if await self.middleware.run_in_thread(
            self.test_ntp_server, data['address']) else False

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
