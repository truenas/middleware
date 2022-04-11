import errno
import subprocess
from collections import deque

from middlewared.schema import accepts, Bool, Dict, Int, Patch, returns, Str, ValidationErrors
from middlewared.service import CRUDService, private
import middlewared.sqlalchemy as sa


class TunableModel(sa.Model):
    __tablename__ = 'system_tunable'

    id = sa.Column(sa.Integer(), primary_key=True)
    tun_value = sa.Column(sa.String(512))
    tun_orig_value = sa.Column(sa.String(512))
    tun_type = sa.Column(sa.String(20))
    tun_comment = sa.Column(sa.String(100))
    tun_enabled = sa.Column(sa.Boolean(), default=True)
    tun_var = sa.Column(sa.String(128), unique=True)


TUNABLE_TYPES = ['SYSCTL']


class TunableService(CRUDService):
    class Config:
        datastore = 'system.tunable'
        datastore_prefix = 'tun_'
        cli_namespace = 'system.tunable'

    SYSTEM_TUNABLES = deque()

    ENTRY = Patch(
        'tunable_create', 'tunable_entry',
        ('add', Int('id')),
    )

    @private
    def get_system_tunables(self):
        if not TunableService.SYSTEM_TUNABLES:
            tunables = subprocess.run(['sysctl', '-aN'], stdout=subprocess.PIPE)
            for tunable in filter(lambda x: x, tunables.stdout.decode().split('\n')):
                TunableService.SYSTEM_TUNABLES.append(tunable)
        return TunableService.SYSTEM_TUNABLES

    @private
    def get_or_set(self, var, value=None):
        with open(f'/proc/sys/{var.replace(".", "/")}', 'r' if not value else 'w') as f:
            return f.read().strip() if not value else f.write(value)

    @accepts()
    @returns(Dict('tunable_type_choices', *[Str(k, enum=[k]) for k in TUNABLE_TYPES]))
    async def tunable_type_choices(self):
        """
        Retrieve the supported tunable types that can be changed.
        """
        return {k: k for k in TUNABLE_TYPES}

    @accepts(Dict(
        'tunable_create',
        Str('var', required=True),
        Str('value', required=True),
        Str('type', enum=TUNABLE_TYPES, default='SYSCTL', required=True),
        Str('comment'),
        Bool('enabled', default=True),
        register=True
    ))
    async def do_create(self, data):
        """
        Create a Tunable.
        """
        verrors = ValidationErrors()
        if await self.middleware.call('tunable.query', [('var', '=', data['var'])]):
            verrors.add('tunable.create', f'Tunable {data["var"]!r} already exists in database.', errno.EEXIST)

        if data['var'] not in await self.middleware.call('tunable.get_system_tunables'):
            verrors.add('tunable.create', f'Tunable {data["var"]!r} does not exist in kernel.', errno.ENOENT)

        if data['type'] not in await self.middleware.call('tunable.tunable_type_choices'):
            verrors.add('tunable.create', 'Invalid tunable type.')

        verrors.check()

        data['orig_value'] = await self.middleware.call('tunable.get_or_set', data['var'])

        if (comment := data.get('comment', '').strip()):
            data['comment'] = comment

        _id = await self.middleware.call(
            'datastore.insert', self._config.datastore, data, {'prefix': self._config.datastore_prefix}
        )
        await self.middleware.call('service.restart', 'sysctl')
        return await self.get_instance(_id)

    @accepts(
        Int('id', required=True),
        Patch(
            'tunable_create',
            'tunable_update',
            ('rm', 'var'),
            ('rm', 'type'),
            ('attr', {'update': True}),
        )
    )
    async def do_update(self, _id, data):
        """
        Update Tunable of `id`.
        """
        old = await self.get_instance(_id)

        new = old.copy()
        new.update(data)
        if old == new:
            # nothing updated so return early
            return old

        if (comment := data.get('comment', '').strip()) and comment != new['comment']:
            new['comment'] = comment

        if not new['enabled']:
            await self.middleware.run_in_thread(self.get_or_set, new['var'], new['orig_value'])

        _id = await self.middleware.call(
            'datastore.update', self._config.datastore, _id, new, {'prefix': self._config.datastore_prefix}
        )
        await self.middleware.call('service.restart', 'sysctl')
        return await self.get_instance(_id)

    async def do_delete(self, _id):
        """
        Delete Tunable of `id`.
        """
        entry = await self.get_instance(_id)

        # before we delete from db, let's set the tunable back to it's original value
        await self.middleware.run_in_thread(self.get_or_set, entry['var'], entry['orig_value'])

        await self.middleware.call('datastore.delete', self._config.datastore, entry['id'])
        await self.middleware.call('service.restart', 'sysctl')
