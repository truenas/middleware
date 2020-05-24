import re
import shlex
import subprocess

from middlewared.schema import (Bool, Dict, Int, Patch, Str, ValidationErrors,
                                accepts)
from middlewared.service import CRUDService, private
import middlewared.sqlalchemy as sa
from middlewared.validators import Match

TUNABLES_DEFAULT_FILE = '/data/tunables_default'


class TunableModel(sa.Model):
    __tablename__ = 'system_tunable'

    id = sa.Column(sa.Integer(), primary_key=True)
    tun_value = sa.Column(sa.String(512))
    tun_type = sa.Column(sa.String(20), default='loader')
    tun_comment = sa.Column(sa.String(100))
    tun_enabled = sa.Column(sa.Boolean(), default=True)
    tun_var = sa.Column(sa.String(128))


class TunableService(CRUDService):
    class Config:
        datastore = 'system.tunable'
        datastore_prefix = 'tun_'
        datastore_extend = 'tunable.upper'

    def sysctl(self, oid):
        """Quick and dirty means of doing sysctl -n"""
        cmd = 'sysctl -n %s' % oid
        p = subprocess.Popen(shlex.split(cmd), stdout=subprocess.PIPE)
        return p.communicate()[0]

    def get_default_value(self, oid):
        """Get the default value for systctl"""
        value_default = None
        try:
            with open(TUNABLES_DEFAULT_FILE, 'r') as f:
                for line in f.readlines():
                    line = line.rstrip()
                    groups = line.split(" = ")
                    if groups[0] == oid:
                        value_default = groups[1]
                        break
        except Exception:
            pass
        return value_default

    @accepts(Dict(
        'tunable_create',
        Str('var', validators=[Match(r'^[\w\.]+$')], required=True),
        Str('value', required=True),
        Str('type', enum=['LOADER', 'RC', 'SYSCTL'], required=True),
        Str('comment'),
        Bool('enabled', default=True),
        register=True
    ))
    async def do_create(self, data):
        """
        Create a Tunable.

        `var` represents name of the sysctl/loader/rc variable.

        `type` should be one of the following:
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

        if data['type'] == 'sysctl':
            value_default = self.get_default_value(data['var'])
            if value_default is None:
                # Write default value
                cfg_file = open(TUNABLES_DEFAULT_FILE, 'a')
                cfg_file.writelines(f'{data["var"]} = {data["value"]}')
                cfg_file.close()

        await self.middleware.call('service.reload', data['type'])

        return await self._get_instance(data['id'])

    @accepts(
        Int('id'),
        Patch(
            'tunable_create',
            'tunable_update',
            ('attr', {'update': True})
        )
    )
    async def do_update(self, id, data):
        """
        Update Tunable of `id`.
        """
        old = await self._get_instance(id)

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

        await self.middleware.call('service.reload', new['type'])

        return await self._get_instance(id)

    @accepts(Int('id'))
    async def do_delete(self, id):
        """
        Delete Tunable of `id`.
        """
        tunable = await self._get_instance(id)
        await self.lower(tunable)
        if tunable['type'].lower() == 'sysctl':
            # Restore the default value, if it is possible.
            value_default = self.get_default_value(tunable['var'])
            if value_default is not None:
                ret = subprocess.run(
                    ['sysctl', f'{tunable["var"]}="{value_default}"'],
                    capture_output=True
                )
                if ret.returncode:
                    self.middleware.logger.debug(
                        'Failed to set sysctl %s -> %s: %s',
                        tunable['var'], tunable['value'], ret.stderr.decode(),
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
