from __future__ import annotations

from middlewared.api.current import NTPServerCreate, NTPServerEntry, NTPServerUpdate
from middlewared.service import CallError, CRUDServicePart, ValidationErrors
import middlewared.sqlalchemy as sa
from middlewared.utils.ntp import NTSKEError, probe_nts_ke
from middlewared.utils.types import AuditCallback

from .advice import domain_clock_advice
from .peers import test_ntp_server

# chrony repeats NTS key establishment at least every `ntsrefresh` seconds (four weeks by default), and has to poll a
# source more often than that or it keeps re-establishing keys and never gets as far as exchanging NTP packets.
# 2 ** 21 seconds is a little over 24 days.
NTS_MAX_POLL = 21


class NTPModel(sa.Model):
    __tablename__ = 'system_ntpserver'

    id = sa.Column(sa.Integer(), primary_key=True)
    ntp_address = sa.Column(sa.String(120))
    ntp_burst = sa.Column(sa.Boolean(), default=False)
    ntp_iburst = sa.Column(sa.Boolean(), default=True)
    ntp_prefer = sa.Column(sa.Boolean(), default=False)
    ntp_minpoll = sa.Column(sa.Integer(), default=6)
    ntp_maxpoll = sa.Column(sa.Integer(), default=10)
    ntp_nts = sa.Column(sa.Boolean(), default=False)


class NTPServerServicePart(CRUDServicePart[NTPServerEntry]):
    _datastore = 'system.ntpserver'
    _datastore_prefix = 'ntp_'
    _entry = NTPServerEntry

    async def do_create(self, data: NTPServerCreate) -> NTPServerEntry:
        await self.validate(data, 'ntpserver_create', force=data.force)
        entry = await self._create(data.model_dump(exclude={'force'}))
        await (await self.call2(self.s.service.control, 'RESTART', 'ntpd')).wait(raise_error=True)
        return entry

    async def do_update(self, audit_callback: AuditCallback, id_: int, data: NTPServerUpdate) -> NTPServerEntry:
        old = await self.get_instance(id_)
        audit_callback(old.address)
        force = data.model_dump(exclude_unset=True).get('force', False)
        new = old.updated(data)
        await self.validate(new, 'ntpserver_update', force=force)
        entry = await self._update(id_, new.model_dump())
        await (await self.call2(self.s.service.control, 'RESTART', 'ntpd')).wait(raise_error=True)
        return entry

    async def do_delete(self, audit_callback: AuditCallback, id_: int) -> None:
        entry = await self.get_instance(id_)
        audit_callback(entry.address)
        if entry.nts and await self._is_last_required_nts_server(id_):
            raise CallError(
                'The last NTS server cannot be deleted while the system security configuration requires NTS.'
            )

        await self._delete(id_)
        await (await self.call2(self.s.service.control, 'RESTART', 'ntpd')).wait(raise_error=True)

    async def validate(self, data: NTPServerEntry, schema_name: str, *, force: bool = False) -> None:
        verrors = ValidationErrors()
        if not data.nts and await self._nts_required():
            # chronyd would never use it (`authselectmode require`)
            verrors.add(
                f'{schema_name}.nts',
                'NTS is required by the system security configuration, so servers without NTS are never used.'
            )
            verrors.check()

        if not force:
            if data.nts:
                await self._validate_nts(data.address, schema_name, verrors)
            elif not await self.to_thread(test_ntp_server, data.address):
                verrors.add(
                    f'{schema_name}.address',
                    'Server could not be reached. Check "Force" to continue regardless.'
                )

        if not data.maxpoll > data.minpoll:
            verrors.add(f'{schema_name}.maxpoll', 'Max Poll should be higher than Min Poll')

        if data.nts and data.maxpoll > NTS_MAX_POLL:
            verrors.add(f'{schema_name}.maxpoll', f'Max Poll can not be higher than {NTS_MAX_POLL} with NTS')

        verrors.check()

    async def domain_clock_advice(self) -> str:
        """What to tell an administrator whose clock disagrees with the domain controller's, given the time sources."""
        nts_servers = [server.address for server in await self.query([['nts', '=', True]])]
        return domain_clock_advice(nts_servers, await self._nts_required())

    async def _nts_required(self) -> bool:
        return (await self.call2(self.s.system.security.config)).require_nts

    async def _is_last_required_nts_server(self, id_: int) -> bool:
        """Whether `system.security` requires NTS and the server `id_` is the only NTS server configured."""
        if not await self._nts_required():
            return False

        return not await self.query([['nts', '=', True], ['id', '!=', id_]])

    async def _validate_nts(self, address: str, schema_name: str, verrors: ValidationErrors) -> None:
        try:
            result = await self.to_thread(probe_nts_ke, address)
        except NTSKEError as e:
            verrors.add(
                f'{schema_name}.nts',
                f'NTS key establishment with {address} failed: {e}. Check "Force" to continue regardless.'
            )
            return

        # The key establishment server may send NTP to another host or port
        ntp_host = result.server or address
        ntp_port = result.port or 123
        if not await self.to_thread(test_ntp_server, ntp_host, ntp_port):
            verrors.add(
                f'{schema_name}.address',
                f'NTS key establishment succeeded, but NTP server {ntp_host} (UDP port {ntp_port}) could not be '
                'reached. Check "Force" to continue regardless.'
            )
