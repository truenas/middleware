from middlewared.schema import Bool, Dict, IPAddr, List, Str, Int, Patch
from middlewared.service import (SystemServiceService, ValidationErrors,
                                 accepts, private, CRUDService)
from middlewared.async_validators import check_path_resides_within_volume
from middlewared.service_exception import CallError

import re
import os


LOGLEVEL_MAP = {
    '0': 'NONE',
    '1': 'MINIMUM',
    '2': 'NORMAL',
    '3': 'FULL',
    '10': 'DEBUG',
}
RE_NETBIOSNAME = re.compile(r"^[a-zA-Z0-9\.\-_!@#\$%^&\(\)'\{\}~]{1,15}$")


class SMBService(SystemServiceService):

    class Config:
        service = 'cifs'
        service_verb = 'restart'
        datastore = 'services.cifs'
        datastore_extend = 'smb.smb_extend'
        datastore_prefix = 'cifs_srv_'

    @private
    async def smb_extend(self, smb):
        """Extend smb for netbios."""
        if not await self.middleware.call('notifier.is_freenas') and await self.middleware.call('notifier.failover_node') == 'B':
            smb['netbiosname'] = smb['netbiosname_b']

        for i in ('aio_enable', 'aio_rs', 'aio_ws'):
            smb.pop(i, None)

        smb['loglevel'] = LOGLEVEL_MAP.get(smb['loglevel'])

        return smb

    async def __validate_netbios_name(self, name):
        return RE_NETBIOSNAME.match(name)

    @accepts(Dict(
        'smb_update',
        Str('netbiosname'),
        Str('netbiosname_b'),
        Str('netbiosalias'),
        Str('workgroup'),
        Str('description'),
        Str('doscharset', enum=[
            'CP437', 'CP850', 'CP852', 'CP866', 'CP932', 'CP949', 'CP950', 'CP1026', 'CP1251',
            'ASCII',
        ]),
        Str('unixcharset', enum=[
            'UTF-8', 'ISO-8859-1', 'ISO-8859-15', 'GB2312', 'EUC-JP', 'ASCII',
        ]),
        Str('loglevel', enum=['NONE', 'MINIMUM', 'NORMAL', 'FULL', 'DEBUG']),
        Bool('syslog'),
        Bool('localmaster'),
        Bool('domain_logons'),
        Bool('timeserver'),
        Str('guest'),
        Str('filemask'),
        Str('dirmask'),
        Bool('nullpw'),
        Bool('unixext'),
        Bool('zeroconf'),
        Bool('hostlookup'),
        Bool('allow_execute_always'),
        Bool('obey_pam_restrictions'),
        Bool('ntlmv1_auth'),
        List('bindip', items=[IPAddr('ip')]),
        Str('smb_options'),
        update=True,
    ))
    async def do_update(self, data):
        old = await self.config()

        new = old.copy()
        new.update(data)

        verrors = ValidationErrors()

        for i in ('workgroup', 'netbiosname', 'netbiosname_b', 'netbiosalias'):
            if i not in data or not data[i]:
                continue
            if not await self.__validate_netbios_name(data[i]):
                verrors.add(f'smb_update.{i}', 'Invalid NetBIOS name')

        if new['netbiosname'] and new['netbiosname'].lower() == new['workgroup'].lower():
            verrors.add('smb_update.netbiosname', 'NetBIOS and Workgroup must be unique')

        for i in ('filemask', 'dirmask'):
            if i not in data or not data[i]:
                continue
            try:
                if int(data[i], 8) & ~0o11777:
                    raise ValueError('Not an octet')
            except (ValueError, TypeError):
                verrors.add(f'smb_update.{i}', 'Not a valid mask')

        if verrors:
            raise verrors

        # TODO: consider using bidict
        for k, v in LOGLEVEL_MAP.items():
            if new['loglevel'] == v:
                new['loglevel'] = k
                break

        await self._update_service(old, new)

        return await self.config()


