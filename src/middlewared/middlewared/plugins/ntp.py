import errno
import subprocess

import ntplib

import middlewared.sqlalchemy as sa
from middlewared.plugins.ntp_.enums import Mode, State
from middlewared.schema import Bool, Dict, Int, IPAddr, Patch, Str, accepts
from middlewared.service import (CRUDService, ValidationErrors, filterable,
                                 private)
from middlewared.service_exception import CallError
from middlewared.utils import filter_list


class NTPModel(sa.Model):
    __tablename__ = 'system_ntpserver'

    id = sa.Column(sa.Integer(), primary_key=True)
    ntp_address = sa.Column(sa.String(120))
    ntp_burst = sa.Column(sa.Boolean(), default=False)
    ntp_iburst = sa.Column(sa.Boolean(), default=True)
    ntp_prefer = sa.Column(sa.Boolean(), default=False)
    ntp_minpoll = sa.Column(sa.Integer(), default=6)
    ntp_maxpoll = sa.Column(sa.Integer(), default=10)


class NTPPeer:
    def __init__(self, initial_data):
        self._mode = Mode.from_str(initial_data['mode'])
        self._state = State.from_str(initial_data['state'])
        self._remote = initial_data['remote']
        IPAddr().validate(self._remote)
        self._stratum = initial_data['stratum']
        self._poll_interval = initial_data['poll_interval']
        self._reach = initial_data['reach']
        self._lastrx = initial_data['lastrx']
        self._offset = initial_data['offset']
        self._offset_measured = initial_data['offset_measured']
        self._jitter = initial_data['jitter']

    @classmethod
    def from_chronyc_sources(cls, mode, state, remote, stratum, poll_interval, reach, lastrx, offset, offset_measured, jitter):
        """Construct a NTPPeer object from one line of output from chronyc sources -c"""
        # From chronyc man page (https://chrony.tuxfamily.org/doc/4.3/chronyc.html)
        # -c This option enables printing of reports in a comma-separated values (CSV) format. Reverse DNS lookups
        # will be disabled, time will be printed as number of seconds since the epoch, and values in seconds will
        # not be converted to other units.
        return cls({
            'mode': mode,
            'state': state,
            'remote': remote,
            'stratum': int(stratum),
            'poll_interval': int(poll_interval),
            'reach': int(reach, 8),
            'lastrx': int(lastrx),
            'offset': float(offset),
            'offset_measured': float(offset_measured),
            'jitter': float(jitter)
        })

    def asdict(self):
        return {
            'mode': str(self._mode),
            'state': str(self._state),
            'remote': self._remote,
            'stratum': self._stratum,
            'poll_interval': self._poll_interval,
            'reach': self._reach,
            'lastrx': self._lastrx,
            'offset': self._offset,
            'offset_measured': self._offset_measured,
            'jitter': self._jitter,
            'active': self.is_active(),
        }

    def is_active(self):
        return self._state.is_active()

    def __str__(self):
        return f"{self._mode}: {self._state} [{self._remote}]"

    @property
    def remote(self):
        return self._remote

    @property
    def offset_in_secs(self):
        return self._offset


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
        old = await self.get_instance(id)

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
    @filterable
    def peers(self, filters, options):
        peers = []

        if not self.middleware.call_sync('system.ready'):
            return peers

        resp = subprocess.run(['chronyc', '-c', 'sources'], capture_output=True)
        if resp.returncode != 0 or resp.stderr:
            errmsg = resp.stderr.decode().strip()
            raise CallError(
                errmsg,
                errno.ECONNREFUSED if "Connection refused" in errmsg else errno.EFAULT
            )

        for entry in resp.stdout.decode().splitlines():
            values = entry.split(',')
            if len(values) != 10:
                self.logger.debug("Unexpected peer result: %s", entry)
                continue

            try:
                peer = NTPPeer.from_chronyc_sources(*values)
                # mode = Mode.from_str(values[0])
                # state = State.from_str(values[1])
            except NotImplementedError as e:
                self.logger.debug(f"Unexpected item {e}: {entry}")
                continue
            except ValidationErrors as e:
                self.logger.debug("Invalid remote address: %s", e)
                continue

            peers.append(peer.asdict())

        return filter_list(peers, filters, options)

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
