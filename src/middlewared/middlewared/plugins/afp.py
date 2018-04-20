from middlewared.async_validators import check_path_resides_within_volume
from middlewared.schema import (accepts, Bool, Dict, Dir, Int, List, Str,
                                Patch, IPAddr, UnixPerm)
from middlewared.validators import IpAddress, Range
from middlewared.service import (SystemServiceService, ValidationErrors,
                                 CRUDService, private)
from middlewared.service_exception import CallError
import os


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
    ))
    async def do_update(self, data):
        old = await self.config()

        new = old.copy()
        new.update(data)

        verrors = ValidationErrors()

        if new["dbpath"]:
            await check_path_resides_within_volume(verrors, self.middleware, "afp_update.dbpath", new["dbpath"])

        if verrors:
            raise verrors

        await self._update_service(old, new)

        return new


class SharingAFPService(CRUDService):
    class Config:
        namespace = 'sharing.afp'
        datastore = 'sharing.afp_share'
        datastore_prefix = 'afp_'
        datastore_extend = 'sharing.afp.extend'

    @accepts(Dict(
        'sharingafp_create',
        Str('path'),
        Bool('home'),
        Str('name'),
        Str('comment'),
        List('allow'),
        List('deny'),
        List('ro'),
        List('rw'),
        Bool('timemachine'),
        Int('timemachine_quota'),
        Bool('nodev'),
        Bool('nostat'),
        Bool('upriv'),
        UnixPerm('fperm', default='644'),
        UnixPerm('dperm', default='755'),
        UnixPerm('umask', default='000'),
        List('hostsallow', items=[IPAddr('ip', cidr=True)]),
        List('hostsdeny', items=[IPAddr('ip', cidr=True)]),
        Str('auxparams'),
        register=True
    ))
    async def do_create(self, data):
        verrors = ValidationErrors()
        path = data['path']

        await self.clean(data, 'sharingafp_create', verrors)
        await self.validate(data, 'sharingafp_create', verrors)

        await check_path_resides_within_volume(
            verrors, self.middleware, "sharingafp_create.path", path)

        if verrors:
            raise verrors

        if path and not os.path.exists(path):
            try:
                os.makedirs(path)
            except OSError as e:
                raise CallError(f'Failed to create {path}: {e}')

        await self.compress(data)
        data['id'] = await self.middleware.call(
            'datastore.insert', self._config.datastore, data,
            {'prefix': self._config.datastore_prefix})
        await self.extend(data)

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
        verrors = ValidationErrors()
        old = await self.middleware.call(
            'datastore.query', self._config.datastore, [('id', '=', id)],
            {'extend': self._config.datastore_extend,
             'prefix': self._config.datastore_prefix,
             'get': True})
        path = data['path']

        new = old.copy()
        new.update(data)

        await self.clean(new, 'sharingafp_update', verrors, id=id)
        await self.validate(new, 'sharingafp_update', verrors, old=old)

        await check_path_resides_within_volume(
            verrors, self.middleware, "sharingafp_create.path", path)

        if verrors:
            raise verrors

        if path and not os.path.exists(path):
            try:
                os.makedirs(path)
            except OSError as e:
                raise CallError(f'Failed to create {path}: {e}')

        await self.compress(new)
        await self.middleware.call(
            'datastore.update', self._config.datastore, id, new,
            {'prefix': self._config.datastore_prefix})
        await self.extend(new)

        await self.middleware.call('service.reload', 'afp')

        return new

    @accepts(Int('id'))
    async def do_delete(self, id):
        return await self.middleware.call(
            'datastore.delete', self._config.datastore, id)

    @private
    async def clean(self, data, schema_name, verrors, id=None):
        data['name'] = await self.name_exists(data, schema_name, verrors, id)

    @private
    async def validate(self, data, schema_name, verrors, old=None):
        await self.home_exists(data['home'], schema_name, verrors, old)

    @private
    async def home_exists(self, home, schema_name, verrors, old=None):
        home_filters = [('home', '=', True)]
        home_result = None

        if home:
            if old and old['id'] is not None:
                id = old['id']

                if not old['home']:
                    home_filters.append(('id', '!=', id))
                    # The user already had this set as the home share
                    home_result = await self.middleware.call(
                        'datastore.query', self._config.datastore,
                        home_filters, {'prefix': self._config.datastore_prefix})

        if home_result:
            verrors.add(f'{schema_name}.home',
                        'Only one share is allowed to be a home share.')

    async def name_exists(self, data, schema_name, verrors, id=None):
        name = data['name']
        path = data['path']
        home = data['home']
        name_filters = [('name', '=', name)]
        path_filters = [('path', '=', path)]

        if not name:
            if home:
                name = 'Homes'
            else:
                name = path.rsplit('/', 1)[-1]

        if id is not None:
            name_filters.append(('id', '!=', id))
            path_filters.append(('id', '!=', id))

        name_result = await self.middleware.call(
            'datastore.query', self._config.datastore,
            name_filters,
            {'prefix': self._config.datastore_prefix})
        path_result = await self.middleware.call(
            'datastore.query', self._config.datastore,
            path_filters,
            {'prefix': self._config.datastore_prefix})

        if name_result:
            verrors.add(f'{schema_name}.name',
                        'A share with this name already exists.')

        if path_result:
            verrors.add(f'{schema_name}.path',
                        'A share with this path already exists.')

        return name

    @private
    async def extend(self, data):
        data['allow'] = data['allow'].split()
        data['deny'] = data['deny'].split()
        data['ro'] = data['ro'].split()
        data['rw'] = data['rw'].split()
        data['hostsallow'] = data['hostsallow'].split()
        data['hostsdeny'] = data['hostsdeny'].split()

        return data

    @private
    async def compress(self, data):
        data['allow'] = ' '.join(data['allow'])
        data['deny'] = ' '.join(data['deny'])
        data['ro'] = ' '.join(data['ro'])
        data['rw'] = ' '.join(data['rw'])
        data['hostsallow'] = ' '.join(data['hostsallow'])
        data['hostsdeny'] = ' '.join(data['hostsdeny'])

        return data
