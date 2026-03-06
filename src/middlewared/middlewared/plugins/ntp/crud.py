from __future__ import annotations

import middlewared.sqlalchemy as sa
from middlewared.api.current import NTPServerCreate, NTPServerEntry, NTPServerUpdate
from middlewared.service import CRUDServicePart, ValidationErrors

from .peers import test_ntp_server


class NTPModel(sa.Model):
    __tablename__ = 'system_ntpserver'

    id = sa.Column(sa.Integer(), primary_key=True)
    ntp_address = sa.Column(sa.String(120))
    ntp_burst = sa.Column(sa.Boolean(), default=False)
    ntp_iburst = sa.Column(sa.Boolean(), default=True)
    ntp_prefer = sa.Column(sa.Boolean(), default=False)
    ntp_minpoll = sa.Column(sa.Integer(), default=6)
    ntp_maxpoll = sa.Column(sa.Integer(), default=10)


class NTPServerServicePart(CRUDServicePart[NTPServerEntry]):
    _datastore = 'system.ntpserver'
    _datastore_prefix = 'ntp_'
    _entry = NTPServerEntry

    async def do_create(self, data: NTPServerCreate) -> NTPServerEntry:
        await self.validate(data, 'ntpserver_create', force=data.force)
        entry = await self._create(data.model_dump(exclude={'force'}))
        await (await self.middleware.call('service.control', 'RESTART', 'ntpd')).wait(raise_error=True)
        return entry

    async def do_update(self, id_: int, data: NTPServerUpdate) -> NTPServerEntry:
        old = await self.get_instance(id_)
        force = data.model_dump(exclude_unset=True).get('force', False)
        new = old.updated(data)
        await self.validate(new, 'ntpserver_update', force=force)
        entry = await self._update(id_, new.model_dump())
        await (await self.middleware.call('service.control', 'RESTART', 'ntpd')).wait(raise_error=True)
        return entry

    async def do_delete(self, id_: int) -> None:
        await self._delete(id_)
        await (await self.middleware.call('service.control', 'RESTART', 'ntpd')).wait(raise_error=True)

    async def validate(self, data: NTPServerEntry, schema_name: str, *, force: bool = False) -> None:
        verrors = ValidationErrors()
        if not force:
            if not await self.to_thread(test_ntp_server, data.address):
                verrors.add(
                    f'{schema_name}.address',
                    'Server could not be reached. Check "Force" to continue regardless.'
                )

        if not data.maxpoll > data.minpoll:
            verrors.add(f'{schema_name}.maxpoll', 'Max Poll should be higher than Min Poll')

        verrors.check()
