from __future__ import annotations

import errno
import os
from typing import Any

import middlewared.sqlalchemy as sa
from middlewared.api.current import TunableCreate, TunableEntry, TunableUpdate
from middlewared.service import CRUDServicePart, ValidationErrors
from middlewared.utils import run
from .utils import (
    get_sysctl,
    get_sysctls,
    reset_sysctl,
    reset_zfs_parameter,
    set_sysctl,
    set_zfs_parameter,
    zfs_parameter_path,
    zfs_parameter_value,
)


class TunableModel(sa.Model):
    __tablename__ = 'system_tunable'

    id = sa.Column(sa.Integer(), primary_key=True)
    tun_type = sa.Column(sa.String(20))
    tun_var = sa.Column(sa.String(128), unique=True)
    tun_value = sa.Column(sa.String(512))
    tun_orig_value = sa.Column(sa.String(512))
    tun_comment = sa.Column(sa.String(100))
    tun_enabled = sa.Column(sa.Boolean(), default=True)


class TunableServicePart(CRUDServicePart[TunableEntry]):
    _datastore = 'system.tunable'
    _datastore_prefix = 'tun_'
    _entry = TunableEntry

    def compress(self, data: dict[str, Any]) -> dict[str, Any]:
        data.pop('update_initramfs', None)
        return data

    async def do_create(self, data: TunableCreate) -> TunableEntry:
        update_initramfs = data.update_initramfs

        verrors = ValidationErrors()

        if await self.query([('var', '=', data.var)]):
            verrors.add(
                'tunable_create.var',
                f'Tunable {data.var!r} already exists in database.',
                errno.EEXIST,
            )

        if data.type == 'SYSCTL':
            if data.var not in await self.to_thread(get_sysctls):
                verrors.add(
                    'tunable_create.var',
                    f'Sysctl {data.var!r} does not exist in kernel.',
                    errno.ENOENT,
                )

        if data.type == 'UDEV' and 'truenas' in data.var:
            verrors.add(
                'tunable_create.var',
                'Udev rules with `truenas` in their name are not allowed.',
                errno.EPERM,
            )

        if data.type == 'ZFS':
            if not await self.to_thread(os.path.exists, zfs_parameter_path(data.var)):
                verrors.add(
                    'tunable_create.var',
                    f'ZFS module does not accept {data.var!r} parameter.',
                    errno.ENOENT,
                )

        verrors.check()

        orig_value = ''
        if data.type == 'SYSCTL':
            orig_value = await self.to_thread(get_sysctl, data.var)
        elif data.type == 'ZFS':
            orig_value = await self.to_thread(zfs_parameter_value, data.var)

        create_data = data.model_dump()
        create_data['orig_value'] = orig_value

        entry = await self._create(create_data)

        try:
            if entry.type == 'SYSCTL':
                if entry.enabled:
                    await self.middleware.call('etc.generate', 'sysctl')
                    await self.to_thread(set_sysctl, entry.var, entry.value)
            elif entry.type == 'ZFS':
                if entry.enabled:
                    await self.to_thread(set_zfs_parameter, entry.var, entry.value)
                    if update_initramfs:
                        await self.middleware.call('boot.update_initramfs')
            else:
                await self._handle_tunable_change(entry)
        except Exception:
            await self._delete(entry.id)
            raise

        return entry

    async def do_update(self, id_: int, data: TunableUpdate) -> TunableEntry:
        old = await self.get_instance(id_)

        update_data = data.model_dump()
        update_initramfs: bool = update_data.get('update_initramfs', True)

        new = old.updated(data)

        if old.model_dump(exclude={'update_initramfs'}) == new.model_dump(exclude={'update_initramfs'}):
            return old

        await self._update(id_, new.model_dump())

        try:
            if new.type == 'SYSCTL':
                await self.middleware.call('etc.generate', 'sysctl')

                if new.enabled:
                    await self.to_thread(set_sysctl, new.var, new.value)
                else:
                    await self.to_thread(reset_sysctl, new)
            elif new.type == 'ZFS':
                if new.enabled:
                    await self.to_thread(set_zfs_parameter, new.var, new.value)
                else:
                    await self.to_thread(reset_zfs_parameter, new)

                if update_initramfs:
                    await self.middleware.call('boot.update_initramfs')
            else:
                await self._handle_tunable_change(new)
        except Exception:
            await self._update(id_, old.model_dump())
            raise

        return await self.get_instance(id_)

    async def do_delete(self, id_: int) -> None:
        entry = await self.get_instance(id_)

        await self._delete(entry.id)

        if entry.type == 'SYSCTL':
            await self.middleware.call('etc.generate', 'sysctl')
            await self.to_thread(reset_sysctl, entry)
        elif entry.type == 'ZFS':
            await self.to_thread(reset_zfs_parameter, entry)
            await self.middleware.call('boot.update_initramfs')
        else:
            await self._handle_tunable_change(entry)

    async def _handle_tunable_change(self, entry: TunableEntry) -> None:
        if entry.type == 'UDEV':
            await self.middleware.call('etc.generate', 'udev')
            await run(['udevadm', 'control', '-R'])
