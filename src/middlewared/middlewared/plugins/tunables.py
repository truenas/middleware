import contextlib
import errno
import os
import subprocess

from middlewared.api import api_method
from middlewared.api.current import (
    TunableEntry, TunableCreateArgs, TunableCreateResult, TunableUpdateArgs, TunableUpdateResult, TunableDeleteArgs,
    TunableDeleteResult, TunableTunableTypeChoicesArgs, TunableTunableTypeChoicesResult
)
from middlewared.service import CRUDService, ValidationErrors, job, private
import middlewared.sqlalchemy as sa
from middlewared.utils import run


class TunableModel(sa.Model):
    __tablename__ = 'system_tunable'

    id = sa.Column(sa.Integer(), primary_key=True)
    tun_type = sa.Column(sa.String(20))
    tun_var = sa.Column(sa.String(128), unique=True)
    tun_value = sa.Column(sa.String(512))
    tun_orig_value = sa.Column(sa.String(512))
    tun_comment = sa.Column(sa.String(100))
    tun_enabled = sa.Column(sa.Boolean(), default=True)


TUNABLE_TYPES = ['SYSCTL', 'UDEV', 'ZFS']


def zfs_parameter_path(name):
    return f'/sys/module/zfs/parameters/{name}'


def zfs_parameter_value(name):
    with open(zfs_parameter_path(name)) as f:
        return f.read().strip()


