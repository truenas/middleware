import errno
import subprocess

from middlewared.schema import accepts, Bool, Dict, Int, Patch, returns, Str, ValidationErrors
from middlewared.service import CRUDService, private
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


TUNABLE_TYPES = ['SYSCTL', 'UDEV']


class TunableService(CRUDService):
    class Config:
        datastore = 'system.tunable'
        datastore_prefix = 'tun_'
        cli_namespace = 'system.tunable'

    SYSCTLS = set()

    ENTRY = Patch(
        'tunable_create', 'tunable_entry',
        ('add', Int('id')),
    )

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
        with open(f'/proc/sys/{var.replace(".", "/")}', 'w') as f:
            f.write(value)

    @private
    def reset_sysctl(self, tunable):
        self.set_sysctl(tunable['var'], tunable['orig_value'])

    @private
    async def handle_tunable_change(self, tunable):
        if tunable['type'] == 'UDEV':
            await self.middleware.call('etc.generate', 'udev')
            await run(['udevadm', 'control', '-R'])

    @accepts()
    @returns(Dict('tunable_type_choices', *[Str(k, enum=[k]) for k in TUNABLE_TYPES]))
    async def tunable_type_choices(self):
        """
        Retrieve the supported tunable types that can be changed.
        """
        return {k: k for k in TUNABLE_TYPES}

    @accepts(Dict(
        'tunable_create',
        Str('type', enum=TUNABLE_TYPES, default='SYSCTL', required=True),
        Str('var', required=True),
        Str('value', required=True),
        Str('comment', default=''),
        Bool('enabled', default=True),
        register=True
    ))
    async def do_create(self, data):
        """
        Create a tunable.

        If `type` is `SYSCTL` then `var` is a sysctl name (e.g. `kernel.watchdog`) and `value` is its corresponding
        value (e.g. `0`).

        If `type` is `UDEV` then `var` is an udev rules file name (e.g. `10-disable-usb`, `.rules` suffix will be
        appended automatically) and `value` is its contents (e.g. `BUS=="usb", OPTIONS+="ignore_device"`).
        """
        verrors = ValidationErrors()

        if await self.middleware.call('tunable.query', [('var', '=', data['var'])]):
            verrors.add('tunable_create.var', f'Tunable {data["var"]!r} already exists in database.', errno.EEXIST)

        if data['type'] == 'SYSCTL':
            if data['var'] not in await self.middleware.call('tunable.get_sysctls'):
                verrors.add('tunable_create.var', f'Sysctl {data["var"]!r} does not exist in kernel.', errno.ENOENT)

        if data['type'] == 'UDEV':
            if 'truenas' in data['var']:
                verrors.add(
                    'tunable_create.var',
                    'Udev rules with `truenas` in their name are not allowed.',
                    errno.EPERM,
                )

        verrors.check()

        data['orig_value'] = ''
        if data['type'] == 'SYSCTL':
            data['orig_value'] = await self.middleware.call('tunable.get_sysctl', data['var'])

        id = await self.middleware.call(
            'datastore.insert', self._config.datastore, data, {'prefix': self._config.datastore_prefix}
        )

        if data['type'] == 'SYSCTL':
            await self.middleware.call('etc.generate', 'sysctl')

            if data['enabled']:
                await self.middleware.call('tunable.set_sysctl', data['var'], data['value'])
        else:
            await self.handle_tunable_change(data)

        return await self.get_instance(id)

    @accepts(
        Int('id', required=True),
        Patch(
            'tunable_create',
            'tunable_update',
            ('rm', {'name': 'type'}),
            ('rm', {'name': 'var'}),
            ('attr', {'update': True}),
        )
    )
    async def do_update(self, id, data):
        """
        Update Tunable of `id`.
        """
        old = await self.get_instance(id)

        new = old.copy()
        new.update(data)
        if old == new:
            # nothing updated so return early
            return old

        await self.middleware.call(
            'datastore.update', self._config.datastore, id, new, {'prefix': self._config.datastore_prefix}
        )

        if new['type'] == 'SYSCTL':
            await self.middleware.call('etc.generate', 'sysctl')

            if new['enabled']:
                await self.middleware.call('tunable.set_sysctl', new['var'], new['value'])
            else:
                await self.middleware.call('tunable.reset_sysctl', new)
        else:
            await self.handle_tunable_change(new)

        return await self.get_instance(id)

    async def do_delete(self, id):
        """
        Delete Tunable of `id`.
        """
        entry = await self.get_instance(id)

        await self.middleware.call('datastore.delete', self._config.datastore, entry['id'])

        if entry['type'] == 'SYSCTL':
            await self.middleware.call('etc.generate', 'sysctl')

            await self.middleware.call('tunable.reset_sysctl', entry)
        else:
            await self.handle_tunable_change(entry)
