import errno
import subprocess
from typing import Literal

import middlewared.sqlalchemy as sa
from middlewared.api import api_method
from middlewared.api.base import BaseModel
from middlewared.api.current import (
    NTPServerEntry,
    NTPServerCreateArgs, NTPServerCreateResult,
    NTPServerUpdateArgs, NTPServerUpdateResult,
    NTPServerDeleteArgs, NTPServerDeleteResult,
)
from middlewared.plugins.ntp_.enums import Mode, State
from middlewared.service import CRUDService, ValidationErrors, filterable_api_method, private
from middlewared.service_exception import CallError
from middlewared.utils.filter_list import filter_list
from middlewared.plugins.ntp_.client import NTPClient


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
        self._stratum = initial_data['stratum']
        self._poll_interval = initial_data['poll_interval']
        self._reach = initial_data['reach']
        self._lastrx = initial_data['lastrx']
        self._offset = initial_data['offset']
        self._offset_measured = initial_data['offset_measured']
        self._jitter = initial_data['jitter']

    @classmethod
    def from_chronyc_sources(
        cls, mode, state, remote, stratum, poll_interval, reach, lastrx, offset, offset_measured, jitter
    ):
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


class NTPPeerEntry(BaseModel):
    mode: Literal['SERVER', 'PEER', 'LOCAL']
    state: Literal['BEST', 'SELECTED', 'SELECTABLE', 'FALSE_TICKER', 'TOO_VARIABLE', 'NOT_SELECTABLE']
    remote: str
    stratum: int
    poll_interval: int
    reach: int
    lastrx: int
    offset: float
    offset_measured: float
    jitter: float
    active: bool


class NTPServerService(CRUDService):
    class Config:
        namespace = 'system.ntpserver'
        datastore = 'system.ntpserver'
        datastore_prefix = 'ntp_'
        cli_namespace = 'system.ntp_server'
        entry = NTPServerEntry
        role_prefix = 'NETWORK_GENERAL'

    @api_method(NTPServerCreateArgs, NTPServerCreateResult)
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

        await (await self.middleware.call('service.control', 'RESTART', 'ntpd')).wait(raise_error=True)

        return await self.get_instance(data['id'])

    @api_method(NTPServerUpdateArgs, NTPServerUpdateResult)
    async def do_update(self, id_, data):
        """
        Update NTP server of `id`.
        """
        old = await self.get_instance(id_)

        new = old.copy()
        new.update(data)

        await self.clean(new, 'ntpserver_update')

        await self.middleware.call(
            'datastore.update', self._config.datastore, id_, new,
            {'prefix': self._config.datastore_prefix})

        await (await self.middleware.call('service.control', 'RESTART', 'ntpd')).wait(raise_error=True)

        return await self.get_instance(id_)

    @api_method(NTPServerDeleteArgs, NTPServerDeleteResult)
    async def do_delete(self, id_):
        """
        Delete NTP server of `id`.
        """
        response = await self.middleware.call('datastore.delete', self._config.datastore, id_)

        await (await self.middleware.call('service.control', 'RESTART', 'ntpd')).wait(raise_error=True)

        return response

    @staticmethod
    @private
    def test_ntp_server(addr):
        try:
            return bool(NTPClient(addr).make_request()['version'])
        except Exception:
            return False

    @filterable_api_method(item=NTPPeerEntry, private=True)
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
        if not data.pop('force', False):
            if not await self.middleware.run_in_thread(self.test_ntp_server, data['address']):
                verrors.add(
                    f'{schema_name}.address',
                    'Server could not be reached. Check "Force" to continue regardless.'
                )

        if not maxpoll > minpoll:
            verrors.add(f'{schema_name}.maxpoll',
                        'Max Poll should be higher than Min Poll')

        verrors.check()

        return data
