from middlewared.schema import Bool, Dict, IPAddr, List, Str, Int, Patch
from middlewared.service import (SystemServiceService, ValidationErrors,
                                 accepts, private, CRUDService, job)
from middlewared.async_validators import check_path_resides_within_volume
from middlewared.service_exception import CallError
from middlewared.utils import Popen

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
        if not await self.middleware.call('notifier.is_freenas') and await self.middleware.call('notifier.failover_node') == 'B':
            smb['netbiosname'] = smb['netbiosname_b']

        for i in ('aio_enable', 'aio_rs', 'aio_ws'):
            smb.pop(i, None)

        smb['loglevel'] = LOGLEVEL_MAP.get(smb['loglevel'])

        return smb

    async def __validate_netbios_name(self, name):
        return RE_NETBIOSNAME.match(name)

    async def doscharset_choices(self):
        return await self.generate_choices(
            ['CP437', 'CP850', 'CP852', 'CP866', 'CP932', 'CP949', 'CP950', 'CP1026', 'CP1251', 'ASCII']
        )

    async def unixcharset_choices(self):
        return await self.generate_choices(
            ['UTF-8', 'ISO-8859-1', 'ISO-8859-15', 'GB2312', 'EUC-JP', 'ASCII']
        )

    @private
    async def generate_choices(self, initial):
        def key_cp(encoding):
            cp = re.compile("(?P<name>CP|GB|ISO-8859-|UTF-)(?P<num>\d+)").match(encoding)
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
    async def validate_admin_groups(self, sid):
        """
        Check if group mapping already exists because 'net groupmap addmem' will fail
        if the mapping exists. Remove any entries that should not be present. Extra
        entries here can pose a significant security risk. The only default entry will
        have a RID value of "512" (Domain Admins).
        In LDAP environments, members of S-1-5-32-544 cannot be removed without impacting
        the entire LDAP environment because this alias exists on the remote LDAP server.
        """
        sid_is_present = False
        ldap = await self.middleware.call('datastore.config', 'directoryservice.ldap')
        if ldap['ldap_enable']:
            self.logger.debug("As a safety precaution, extra alias entries for S-1-5-32-544 cannot be removed while LDAP is enabled. Skipping removal.")
            return True
        proc = await Popen(
            ['/usr/local/bin/net', 'groupmap', 'listmem', 'S-1-5-32-544'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        member_list = (await proc.communicate())[0].decode()
        if not member_list:
            return True

        for group in member_list.splitlines():
            group = group.strip()
            if group == sid:
                self.logger.debug(f"SID [{sid}] is already a member of BUILTIN\\administrators")
                sid_is_present = True
            if group.rsplit('-', 1)[-1] != "512" and group != sid:
                self.logger.debug(f"Removing {group} from local admins group.")
                rem = await Popen(
                    ['/usr/local/bin/net', 'groupmap', 'delmem', 'S-1-5-32-544', group],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )
                remout = await rem.communicate()
                if rem.returncode != 0:
                    raise CallError(f'Failed to remove sid [{sid}] from S-1-5-32-544: {remout[1].decode()}')

        if sid_is_present:
            return False
        else:
            return True

    @private
    async def wbinfo_gidtosid(self, gid):
        verrors = ValidationErrors()
        proc = await Popen(
            ['/usr/local/bin/wbinfo', '--gid-to-sid', f"{gid}"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        output = await proc.communicate()
        if proc.returncode != 0:
            if "WBC_ERR_WINBIND_NOT_AVAILABLE" in output[1].decode():
                return "WBC_ERR_WINBIND_NOT_AVAILABLE"
            else:
                verrors.add('smb_update.admin_group', f"Failed to identify Windows SID for group: {output[1].decode()}")
                raise verrors

        return output[0].decode().strip()

    @private
    async def add_admin_group(self, admin_group=None, check_deferred=False):
        """
        Add a local or directory service group to BUILTIN\\Administrators (S-1-5-32-544)
        Members of this group have elevated privileges to the Samba server (ability to
        take ownership of files, override ACLs, view and modify user quotas, and administer
        the server via the Computer Management MMC Snap-In. Unfortuntely, group membership
        must be managed via "net groupmap listmem|addmem|delmem", which requires that
        winbind be running when the commands are executed. In this situation, net command
        will fail with WBC_ERR_WINBIND_NOT_AVAILABLE. If this error message is returned, then
        flag for a deferred command retry when service starts.

        @param-in (admin_group): This is the group to add to BUILTIN\\Administrators. If unset, then
            look up the value in the config db.
        @param-in (check_deferred): If this is True, then only perform the group mapping if this has
            been flagged as in need of deferred setup (i.e. Samba wasn't running when it was initially
            called). This is to avoid unecessarily calling during service start.
        """

        verrors = ValidationErrors()
        if check_deferred:
            is_deferred = await self.middleware.call('cache.has_key', 'SMB_SET_ADMIN')
            if not is_deferred:
                self.logger.debug("No cache entry indicating delayed action to add admin_group was found.")
                return True
            else:
                await self.middleware.call('cache.pop', 'SMB_SET_ADMIN')

        if not admin_group:
            smb = await self.middleware.call('smb.config')
            admin_group = smb['admin_group']

        # We must use GIDs because wbinfo --name-to-sid expects a domain prefix "FREENAS\user"
        group = await self.middleware.call("notifier.get_group_object", admin_group)
        if not group:
            verrors.add('smb_update.admin_group', f"Failed to validate group: {admin_group}")
            raise verrors

        sid = await self.wbinfo_gidtosid(group[2])
        if sid == "WBC_ERR_WINBIND_NOT_AVAILABLE":
            self.logger.debug("Delaying admin group add until winbind starts")
            await self.middleware.call('cache.put', 'SMB_SET_ADMIN', True)
            return True

        must_add_sid = await self.validate_admin_groups(sid)
        if not must_add_sid:
            return True

        proc = await Popen(
            ['/usr/local/bin/net', 'groupmap', 'addmem', 'S-1-5-32-544', sid],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        output = await proc.communicate()
        if proc.returncode != 0:
            raise CallError(f'net groupmap addmem failed: {output[1].decode()}')

        self.logger.debug(f"Successfully added {admin_group} to BUILTIN\\Administrators")
        return True

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
        Str('netbiosalias'),
        Str('workgroup'),
        Str('description'),
        Bool('enable_smb1'),
        Str('doscharset'),
        Str('unixcharset'),
        Str('loglevel', enum=['NONE', 'MINIMUM', 'NORMAL', 'FULL', 'DEBUG']),
        Bool('syslog'),
        Bool('localmaster'),
        Bool('domain_logons'),
        Bool('timeserver'),
        Str('guest'),
        Str('admin_group'),
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

        for k, m in [('unixcharset', self.unixcharset_choices), ('doscharset', self.doscharset_choices)]:
            if data.get(k) and data[k] not in await m():
                verrors.add(
                    f'smb_update.{k}',
                    f'Please provide a valid value for {k}'
                )

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

        if new['admin_group'] and new['admin_group'] != old['admin_group']:
            await self.add_admin_group(new['admin_group'])

        if verrors:
            raise verrors

        # TODO: consider using bidict
        for k, v in LOGLEVEL_MAP.items():
            if new['loglevel'] == v:
                new['loglevel'] = k
                break

        await self._update_service(old, new)

        return await self.config()


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
        Int('storage_task'),
        Str('auxsmbconf'),
        Bool('default_permissions', default=False),
        register=True
    ))
    async def do_create(self, data):
        verrors = ValidationErrors()
        path = data['path']

        default_perms = data.pop('default_permissions', False)

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
        vuid = await self.generate_vuid(data['timemachine'])
        data.update({'vuid': vuid})
        data['id'] = await self.middleware.call(
            'datastore.insert', self._config.datastore, data,
            {'prefix': self._config.datastore_prefix})
        await self.extend(data)  # We should do this in the insert call ?

        await self.middleware.call('service.reload', 'cifs')
        await self.middleware.call('sharing.smb.apply_default_perms', default_perms, path, data['home'])

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
        await self.middleware.call(
            'datastore.update', self._config.datastore, id, new,
            {'prefix': self._config.datastore_prefix})
        await self.extend(new)  # same here ?

        await self.middleware.call('service.reload', 'cifs')
        await self.middleware.call('sharing.smb.apply_default_perms', default_perms, path, data['home'])

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

        if data['path']:
            await check_path_resides_within_volume(
                verrors, self.middleware, f"{schema_name}.path", data['path']
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
    @job(lock=lambda args: f'setacl:{args[1]}')
    async def apply_default_perms(self, job, default_perms, path, is_home):
        if default_perms:
            try:
                (owner, group) = await self.middleware.call(
                    'notifier.mp_get_owner', path)
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
                tasks = await self.middleware.call(
                    'datastore.query', 'storage.task',
                    [['task_filesystem', '=', name]])
            elif path.startswith(f'{mountpoint}/'):
                tasks = await self.middleware.call(
                    'datastore.query', 'storage.task',
                    [['task_filesystem', '=', name],
                     ['task_recursive', '=', 'True']])

            task_list.extend(tasks)

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
