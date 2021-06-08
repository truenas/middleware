import re

from middlewared.schema import accepts, Bool, Dict, Int, Patch, returns, Str, ValidationErrors
from middlewared.service import CRUDService, private
import middlewared.sqlalchemy as sa
from middlewared.utils import run
from middlewared.validators import Match


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
        datastore_extend = 'tunable.upper'
        cli_namespace = 'system.tunable'

    def __init__(self, *args, **kwargs):
        super(TunableService, self).__init__(*args, **kwargs)
        self.__default_sysctl = {}

    ENTRY = Patch(
        'tunable_create', 'tunable_entry',
        ('add', Int('id')),
    )

    @private
    async def default_sysctl_config(self):
        return self.__default_sysctl

    @private
    async def get_default_value(self, oid):
        return self.__default_sysctl[oid]

    @private
    async def set_default_value(self, oid, value):
        if oid not in self.__default_sysctl:
            self.__default_sysctl[oid] = value

    @accepts()
    @returns(Dict(
        'tunable_type_choices',
        *[Str(k, enum=[k]) for k in TUNABLE_TYPES],
    ))
    async def tunable_type_choices(self):
        """
        Retrieve tunable type choices supported in the system
        """
        return {k: k for k in TUNABLE_TYPES}

    @accepts(Dict(
        'tunable_create',
        Str('var', validators=[Match(r'^[\w\.\-]+$')], required=True),
        Str('value', required=True),
        Str('type', enum=TUNABLE_TYPES, required=True),
        Str('comment'),
        Bool('enabled', default=True),
        register=True
    ))
    async def do_create(self, data):
        """
        Create a Tunable.

        `var` represents name of the sysctl/loader/rc variable.

        `type` for SCALE should be one of the following:
        1) SYSCTL     -     Configure `var` for sysctl(8)

        `type` for CORE/ENTERPRISE should be one of the following:
        1) LOADER     -     Configure `var` for loader(8)
        2) RC         -     Configure `var` for rc(8)
        3) SYSCTL     -     Configure `var` for sysctl(8)
        """
        await self.clean(data, 'tunable_create')
        await self.validate(data, 'tunable_create')
        await self.lower(data)

        data['id'] = await self.middleware.call(
            'datastore.insert',
            self._config.datastore,
            data,
            {'prefix': self._config.datastore_prefix}
        )

        await self.middleware.call('service.reload', data['type'])

        return await self._get_instance(data['id'])

    async def do_update(self, id, data):
        """
        Update Tunable of `id`.
        """
        old = await self.get_instance(id)

        new = old.copy()
        new.update(data)

        await self.clean(new, 'tunable_update', old=old)
        await self.validate(new, 'tunable_update')

        await self.lower(new)

        await self.middleware.call(
            'datastore.update',
            self._config.datastore,
            id,
            new,
            {'prefix': self._config.datastore_prefix}
        )

        if old['type'] == 'SYSCTL' and old['var'] in self.__default_sysctl and (
            old['var'] != new['var'] or old['type'] != new['type']
        ):
            default_value = self.__default_sysctl.pop(old['var'])
            cp = await run(['sysctl', f'{old["var"]}={default_value}'], check=False, encoding='utf8')
            if cp.returncode:
                self.middleware.logger.error(
                    'Failed to set sysctl %r -> %r : %s', old['var'], default_value, cp.stderr
                )

        await self.middleware.call('service.reload', new['type'])

        return await self.get_instance(id)

    async def do_delete(self, id):
        """
        Delete Tunable of `id`.
        """
        tunable = await self.get_instance(id)
        await self.lower(tunable)
        if tunable['type'] == 'sysctl':
            # Restore the default value, if it is possible.
            value_default = self.__default_sysctl.pop(tunable['var'], None)
            if value_default:
                cp = await run(['sysctl', f'{tunable["var"]}={value_default}'], check=False, encoding='utf8')
                if cp.returncode:
                    self.middleware.logger.error(
                        'Failed to set sysctl %r -> %r : %s', tunable['var'], value_default, cp.stderr
                    )

        response = await self.middleware.call(
            'datastore.delete',
            self._config.datastore,
            id
        )

        await self.middleware.call('service.reload', tunable['type'].lower())

        return response

    @private
    async def lower(self, data):
        data['type'] = data['type'].lower()

        return data

    @private
    async def upper(self, data):
        data['type'] = data['type'].upper()

        return data

    @private
    async def clean(self, tunable, schema_name, old=None):
        verrors = ValidationErrors()
        skip_dupe = False
        tun_comment = tunable.get('comment')
        tun_value = tunable['value']
        tun_var = tunable['var']

        if tun_comment is not None:
            tunable['comment'] = tun_comment.strip()

        if '"' in tun_value or "'" in tun_value:
            verrors.add(f"{schema_name}.value",
                        'Quotes in value are not allowed')

        if schema_name == 'tunable_update' and old:
            old_tun_var = old['var']

            if old_tun_var == tun_var:
                # They aren't trying to change to a new name, just updating
                skip_dupe = True

        if not skip_dupe:
            tun_vars = await self.middleware.call(
                'datastore.query', self._config.datastore, [('tun_var', '=',
                                                             tun_var)])

            if tun_vars:
                verrors.add(f"{schema_name}.value",
                            'This variable already exists')

        if verrors:
            raise verrors

        return tunable

    @private
    async def validate(self, tunable, schema_name):
        sysctl_re = \
            re.compile('[a-z][a-z0-9_]+\.([a-z0-9_]+\.)*[a-z0-9_]+', re.I)

        loader_re = \
            re.compile('[a-z][a-z0-9_]+\.*([a-z0-9_]+\.)*[a-z0-9_]+', re.I)

        verrors = ValidationErrors()
        tun_var = tunable['var'].lower()
        tun_type = tunable['type'].lower()

        if tun_type == 'loader' or tun_type == 'rc':
            err_msg = "Value can start with a letter and end with an alphanumeric. Aphanumeric and underscore" \
                      " characters are allowed"
        else:
            err_msg = 'Value can start with a letter and end with an alphanumeric. A period (.) once is a must.' \
                      ' Alphanumeric and underscore characters are allowed'

        if (
            tun_type in ('loader', 'rc') and
            not loader_re.match(tun_var)
        ) or (
            tun_type == 'sysctl' and
            not sysctl_re.match(tun_var)
        ):
            verrors.add(f"{schema_name}.var", err_msg)

        if verrors:
            raise verrors
