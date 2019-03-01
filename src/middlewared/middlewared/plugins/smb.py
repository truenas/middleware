from middlewared.schema import Bool, Dict, IPAddr, List, Str, Int, Patch
from middlewared.service import (SystemServiceService, ValidationErrors,
                                 accepts, private, CRUDService)
from middlewared.async_validators import check_path_resides_within_volume
from middlewared.service_exception import CallError
from middlewared.utils import Popen

import asyncio
import codecs
import os
import re
import subprocess
import uuid

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
        if not await self.middleware.call('system.is_freenas') and await self.middleware.call('failover.node') == 'B':
            smb['netbiosname'] = smb['netbiosname_b']

        for i in ('aio_enable', 'aio_rs', 'aio_ws'):
            smb.pop(i, None)

        smb['netbiosalias'] = smb['netbiosalias'].split()

        smb['loglevel'] = LOGLEVEL_MAP.get(smb['loglevel'])

        return smb

    async def __validate_netbios_name(self, name):
        return RE_NETBIOSNAME.match(name)

    async def unixcharset_choices(self):
        return await self.generate_choices(
            ['UTF-8', 'ISO-8859-1', 'ISO-8859-15', 'GB2312', 'EUC-JP', 'ASCII']
        )

    @private
    async def generate_choices(self, initial):
        def key_cp(encoding):
            cp = re.compile(r"(?P<name>CP|GB|ISO-8859-|UTF-)(?P<num>\d+)").match(encoding)
            if cp:
                return tuple((cp.group('name'), int(cp.group('num'), 10)))
            else:
                return tuple((encoding, float('inf')))

        charset = await self.common_charset_choices()
        return {
            v: v for v in [
                c for c in sorted(charset, key=key_cp) if c not in initial
            ] + initial
        }

    @private
    async def common_charset_choices(self):

        def check_codec(encoding):
            try:
                return encoding.upper() if codecs.lookup(encoding) else False
            except LookupError:
                return False

        proc = await Popen(
            ['/usr/bin/iconv', '-l'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        output = (await proc.communicate())[0].decode()

        encodings = set()
        for line in output.splitlines():
            enc = [e for e in line.split() if check_codec(e)]

            if enc:
                cp = enc[0]
                for e in enc:
                    if e in ('UTF-8', 'ASCII', 'GB2312', 'HZ-GB-2312', 'CP1361'):
                        cp = e
                        break

                encodings.add(cp)

        return encodings

    @accepts(Dict(
        'smb_update',
        Str('netbiosname'),
        Str('netbiosname_b'),
        List('netbiosalias', default=[]),
        Str('workgroup'),
        Str('description'),
        Bool('enable_smb1'),
        Str('unixcharset'),
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
        List('bindip', items=[IPAddr('ip')], default=[]),
        Str('smb_options'),
        update=True,
    ))
    async def do_update(self, data):
        old = await self.config()

        new = old.copy()
        new.update(data)

        verrors = ValidationErrors()

        if data.get('unixcharset') and data['unixcharset'] not in await self.unixcharset_choices():
            verrors.add(
                'smb_update.unixcharset',
                'Please provide a valid value for unixcharset'
            )

        for i in ('workgroup', 'netbiosname', 'netbiosname_b', 'netbiosalias'):
            if i not in data or not data[i]:
                continue
            if i == 'netbiosalias':
                for idx, item in enumerate(data[i]):
                    if not await self.__validate_netbios_name(item):
                        verrors.add(f'smb_update.{i}.{idx}', f'Invalid NetBIOS name: {item}')
            else:
                if not await self.__validate_netbios_name(data[i]):
                    verrors.add(f'smb_update.{i}', f'Invalid NetBIOS name: {data[i]}')

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

        await self.compress(new)

        await self._update_service(old, new)

        return await self.config()

    @private
    async def compress(self, data):
        data['netbiosalias'] = ' '.join(data['netbiosalias'])

        return data


class SharingSMBService(CRUDService):
    class Config:
        namespace = 'sharing.smb'
        datastore = 'sharing.cifs_share'
        datastore_prefix = 'cifs_'
        datastore_extend = 'sharing.smb.extend'

    @accepts(Dict(
        'sharingsmb_create',
        Str('path', required=True),
        Bool('home', default=False),
        Str('name'),
        Str('comment'),
        Bool('ro', default=False),
        Bool('browsable', default=True),
        Bool('timemachine', default=False),
        Bool('recyclebin', default=False),
        Bool('showhiddenfiles', default=False),
        Bool('guestok', default=False),
        Bool('guestonly', default=False),
        Bool('abe', default=False),
        List('hostsallow', default=[]),
        List('hostsdeny', default=[]),
        List('vfsobjects', default=['zfs_space', 'zfsacl', 'streams_xattr']),
        Int('storage_task', null=True),
        Str('auxsmbconf'),
        Bool('default_permissions'),
        register=True
    ))
    async def do_create(self, data):
        verrors = ValidationErrors()
        path = data['path']

        default_perms = data.pop('default_permissions', True)

        await self.clean(data, 'sharingsmb_create', verrors)
        await self.validate(data, 'sharingsmb_create', verrors)

        if verrors:
            raise verrors

        if path and not os.path.exists(path):
            try:
                os.makedirs(path)
            except OSError as e:
                raise CallError(f'Failed to create {path}: {e}')

        await self.compress(data)
        await self.set_storage_tasks(data)
        vuid = await self.generate_vuid(data['timemachine'])
        data.update({'vuid': vuid})
        data['id'] = await self.middleware.call(
            'datastore.insert', self._config.datastore, data,
            {'prefix': self._config.datastore_prefix})
        await self.extend(data)  # We should do this in the insert call ?

        await self._service_change('cifs', 'reload')
        await self.apply_default_perms(default_perms, path, data['home'])

        return data

    @accepts(
        Int('id'),
        Patch(
            'sharingsmb_create',
            'sharingsmb_update',
            ('attr', {'update': True})
        )
    )
    async def do_update(self, id, data):
        verrors = ValidationErrors()
        path = data.get('path')
        default_perms = data.pop('default_permissions', False)

        old = await self.middleware.call(
            'datastore.query', self._config.datastore, [('id', '=', id)],
            {'extend': self._config.datastore_extend,
             'prefix': self._config.datastore_prefix,
             'get': True})

        new = old.copy()
        new.update(data)

        new['vuid'] = await self.generate_vuid(new['timemachine'], new['vuid'])
        await self.clean(new, 'sharingsmb_update', verrors, id=id)
        await self.validate(new, 'sharingsmb_update', verrors, old=old)

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
        await self.extend(new)  # same here ?

        await self._service_change('cifs', 'reload')
        await self.apply_default_perms(default_perms, path, data['home'])

        return new

    @accepts(Int('id'))
    async def do_delete(self, id):
        share = await self._get_instance(id)
        result = await self.middleware.call('datastore.delete', self._config.datastore, id)
        await self.middleware.call('notifier.sharesec_delete', share['name'])
        await self._service_change('cifs', 'reload')
        return result

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

        if data['path']:
            await check_path_resides_within_volume(
                verrors, self.middleware, f"{schema_name}.path", data['path']
            )

        if data.get('name') and data['name'] == 'global':
            verrors.add(
                f'{schema_name}.name',
                'Global is a reserved section name, please select another one'
            )

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

        if path and not name:
            name = path.rsplit('/', 1)[-1]

        name_filters = [('name', '=', name)]

        if id is not None:
            name_filters.append(('id', '!=', id))

        name_result = await self.middleware.call(
            'datastore.query', self._config.datastore,
            name_filters,
            {'prefix': self._config.datastore_prefix})

        if name_result:
            verrors.add(f'{schema_name}.name',
                        'A share with this name already exists.')

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
    async def apply_default_perms(self, default_perms, path, is_home):
        if default_perms:
            try:
                stat = await self.middleware.call('filesystem.stat', path)
                owner = stat['user'] or 'root'
                group = stat['group'] or 'wheel'
            except Exception:
                (owner, group) = ('root', 'wheel')

            await self.middleware.call(
                'notifier.winacl_reset', path, owner, group, None, not is_home
            )

    @private
    async def generate_vuid(self, timemachine, vuid=""):
        try:
            if timemachine and vuid:
                uuid.UUID(vuid, version=4)
        except ValueError:
            self.logger.debug(f"Time machine VUID string ({vuid}) is invalid. Regenerating.")
            vuid = ""

        if timemachine and not vuid:
            vuid = str(uuid.uuid4())

        return vuid

    @accepts(Str('path', required=True))
    async def get_storage_tasks(self, path):
        zfs_datasets = await self.middleware.call('zfs.dataset.query', [('type', '=', 'FILESYSTEM')])
        task_list = []
        task_dict = {}

        for ds in zfs_datasets:
            tasks = []
            name = ds['name']
            mountpoint = ds['properties']['mountpoint']['parsed']

            if path == mountpoint:
                tasks = await self.middleware.call('pool.snapshottask.query', [['dataset', '=', name]])
            elif path.startswith(f'{mountpoint}/'):
                tasks = await self.middleware.call('pool.snapshottask.query', [['dataset', '=', name],
                                                                               ['recursive', '=', True]])

            task_list.extend(tasks)

        for task in task_list:
            task_id = task['id']

            msg = (f'{task["dataset"]} - {task["naming_schema"]} - '
                   f'{task["lifetime_value"]}{task["lifetime_unit"].lower()[0]}')

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
        vfs_exclude = {
            'acl_tdb',
            'acl_xattr',
            'aio_fork',
            'aio_pthread',
            'cacheprime',
            'commit',
            'expand_msdfs',
            'linux_xfs_sgid',
            'netatalk',
            'posix_eadb',
            'recycle',
            'shadow_copy',
            'shadow_copy2',
            'streams_depot',
            'syncops',
            'xattr_tdb'
        }

        if os.path.exists(vfs_modules_path):
            vfs_modules.extend(
                filter(lambda m: m not in vfs_exclude,
                       map(lambda f: f.rpartition('.')[0],
                           os.listdir(vfs_modules_path)))
            )
        else:
            vfs_modules.extend(['streams_xattr'])

        return vfs_modules


async def pool_post_import(middleware, pool):
    """
    Makes sure to reload SMB if a pool is imported and there are shares configured for it.
    """
    path = f'/mnt/{pool["name"]}'
    if await middleware.call('sharing.smb.query', [
        ('OR', [
            ('path', '=', path),
            ('path', '^', f'{path}/'),
        ])
    ]):
        asyncio.ensure_future(middleware.call('service.reload', 'cifs'))


async def setup(middleware):
    middleware.register_hook('pool.post_import_pool', pool_post_import, sync=True)