class TunableService(CRUDService):
    class Config:
        datastore = 'system.tunable'
        datastore_prefix = 'tun_'
        cli_namespace = 'system.tunable'
        role_prefix = 'SYSTEM_TUNABLE'
        entry = TunableEntry

    SYSCTLS = set()

    @private
    def get_sysctls(self):
        if not TunableService.SYSCTLS:
            tunables = subprocess.run(['sysctl', '-aN'], stdout=subprocess.PIPE)
            for tunable in filter(lambda x: x, tunables.stdout.decode().split('\n')):
                TunableService.SYSCTLS.add(tunable)
        return TunableService.SYSCTLS

    @private
    def get_sysctl(self, var):
        with open(f'/proc/sys/{var.replace(".", "/")}', 'r') as f:
            return f.read().strip()

    @private
    def set_sysctl(self, var, value):
        path = f'/proc/sys/{var.replace(".", "/")}'
        with contextlib.suppress(FileNotFoundError, PermissionError):
            with open(path, 'w') as f:
                f.write(value)

    @private
    def reset_sysctl(self, tunable):
        self.set_sysctl(tunable['var'], tunable['orig_value'])

    @private
    def set_zfs_parameter(self, name, value):
        path = zfs_parameter_path(name)
        with contextlib.suppress(FileNotFoundError, PermissionError):
            with open(path, 'w') as f:
                f.write(value)

    @private
    def reset_zfs_parameter(self, tunable):
        self.set_zfs_parameter(tunable['var'], tunable['orig_value'])

    @private
    async def handle_tunable_change(self, tunable):
        if tunable['type'] == 'UDEV':
            await self.middleware.call('etc.generate', 'udev')
            await run(['udevadm', 'control', '-R'])

    @api_method(TunableTunableTypeChoicesArgs, TunableTunableTypeChoicesResult, authorization_required=False)
    async def tunable_type_choices(self):
        """
        Retrieve the supported tunable types that can be changed.
        """
        return {k: k for k in TUNABLE_TYPES}

    @api_method(TunableCreateArgs, TunableCreateResult, audit='Tunable create')
    @job(lock='tunable_crud')
    async def do_create(self, job, data):
        """
        Create a tunable.
        """
        update_initramfs = data.pop('update_initramfs')

        verrors = ValidationErrors()

        if await self.middleware.call('tunable.query', [('var', '=', data['var'])]):
            verrors.add('tunable_create.var', f'Tunable {data["var"]!r} already exists in database.', errno.EEXIST)

        if data['type'] == 'SYSCTL':
            if data['var'] not in await self.middleware.call('tunable.get_sysctls'):
                verrors.add('tunable_create.var', f'Sysctl {data["var"]!r} does not exist in kernel.', errno.ENOENT)

        if data['type'] == 'UDEV' and 'truenas' in data['var']:
            verrors.add(
                'tunable_create.var',
                'Udev rules with `truenas` in their name are not allowed.',
                errno.EPERM,
            )

        if data['type'] == 'ZFS':
            if not await self.middleware.run_in_thread(os.path.exists, zfs_parameter_path(data['var'])):
                verrors.add(
                    'tunable_create.var',
                    f'ZFS module does not accept {data["var"]!r} parameter.',
                    errno.ENOENT
                )

        verrors.check()

        data['orig_value'] = ''
        if data['type'] == 'SYSCTL':
            data['orig_value'] = await self.middleware.call('tunable.get_sysctl', data['var'])
        if data['type'] == 'ZFS':
            data['orig_value'] = await self.middleware.run_in_thread(zfs_parameter_value, data['var'])

        id_ = await self.middleware.call(
            'datastore.insert', self._config.datastore, data, {'prefix': self._config.datastore_prefix}
        )

        try:
            if data['type'] == 'SYSCTL':
                if data['enabled']:
                    await self.middleware.call('etc.generate', 'sysctl')
                    await self.middleware.call('tunable.set_sysctl', data['var'], data['value'])
            elif data['type'] == 'ZFS':
                if data['enabled']:
                    await self.middleware.call('tunable.set_zfs_parameter', data['var'], data['value'])
                    if update_initramfs:
                        await self.middleware.call('boot.update_initramfs')
            else:
                await self.handle_tunable_change(data)
        except Exception:
            await self.middleware.call('datastore.delete', self._config.datastore, id_)
            raise

        return await self.get_instance(id_)

    @api_method(TunableUpdateArgs, TunableUpdateResult, audit='Tunable update')
    @job(lock='tunable_crud')
    async def do_update(self, job, id_, data):
        """
        Update Tunable of `id`.
        """
        old = await self.get_instance(id_)

        update_initramfs = data.pop('update_initramfs', True)

        new = old.copy()
        new.update(data)
        if old == new:
            # nothing updated so return early
            return old

        await self.middleware.call(
            'datastore.update', self._config.datastore, id_, new, {'prefix': self._config.datastore_prefix}
        )

        try:
            if new['type'] == 'SYSCTL':
                await self.middleware.call('etc.generate', 'sysctl')

                if new['enabled']:
                    await self.middleware.call('tunable.set_sysctl', new['var'], new['value'])
                else:
                    await self.middleware.call('tunable.reset_sysctl', new)
            elif new['type'] == 'ZFS':
                if new['enabled']:
                    await self.middleware.call('tunable.set_zfs_parameter', new['var'], new['value'])
                else:
                    await self.middleware.call('tunable.reset_zfs_parameter', new)

                if update_initramfs:
                    await self.middleware.call('boot.update_initramfs')
            else:
                await self.handle_tunable_change(new)
        except Exception:
            await self.middleware.call(
                'datastore.update', self._config.datastore, id_, old, {'prefix': self._config.datastore_prefix}
            )
            raise

        return await self.get_instance(id_)

    @api_method(TunableDeleteArgs, TunableDeleteResult, audit='Tunable delete')
    @job(lock='tunable_crud')
    async def do_delete(self, job, id_):
        """
        Delete Tunable of `id`.
        """
        entry = await self.get_instance(id_)

        await self.middleware.call('datastore.delete', self._config.datastore, entry['id'])

        if entry['type'] == 'SYSCTL':
            await self.middleware.call('etc.generate', 'sysctl')

            await self.middleware.call('tunable.reset_sysctl', entry)
        elif entry['type'] == 'ZFS':
            await self.middleware.call('tunable.reset_zfs_parameter', entry)

            await self.middleware.call('boot.update_initramfs')
        else:
            await self.handle_tunable_change(entry)
