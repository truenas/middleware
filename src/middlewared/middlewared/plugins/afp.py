import asyncio
import enum
import uuid

from middlewared.async_validators import check_path_resides_within_volume
from middlewared.common.attachment import LockableFSAttachmentDelegate
from middlewared.common.listen import SystemServiceListenMultipleDelegate
from middlewared.schema import (accepts, Bool, Dict, Dir, Int, List, Str,
                                Patch, UnixPerm)
from middlewared.validators import IpAddress, Range
from middlewared.service import SystemServiceService, ValidationErrors, SharingService, private
from middlewared.service_exception import CallError
import middlewared.sqlalchemy as sa
import os


class AFPModel(sa.Model):
    __tablename__ = 'services_afp'

    id = sa.Column(sa.Integer(), primary_key=True)
    afp_srv_guest = sa.Column(sa.Boolean(), default=False)
    afp_srv_guest_user = sa.Column(sa.String(120), default="nobody")
    afp_srv_bindip = sa.Column(sa.MultiSelectField(), default=[])
    afp_srv_connections_limit = sa.Column(sa.Integer(), default=50)
    afp_srv_dbpath = sa.Column(sa.String(255), nullable=True)
    afp_srv_global_aux = sa.Column(sa.Text())
    afp_srv_map_acls = sa.Column(sa.String(120))
    afp_srv_chmod_request = sa.Column(sa.String(120))
    afp_srv_loglevel = sa.Column(sa.String(120), default="MINIMUM")


class AFPLogLevel(enum.Enum):
    NONE = "severe"
    MINIMUM = "warn"
    NORMAL = "note"
    FULL = "info"
    DEBUG = "maxdebug"


class AFPService(SystemServiceService):

    class Config:
        service = 'afp'
        datastore_extend = 'afp.extend'
        datastore_prefix = 'afp_srv_'
        cli_namespace = 'service.afp'

    @private
    async def extend(self, afp):
        for i in ('map_acls', 'chmod_request'):
            afp[i] = afp[i].upper()
        return afp

    @private
    async def compress(self, afp):
        for i in ('map_acls', 'chmod_request'):
            value = afp.get(i)
            if value:
                afp[i] = value.lower()
        return afp

    @accepts(Dict(
        'afp_update',
        Bool('guest'),
        Str('guest_user'),
        List('bindip', items=[Str('ip', validators=[IpAddress()])]),
        Int('connections_limit', validators=[Range(min=1, max=65535)]),
        Dir('dbpath'),
        Str('global_aux', max_length=None),
        Str('map_acls', enum=['RIGHTS', 'MODE', 'NONE']),
        Str('chmod_request', enum=['PRESERVE', 'SIMPLE', 'IGNORE']),
        Str('loglevel', enum=[x.name for x in AFPLogLevel]),
        update=True
    ))
    async def do_update(self, data):
        """
        Update AFP service settings.

        `bindip` is a list of IPs to bind AFP to. Leave blank (empty list) to bind to all
        available IPs.

        `map_acls` defines how to map the effective permissions of authenticated users.
        RIGHTS - Unix-style permissions
        MODE - ACLs
        NONE - Do not map

        `chmod_request` defines advanced permission control that deals with ACLs.
        PRESERVE - Preserve ZFS ACEs for named users and groups or POSIX ACL group mask
        SIMPLE - Change permission as requested without any extra steps
        IGNORE - Permission change requests are ignored
        """
        old = await self.config()

        new = old.copy()
        new.update(data)

        verrors = ValidationErrors()

        if new['dbpath']:
            await check_path_resides_within_volume(
                verrors, self.middleware, 'afp_update.dbpath', new['dbpath'],
            )

        verrors.check()

        new = await self.compress(new)
        await self._update_service(old, new)

        return await self.config()

    @accepts()
    async def bindip_choices(self):
        """
        List of valid choices for IP addresses to which to bind the AFP service.
        """
        return {
            d['address']: d['address'] for d in await self.middleware.call('interface.ip_in_use')
        }


class SharingAFPModel(sa.Model):
    __tablename__ = 'sharing_afp_share'

    id = sa.Column(sa.Integer(), primary_key=True)
    afp_path = sa.Column(sa.String(255))
    afp_name = sa.Column(sa.String(120))
    afp_comment = sa.Column(sa.String(120))
    afp_allow = sa.Column(sa.String(120))
    afp_deny = sa.Column(sa.String(120))
    afp_ro = sa.Column(sa.String(120))
    afp_rw = sa.Column(sa.String(120))
    afp_timemachine = sa.Column(sa.Boolean(), default=False)
    afp_nodev = sa.Column(sa.Boolean(), default=False)
    afp_nostat = sa.Column(sa.Boolean(), default=False)
    afp_upriv = sa.Column(sa.Boolean(), default=True)
    afp_fperm = sa.Column(sa.String(3), default="644")
    afp_dperm = sa.Column(sa.String(3), default="755")
    afp_umask = sa.Column(sa.String(3), default="000")
    afp_hostsallow = sa.Column(sa.String(120))
    afp_hostsdeny = sa.Column(sa.String(120))
    afp_auxparams = sa.Column(sa.Text())
    afp_timemachine_quota = sa.Column(sa.Integer(), default=0)
    afp_home = sa.Column(sa.Boolean(), default=False)
    afp_enabled = sa.Column(sa.Boolean(), default=True)
    afp_vuid = sa.Column(sa.String(36))