class SharingCIFSService(CRUDService):
    class Config:
        namespace = 'sharing.cifs'
        datastore = 'sharing.cifs_share'
        datastore_prefix = 'cifs_'
        datastore_extend = 'sharing.cifs.extend'

    @accepts(Dict(
        'sharingcifs_create',
        Str('path'),
        Bool('home'),
        Str('name'),
        Str('comment'),
        Bool('ro'),
        Bool('browsable'),
        Bool('recyclebin'),
        Bool('showhiddenfiles'),
        Bool('guestok'),
        Bool('guestonly'),
        Bool('abe'),
        List('hostsallow', items=[IPAddr('ip', cidr=True)]),
        List('hostsdeny', items=[IPAddr('ip', cidr=True)]),
        List('vfsobjects'),
        Int('storage_task'),
        Str('auxsmbconf'),
        Bool('default_permissions'),
        register=True
    ))
    async def do_create(self, data):
        verrors = ValidationErrors()
        path = data['path']

        default_perms = data.pop('default_permissions', True)

        await self.clean(data, 'sharingcifs_create', verrors)
        await self.validate(data, 'sharingcifs_create', verrors)

        await check_path_resides_within_volume(
            verrors, self.middleware, "sharingcifs_create.path", path)

        if verrors:
            raise verrors

        if path and not os.path.exists(path):
            try:
                os.makedirs(path)
            except OSError as e:
                raise CallError(f'Failed to create {path}: {e}')

        await self.compress(data)
        await self.set_storage_tasks(data)
        data['id'] = await self.middleware.call(
            'datastore.insert', self._config.datastore, data,
            {'prefix': self._config.datastore_prefix})
        await self.extend(data)

        await self.middleware.call('service.reload', 'cifs')
        await self.apply_default_perms(default_perms, path)

        return data

    @accepts(
        Int('id'),
        Patch(
            'sharingcifs_create',
            'sharingcifs_update',
            ('attr', {'update': True})
        )
    )
    async def do_update(self, id, data):
        verrors = ValidationErrors()
        path = data['path']
        default_perms = data.pop('default_permissions', False)

        old = await self.middleware.call(
            'datastore.query', self._config.datastore, [('id', '=', id)],
            {'extend': self._config.datastore_extend,
             'prefix': self._config.datastore_prefix,
             'get': True})

        new = old.copy()
        new.update(data)

        await self.clean(new, 'sharingcifs_update', verrors, id=id)
        await self.validate(new, 'sharingcifs_update', verrors, old=old)

        await check_path_resides_within_volume(
            verrors, self.middleware, "sharingcifs_update.path", path)

        if verrors:
            raise verrors

        if path and not os.path.exists(path):
            try:
                os.makedirs(path)
            except OSError as e:
                raise CallError(f'Failed to create {path}: {e}')

        await self.compress(new)
        await self.set_storage_tasks(new)
        await self.middleware.call(
            'datastore.update', self._config.datastore, id, new,
            {'prefix': self._config.datastore_prefix})
        await self.extend(new)

        await self.middleware.call('service.reload', 'cifs')
        await self.apply_default_perms(default_perms, path)

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
        home_result = await self.home_exists(
            data['home'], schema_name, verrors, old)

        if home_result:
            verrors.add(f'{schema_name}.home',
                        'Only one share is allowed to be a home share.')
        elif not home_result and not data['path']:
            verrors.add(f'{schema_name}.path', 'This field is required.')

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

        return home_result

    @private
    async def name_exists(self, data, schema_name, verrors, id=None):
        name = data['name']
        path = data['path']
        name_filters = [('name', '=', name)]
        path_filters = [('path', '=', path)]

        if path and not name:
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
        data['hostsallow'] = data['hostsallow'].split()
        data['hostsdeny'] = data['hostsdeny'].split()

        return data

    @private
    async def compress(self, data):
        data['hostsallow'] = ' '.join(data['hostsallow'])
        data['hostsdeny'] = ' '.join(data['hostsdeny'])

        return data

    @private
    async def apply_default_perms(self, default_perms, path):
        if default_perms:
            try:
                (owner, group) = await self.middleware.call(
                    'notifier.mp_get_owner', path)
            except Exception:
                (owner, group) = ('root', 'wheel')

            await self.middleware.call(
                'notifier.winacl_reset', path, owner, group)

    async def get_storage_tasks(self, path=None, home=False):
        zfs_datasets = await self.middleware.call('zfs.dataset.query')
        task_list = []
        task_dict = {}

        if path:
            for ds in zfs_datasets:
                tasks = []
                name = ds['name']
                mountpoint = ds['properties']['mountpoint']['parsed']

                if path == mountpoint or path.startswith(f'{mountpoint}/'):
                    if mountpoint == path:
                        tasks = await self.middleware.call(
                            'datastore.query', 'storage.task',
                            [['task_filesystem', '=', name]])
                    else:
                        tasks = await self.middleware.call(
                            'datastore.query', 'storage.task',
                            [['task_filesystem', '=', name],
                             ['task_recursive', '=', 'True']])

                for t in tasks:
                    task_list.append(t)
        elif home:
            task_list = await self.middleware.call(
                'datastore.query', 'storage.task',
                [['task_recursive', '=', 'True']])

        if task_list:
            for task in task_list:
                task_id = task['id']
                fs = task['task_filesystem']
                retcount = task['task_ret_count']
                retunit = task['task_ret_unit']
                _interval = task['task_interval']
                interval = dict(await self.middleware.call(
                    'notifier.choices', 'TASK_INTERVAL'))[_interval]

                msg = f'{fs} - every {interval} - {retcount}{retunit}'

                task_dict[task_id] = msg

        return task_dict

    @private
    async def set_storage_tasks(self, data):
        task = data.get('storage_task', None)
        home = data['home']
        path = data['path']
        task_list = []

        if not task:
            if path:
                task_list = await self.get_storage_tasks(path=path)
            elif home:
                task_list = await self.get_storage_tasks(home=home)

        if task_list:
            data['storage_task'] = list(task_list.keys())[0]

        return data

    @accepts()
    def vfsobjects_choices(self):
        vfs_modules_path = '/usr/local/lib/shared-modules/vfs'
        vfs_modules = []
        vfs_exclude = {'shadow_copy2', 'recycle', 'aio_pthread'}

        if os.path.exists(vfs_modules_path):
            vfs_modules.extend(
                filter(lambda m: m not in vfs_exclude,
                       map(lambda f: f.rpartition('.')[0],
                           os.listdir(vfs_modules_path)))
            )
        else:
            vfs_modules.extend(['streams_xattr'])

        return vfs_modules
