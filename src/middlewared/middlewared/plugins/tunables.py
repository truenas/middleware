import re

from middlewared.schema import (Bool, Dict, Int, Patch, Str, ValidationErrors,
                                accepts)
from middlewared.service import CRUDService, private


class TunableService(CRUDService):
    class Config:
        datastore = 'system.tunable'
        datastore_prefix = 'tun_'
        datastore_extend = 'tunable.upper'

    @accepts(Dict(
        'tunable_create',
        Str('var'),
        Str('value'),
        Str('type', enum=['LOADER', 'RC', 'SYSCTL']),
        Str('comment'),
        Bool('enabled'),
        register=True
    ))
    async def do_create(self, data):
        await self.clean(data, 'tunable_create')
        await self.validate(data, 'tunable_create')
        await self.lower(data)

        data['id'] = await self.middleware.call(
            'datastore.insert', self._config.datastore, data,
            {'prefix': self._config.datastore_prefix})

        await self.middleware.call('service.reload', data['type'])
        await self.upper(data)

        return data

    @accepts(
        Int('id'),
        Patch(
            'tunable_create',
            'tunable_update',
            ('attr', {'update': True})
        )
    )
    async def do_update(self, id, data):
        old = await self.middleware.call(
            'datastore.query', self._config.datastore, [('id', '=', id)],
            {'extend': self._config.datastore_extend,
             'prefix': self._config.datastore_prefix,
             'get': True})

        new = old.copy()
        new.update(data)

        await self.clean(data, 'tunable_update', old=old)
        await self.validate(data, 'tunable_update')

        await self.lower(data)

        await self.middleware.call(
            'datastore.update', self._config.datastore, id, data,
            {'prefix': self._config.datastore_prefix})

        await self.middleware.call('service.reload', data['type'].lower())

        await self.upper(new)

        return new

    @accepts(Int('id'))
    async def do_delete(self, id):
        return await self.middleware.call(
            'datastore.delete', self._config.datastore, id)

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
            err_msg = """Variable name must:<br />
1. Start with a letter.<br />
2. End with a letter or number.<br />
3. Can contain a combination of alphanumeric characters, numbers and/or
\ underscores.
"""
        else:
            err_msg = """Variable name must:<br />
1. Start with a letter.<br />
2. Contain at least one period.<br />
3. End with a letter or number.<br />
4. Can contain a combination of alphanumeric characters, numbers and/or
\ underscores.
"""

        if (
            tun_type in ('loader', 'rc') and
            not loader_re.match(tun_var)
        ) or (
            tun_type == 'sysctl' and
            not sysctl_re.match(tun_var)
        ):
            verrors.add(f"{schema_name}.value", err_msg)

        if verrors:
            raise verrors
