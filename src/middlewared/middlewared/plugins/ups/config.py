from __future__ import annotations

import os
import re
import typing

import middlewared.sqlalchemy as sa
from middlewared.api.current import UPSEntry, UPSUpdate
from middlewared.service import SystemServicePart, ValidationErrors


class UPSModel(sa.Model):
    __tablename__ = 'services_ups'

    id = sa.Column(sa.Integer(), primary_key=True)
    ups_mode = sa.Column(sa.String(6), default='master')
    ups_identifier = sa.Column(sa.String(120), default='ups')
    ups_remotehost = sa.Column(sa.String(50))
    ups_remoteport = sa.Column(sa.Integer(), default=3493)
    ups_driver = sa.Column(sa.String(120))
    ups_port = sa.Column(sa.String(120))
    ups_options = sa.Column(sa.Text())
    ups_optionsupsd = sa.Column(sa.Text())
    ups_description = sa.Column(sa.String(120))
    ups_shutdown = sa.Column(sa.String(120), default='batt')
    ups_shutdowntimer = sa.Column(sa.Integer(), default=30)
    ups_monuser = sa.Column(sa.String(50), default='upsmon')
    ups_monpwd = sa.Column(sa.EncryptedText(), default='fixmepass')
    ups_extrausers = sa.Column(sa.Text())
    ups_rmonitor = sa.Column(sa.Boolean(), default=False)
    ups_powerdown = sa.Column(sa.Boolean(), default=False)
    ups_nocommwarntime = sa.Column(sa.Integer(), nullable=True)
    ups_hostsync = sa.Column(sa.Integer(), default=15)
    ups_shutdowncmd = sa.Column(sa.String(255), nullable=True)


class UPSServicePart(SystemServicePart[UPSEntry]):
    _datastore = 'services.ups'
    _datastore_prefix = 'ups_'
    _entry = UPSEntry
    _service = 'ups'
    _service_verb = 'restart'

    async def do_update(self, data: UPSUpdate) -> UPSEntry:
        old = await self.config()
        new = old.updated(data)

        await self._validate(new)

        if old != new:
            if new.identifier != old.identifier:
                await self.middleware.call('ups.dismiss_alerts')

            update = data.model_dump()
            if 'mode' in update:
                update['mode'] = update['mode'].lower()
            if 'shutdown' in update:
                update['shutdown'] = update['shutdown'].lower()

            await self._update_service(old.id, update)

        return await self.config()

    async def _validate(self, data: UPSEntry) -> None:
        verrors = ValidationErrors()

        if data.driver:
            if data.driver not in (await self.call2(self.s.ups.driver_choices)):
                verrors.add(
                    'ups_update.driver',
                    'Driver selected does not match local machine\'s driver list'
                )

        if data.port:
            adv_config = await self.middleware.call('system.advanced.config')
            serial_port = os.path.join('/dev', adv_config['serialport'])
            if adv_config['serialconsole'] and serial_port == data.port:
                verrors.add(
                    'ups_update.port',
                    'UPS port must be different then the port specified for '
                    'serial port for console in system advanced settings'
                )

        if data.identifier:
            if not re.search(r'^[a-z0-9\.\-_]+$', data.identifier, re.I):
                verrors.add(
                    'ups_update.identifier',
                    'Use alphanumeric characters, ".", "-" and "_"'
                )

        for field, value in [('monpwd', data.monpwd), ('monuser', data.monuser)]:
            if re.search(r'[ #]', value, re.I):
                verrors.add(
                    f'ups_update.{field}',
                    'Spaces or number signs are not allowed.'
                )

        if data.mode == 'MASTER':
            if not data.port:
                verrors.add('ups_update.port', 'This field is required')
            if not data.driver:
                verrors.add('ups_update.driver', 'This field is required')
        else:
            if not data.remotehost:
                verrors.add(
                    'ups_update.remotehost',
                    'This field is required'
                )

        verrors.check()

    async def extend(self, data: dict[str, typing.Any]) -> dict[str, typing.Any]:
        data['mode'] = data['mode'].upper()
        data['shutdown'] = data['shutdown'].upper()
        host = 'localhost' if data['mode'] == 'MASTER' else data['remotehost']
        data['complete_identifier'] = f'{data["identifier"]}@{host}:{data["remoteport"]}'
        return data
