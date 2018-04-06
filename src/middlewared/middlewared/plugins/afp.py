from middlewared.async_validators import check_path_resides_within_volume
from middlewared.schema import accepts, Bool, Dict, Dir, Int, List, Str, Patch
from middlewared.validators import IpAddress, Range
from middlewared.service import (SystemServiceService, ValidationErrors,
                                 CRUDService, private)
import os
import ipaddress


class AFPService(SystemServiceService):

    class Config:
        service = "afp"
        datastore_prefix = "afp_srv_"

    @accepts(Dict(
        'afp_update',
        Bool('guest'),
        Str('guest_user'),
        List('bindip', items=[Str('ip', validators=[IpAddress()])]),
        Int('connections_limit', validators=[Range(min=1, max=65535)]),
        Dir('dbpath'),
        Str('global_aux'),
        Str('map_acls', enum=["rights", "mode", "none"]),
        Str('chmod_request', enum=["preserve", "simple", "ignore"]),
    ), Bool('dry_run', default=False))
    async def update(self, data, dry_run=False):
        old = await self.config()

        new = old.copy()
        new.update(data)

        verrors = ValidationErrors()

        if new["dbpath"]:
            await check_path_resides_within_volume(verrors, self.middleware, "afp_update.dbpath", new["dbpath"])

        if verrors:
            raise verrors

        if not dry_run:
            await self._update_service(old, new)

        return new


class SharingAFPService(CRUDService):
    class Config:
        namespace = 'sharing.afp'
        datastore = 'sharing.afp_share'
        datastore_prefix = 'afp_'

    @accepts(Dict(
        'sharingafp_create',
        Str('path'),
        Bool('home'),
        Str('name'),
        Str('comment'),
        Str('allow'),
        Str('deny'),
        Str('ro'),
        Str('rw'),
        Bool('timemachine'),
        Int('timemachine_quota'),
        Bool('nodev'),
        Bool('nostat'),
        Bool('upriv'),
        Str('fperm'),
        Str('dperm'),
        Str('umask'),
        Str('hostsallow'),
        Str('hostsdeny'),
        Str('auxparams'),
        register=True
    ))
    async def do_create(self, data):
        path = data['path']

        await self.clean(data, 'sharingafp_create')
        await self.validate(data, 'sharingafp_create')

        if path and not os.path.exists(path):
            try:
                os.makedirs(path)
            except OSError as e:
                verrors = ValidationErrors()
                verrors.add('sharingafp_create.path',
                            f"Failed to create {path}: {e}")

                raise verrors

        data['id'] = await self.middleware.call(
            'datastore.insert', self._config.datastore, data,
            {'prefix': self._config.datastore_prefix})

        await self.middleware.call('service.reload', 'afp')

        return data

    @accepts(
        Int('id'),
        Patch(
            'sharingafp_create',
            'sharingafp_update',
            ('attr', {'update': True})
        )
    )
    async def do_update(self, id, data):
        old = await self.middleware.call(
            'datastore.query', self._config.datastore, [('id', '=', id)],
            {'prefix': self._config.datastore_prefix,
             'get': True})

        new = old.copy()
        new.update(data)

        await self.clean(data, 'sharingafp_update', id=id)
        await self.validate(data, 'sharingafp_update', old=old)

        await self.middleware.call(
            'datastore.update', self._config.datastore, id, data,
            {'prefix': self._config.datastore_prefix})

        await self.middleware.call('service.reload', 'afp')

        return new

    @accepts(Int('id'))
    async def do_delete(self, id):
        return await self.middleware.call(
            'datastore.delete', self._config.datastore, id)

    @private
    async def clean(self, data, schema_name, id=None):
        clean_networks = ['hostsallow', 'hostsdeny']

        for name in clean_networks:
            data[name] = await self.clean_network(data[name], schema_name,
                                                  name)

        data['name'] = await self.name_exists(data, schema_name, id)

    @private
    async def clean_network(self, data, schema_name, attribute):
        verrors = ValidationErrors()

        if data:
            for net in data.split(' '):
                try:
                    ipaddress.ip_interface(net)
                except ValueError as e:
                    verrors.add(f"{schema_name}.{attribute}",
                                f'Invalid IP or Network: {net}')

            if verrors:
                raise verrors

            return data.strip()

        return ""

    @private
    async def validate(self, data, schema_name, old=None):
        await self.home_exists(data['home'], schema_name, old)
        await self.validate_umask(data['umask'], schema_name)

    async def validate_umask(self, data, schema_name):
        verrors = ValidationErrors()

        if not data.isdigit():
                verrors.add(f"{schema_name}.umask",
                            'The umask must be between 000 and 777.'
                            )
        else:
            for i in range(len(data)):
                umask_bit = int(data[i])
                if umask_bit > 7 or umask_bit < 0:
                    verrors.add(f"{schema_name}.umask",
                                'The umask must be between 000 and 777.'
                                )

        if verrors:
            raise verrors

    @private
    async def home_exists(self, home, schema_name, old=None):
        verrors = ValidationErrors()
        home_result = []

        if home:
            if old and old['id'] is not None:
                id = old['id']

                if not old['home']:
                    # The user already had this set as the home share
                    home_result = await self.middleware.call(
                        'datastore.query', self._config.datastore,
                        [('home', '=', True), ('id', '!=', id)],
                        {'prefix': self._config.datastore_prefix})
            else:
                home_result = await self.middleware.call(
                    'datastore.query', self._config.datastore,
                    [('home', '=', True)],
                    {'prefix': self._config.datastore_prefix})

        if home_result:
            verrors.add(f"{schema_name}.home",
                        'Only one share is allowed to be a home share.')

            raise verrors

    @private
    async def name_exists(self, data, schema_name, id=None):
        verrors = ValidationErrors()
        name = data['name']
        path = data['path']
        home = data['home']

        if not name:
            if home:
                name = 'Homes'
            else:
                name = path.rsplit('/', 1)[-1]

        if id is None:
            name_result = await self.middleware.call(
                'datastore.query', self._config.datastore,
                [('name', '=', name)],
                {'prefix': self._config.datastore_prefix})
            path_result = await self.middleware.call(
                'datastore.query', self._config.datastore,
                [('path', '=', path)],
                {'prefix': self._config.datastore_prefix})
        else:
            name_result = await self.middleware.call(
                'datastore.query', self._config.datastore,
                [('name', '=', name), ('id', '!=', id)],
                {'prefix': self._config.datastore_prefix})
            path_result = await self.middleware.call(
                'datastore.query', self._config.datastore,
                [('path', '=', path), ('id', '!=', id)],
                {'prefix': self._config.datastore_prefix})

        if name_result:
            verrors.add(f"{schema_name}.name",
                        'A share with this name already exists.')

        if path_result:
            verrors.add(f"{schema_name}.path",
                        'A share with this path already exists.')

        if verrors:
            raise verrors

        return name
