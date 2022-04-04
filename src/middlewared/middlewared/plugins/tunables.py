import errno
import subprocess

from middlewared.schema import accepts, Bool, Dict, Int, Patch, returns, Str, ValidationErrors
from middlewared.service import CRUDService, private
import middlewared.sqlalchemy as sa


class TunableModel(sa.Model):
    __tablename__ = 'system_tunable'

    id = sa.Column(sa.Integer(), primary_key=True)
    tun_value = sa.Column(sa.String(512))
    tun_type = sa.Column(sa.String(20), default='loader')
    tun_comment = sa.Column(sa.String(100))
    tun_enabled = sa.Column(sa.Boolean(), default=True)
    tun_var = sa.Column(sa.String(128), unique=True)


TUNABLE_TYPES = ['SYSCTL']


class TunableService(CRUDService):
    class Config:
        datastore = 'system.tunable'
        datastore_prefix = 'tun_'
        cli_namespace = 'system.tunable'

    SYSTEM_DEFAULTS = {}

    ENTRY = Patch(
        'tunable_create', 'tunable_entry',
        ('add', Int('id')),
    )

    @private
    def get_system_defaults(self):
        if not TunableService.SYSTEM_DEFAULTS:
            lines = subprocess.run(['sysctl', '-a'], stdout=subprocess.PIPE)
            for line in filter(lambda x: x, lines.stdout.decode().split('\n')):
                var, value = line.split(' = ')
                TunableService.SYSTEM_DEFAULTS[var] = value.strip()
        return TunableService.SYSTEM_DEFAULTS

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
        Str('type', enum=TUNABLE_TYPES, required=True),
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
            verrors.add('tunable.create', f'Tunable {data["var"]!r} already exists.', errno.EEXIST)

        if data['var'] not in TunableService.SYSTEM_DEFAULTS:
            verrors.add('tunable.create', f'Tunable {data["var"]!r} does not exist.', errno.ENOENT)

        verrors.check()

        if (comment := data.get('comment', '').strip()):
            data['comment'] = comment

        _id = await self.middleware.call(
            'datastore.insert', self._config.datastore, data, {'prefix': self._config.datastore_prefix}
        )
        await self.middleware.call('service.restart', 'sysctl')
        return await self.get_instance(_id)

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

        if (comment := data.get('comment', '').strip()):
            new['comment'] = comment

        _id = await self.middleware.call(
            'datastore.update', self._config.datastore, id, new, {'prefix': self._config.datastore_prefix}
        )
        await self.middleware.call('service.restart', 'sysctl')
        return await self.get_instance(_id)

    async def do_delete(self, _id):
        """
        Delete Tunable of `id`.
        """
        await self.get_instance(_id)
        await self.middleware.call('datastore.delete', self._config.datastore, _id)
        await self.middleware.call('service.restart', 'sysctl')