class SharingAFPService(SharingService):

    share_task_type = 'AFP'

    class Config:
        namespace = 'sharing.afp'
        datastore = 'sharing.afp_share'
        datastore_prefix = 'afp_'
        datastore_extend = 'sharing.afp.extend'
        cli_namespace = 'sharing.afp'

    @accepts(Dict(
        'sharingafp_create',
        Str('path', required=True),
        Bool('home', default=False),
        Str('name'),
        Str('comment'),
        List('allow'),
        List('deny'),
        List('ro'),
        List('rw'),
        Bool('timemachine', default=False),
        Int('timemachine_quota', default=0),
        Bool('nodev', default=False),
        Bool('nostat', default=False),
        Bool('upriv', default=True),
        UnixPerm('fperm', default='644'),
        UnixPerm('dperm', default='755'),
        UnixPerm('umask', default='000'),
        List('hostsallow', items=[]),
        List('hostsdeny', items=[]),
        Str('vuid', null=True, default=''),
        Str('auxparams', max_length=None),
        Bool('enabled', default=True),
        register=True
    ))
    async def do_create(self, data):
        """
        Create AFP share.

        `allow`, `deny`, `ro`, and `rw` are lists of users and groups. Groups are designated by
        an @ prefix.

        `hostsallow` and `hostsdeny` are lists of hosts and/or networks.
        """
        verrors = ValidationErrors()
        path = data['path']

        await self.clean(data, 'sharingafp_create', verrors)
        await self.validate(data, 'sharingafp_create', verrors)
        verrors.check()

        if path and not os.path.exists(path):
            try:
                os.makedirs(path)
            except OSError as e:
                raise CallError(f'Failed to create {path}: {e}')

        await self.compress(data)
        data['id'] = await self.middleware.call(
            'datastore.insert', self._config.datastore, data,
            {'prefix': self._config.datastore_prefix})

        await self._service_change('afp', 'reload')

        return await self.get_instance(data['id'])

    @accepts(
        Int('id'),
        Patch(
            'sharingafp_create',
            'sharingafp_update',
            ('attr', {'update': True})
        )
    )
    async def do_update(self, id, data):
        """
        Update AFP share `id`.
        """
        verrors = ValidationErrors()
        old = await self.middleware.call(
            'datastore.query', self._config.datastore, [('id', '=', id)],
            {'extend': self._config.datastore_extend,
             'prefix': self._config.datastore_prefix,
             'get': True})
        path = data.get('path')

        new = old.copy()
        new.update(data)

        await self.clean(new, 'sharingafp_update', verrors, id=id)
        await self.validate(new, 'sharingafp_update', verrors, old=old)

        verrors.check()

        if path and not os.path.exists(path):
            try:
                os.makedirs(path)
            except OSError as e:
                raise CallError(f'Failed to create {path}: {e}')

        await self.compress(new)
        await self.middleware.call(
            'datastore.update', self._config.datastore, id, new,
            {'prefix': self._config.datastore_prefix})

        await self._service_change('afp', 'reload')

        return await self.get_instance(id)

    @accepts(Int('id'))
    async def do_delete(self, id):
        """
        Delete AFP share `id`.
        """
        result = await self.middleware.call('datastore.delete', self._config.datastore, id)
        await self._service_change('afp', 'reload')
        return result

    @private
    async def clean(self, data, schema_name, verrors, id=None):
        data['name'] = await self.name_exists(data, schema_name, verrors, id)

    @private
    async def validate(self, data, schema_name, verrors, old=None):
        await self.home_exists(data['home'], schema_name, verrors, old)
        if data['vuid']:
            try:
                uuid.UUID(data['vuid'], version=4)
            except ValueError:
                verrors.add(f'{schema_name}.vuid', 'vuid must be a valid UUID.')
        await self.validate_path_field(data, schema_name, verrors)

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

    @private
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
        if not data['vuid'] and data['timemachine']:
            data['vuid'] = str(uuid.uuid4())
        data.pop(self.locked_field, None)
        return data


async def pool_post_import(middleware, pool):
    """
    Makes sure to reload AFP if a pool is imported and there are shares configured for it.
    """
    if pool is None:
        asyncio.ensure_future(middleware.call('etc.generate', 'afpd'))
        return

    path = f'/mnt/{pool["name"]}'
    if await middleware.call('sharing.afp.query', [
        ('OR', [
            ('path', '=', path),
            ('path', '^', f'{path}/'),
        ])
    ]):
        asyncio.ensure_future(middleware.call('service.reload', 'afp'))


class AFPFSAttachmentDelegate(LockableFSAttachmentDelegate):
    name = 'afp'
    title = 'AFP Share'
    service = 'afp'
    service_class = SharingAFPService

    async def restart_reload_services(self, attachments):
        await self._service_change('afp', 'reload')

    async def stop(self, attachments):
        # AFP does not allow us to close specific share forcefully so we have to abort all connections
        await self._service_change('afp', 'restart')


async def setup(middleware):
    await middleware.call(
        'interface.register_listen_delegate',
        SystemServiceListenMultipleDelegate(middleware, 'afp', 'bindip'),
    )
    await middleware.call('pool.dataset.register_attachment_delegate', AFPFSAttachmentDelegate(middleware))
    middleware.register_hook('pool.post_import', pool_post_import, sync=True)
