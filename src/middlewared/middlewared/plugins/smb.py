from middlewared.common.attachment import FSAttachmentDelegate
from middlewared.schema import Bool, Dict, IPAddr, List, Str, Int, Patch
from middlewared.service import (SystemServiceService, ValidationErrors,
                                 accepts, private, CRUDService)
from middlewared.async_validators import check_path_resides_within_volume
from middlewared.service_exception import CallError
from middlewared.utils import Popen, run
from middlewared.utils.path import is_child

import asyncio
import codecs
import enum
import grp
import os
import re
import subprocess
import uuid
from samba import param

LOGLEVEL_MAP = {
    '0': 'NONE',
    '1': 'MINIMUM',
    '2': 'NORMAL',
    '3': 'FULL',
    '10': 'DEBUG',
}
RE_NETBIOSNAME = re.compile(r"^[a-zA-Z0-9\.\-_!@#\$%^&\(\)'\{\}~]{1,15}$")
RE_NETGROUPMAP = re.compile(r"^(?P<ntgroup>.+) \((?P<SID>S-[0-9\-]+)\) -> (?P<unixgroup>.+)$")


class SMBHAMODE(enum.IntEnum):
    """
    'standalone' - Not an HA system.
    'legacy' - Two samba instances simultaneously running on active and passive controllers with no shared state.
    'unified' - Single set of state files migrating between controllers. Single netbios name.
    """
    STANDALONE = 0
    LEGACY = 1
    UNIFIED = 2


class SMBCmd(enum.Enum):
    NET = '/usr/local/bin/net'
    PDBEDIT = '/usr/local/bin/pdbedit'
    SMBCONTROL = '/usr/local/bin/smbcontrol'
    SMBPASSWD = '/usr/local/bin/smbpasswd'


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
        smb['netbiosname_local'] = smb['netbiosname']
        if not await self.middleware.call('system.is_freenas') and await self.middleware.call('failover.node') == 'B':
            smb['netbiosname_local'] = smb['netbiosname_b']

        for i in ('aio_enable', 'aio_rs', 'aio_ws'):
            smb.pop(i, None)

        smb['netbiosalias'] = (smb['netbiosalias'] or '').split()

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

    @private
    async def store_ldap_admin_password(self):
        """
        This is required if the LDAP directory service is enabled. The ldap admin dn and
        password are stored in private/secrets.tdb file.
        """
        ldap = await self.middleware.call('datastore.config', 'directoryservice.ldap')
        if not ldap['ldap_enable']:
            return True

        set_pass = await run(['usr/local/bin/smbpasswd', '-w', ldap['ldap_bindpw']], check=False)
        if set_pass.returncode != 0:
            self.logger.debug(f"Failed to set set ldap bindpw in secrets.tdb: {set_pass.stdout.decode()}")
            return False

        return True

    @private
    async def groupmap_list(self):
        groupmap = []
        out = await run([SMBCmd.NET.value, 'groupmap', 'list'], check=False)
        if out.returncode != 0:
            raise CallError(f'groupmap list failed with error {out.stderr.decode()}')
        for line in (out.stdout.decode()).splitlines():
            m = RE_NETGROUPMAP.match(line)
            if m:
                groupmap.append(m.groupdict())

        return groupmap

    @private
    async def groupmap_add(self, group):
        """
        Map Unix group to NT group. This is required for group members to be
        able to access the SMB share. Name collisions with well-known and
        builtin groups must be avoided. Mapping groups with the same
        names as users should also be avoided.
        """
        passdb_backend = await self.middleware.run_in_thread(self.getparm, 'passdb backend', 'global')
        if passdb_backend == 'ldapsam':
            return

        disallowed_list = ['USERS', 'ADMINISTRATORS', 'GUESTS']
        existing_groupmap = await self.middleware.call('smb.groupmap_list')
        for user in (await self.middleware.call('user.query')):
            disallowed_list.append(user['username'].upper())
        for g in existing_groupmap:
            disallowed_list.append(g['ntgroup'].upper())

        if group.upper() in disallowed_list:
            self.logger.debug('Setting group map for %s is not permitted', group)
            return False
        gm_add = await run(
            ['net', '-d', '0', 'groupmap', 'add', 'type=local', f'unixgroup={group}', f'ntgroup={group}'],
            check=False
        )
        if gm_add.returncode != 0:
            raise CallError(
                f'Failed to generate groupmap for [{group}]: ({gm_add.stderr.decode()})'
            )

    @private
    async def passdb_list(self, verbose=False):
        """
        passdb entries for local SAM database. This will be populated with
        local users in an AD environment. Immediately return in ldap enviornment.
        """
        pdbentries = []
        private_dir = await self.middleware.call('smb.getparm', 'privatedir', 'global')
        if not os.path.exists(f'{private_dir}/passdb.tdb'):
            return pdbentries

        if await self.middleware.call('smb.getparm', 'passdb backend', 'global') == 'ldapsam':
            return pdbentries

        if not verbose:
            pdb = await run([SMBCmd.PDBEDIT.value, '-L', '-d', '0'], check=False)
            if pdb.returncode != 0:
                raise CallError(f'Failed to list passdb output: {pdb.stderr.decode()}')
            for p in (pdb.stdout.decode()).splitlines():
                entry = p.split(':')
                pdbentries.append({
                    'username': entry[0],
                    'full_name': entry[2],
                    'uid': entry[1],
                })
            return pdbentries

        pdb = await run([SMBCmd.PDBEDIT.value, '-Lv', '-d', '0'], check=False)
        if pdb.returncode != 0:
            raise CallError(f'Failed to list passdb output: {pdb.stderr.decode()}')

        for p in (pdb.stdout.decode()).split('---------------'):
            pdbentry = {}
            for entry in p.splitlines():
                parm = entry.split(':')
                if len(parm) != 2:
                    continue

                pdbentry.update({parm[0].rstrip(): parm[1].lstrip() if parm[1] else ''})

            if pdbentry:
                pdbentries.append(pdbentry)

        return pdbentries

    @private
    async def update_passdb_user(self, username):
        """
        Updates a user's passdb entry to reflect the current server configuration.
        Accounts that are 'locked' in the UI will have their corresponding passdb entry
        disabled.
        """
        if self.getparm('passdb backend', 'global') == 'ldapsam':
            return

        bsduser = await self.middleware.call('user.query', [
            ('username', '=', username),
            ['OR', [
                ('smbhash', '~', r'^.+:.+:[X]{32}:.+$'),
                ('smbhash', '~', r'^.+:.+:[A-F0-9]{32}:.+$'),
            ]]
        ])
        if not bsduser:
            self.logger.debug(f'{username} is not an SMB user, bypassing passdb import')
            return
        smbpasswd_string = bsduser[0]['smbhash'].split(':')
        p = await run([SMBCmd.PDBEDIT.value, '-d', '0', '-Lw', username], check=False)
        if p.returncode != 0:
            CallError(f'Failed to retrieve passdb entry for {username}: {p.stderr.decode()}')
        entry = p.stdout.decode()
        if not entry:
            self.logger.debug("User [%s] does not exist in the passdb.tdb file. Creating entry.", username)
            pdbcreate = await Popen(
                [SMBCmd.PDBEDIT.value, '-d', '0', '-a', username, '-t'],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE
            )
            await pdbcreate.communicate(input=" \n \n".encode())
            setntpass = await run([SMBCmd.PDBEDIT.value, '-d', '0', '--set-nt-hash', smbpasswd_string[3], username], check=False)
            if setntpass.returncode != 0:
                raise CallError(f'Failed to set NT password for {username}: {setntpass.stderr.decode()}')
            if bsduser[0]['locked']:
                disableacct = await run([SMBCmd.SMBPASSWD.value, '-d', username], check=False)
                if disableacct.returncode != 0:
                    raise CallError(f'Failed to disable {username}: {disableacct.stderr.decode()}')
            return

        if entry == bsduser[0]['smbhash']:
            return

        entry = entry.split(':')

        if smbpasswd_string[3] != entry[3]:
            setntpass = await run([SMBCmd.PDBEDIT.value, '-d', '0', '--set-nt-hash', smbpasswd_string[3], username], check=False)
            if setntpass.returncode != 0:
                raise CallError(f'Failed to set NT password for {username}: {setntpass.stderr.decode()}')
        if bsduser[0]['locked'] and 'D' not in entry[4]:
            disableacct = await run([SMBCmd.SMBPASSWD.value, '-d', username], check=False)
            if disableacct.returncode != 0:
                raise CallError(f'Failed to disable {username}: {disableacct.stderr.decode()}')
        elif not bsduser[0]['locked'] and 'D' in entry[4]:
            enableacct = await run([SMBCmd.SMBPASSWD.value, '-e', username], check=False)
            if enableacct.returncode != 0:
                raise CallError(f'Failed to enable {username}: {enableacct.stderr.decode()}')

    @private
    async def synchronize_passdb(self):
        """
        Create any missing entries in the passdb.tdb.
        Replace NT hashes of users if they do not match what is the the config file.
        Synchronize the "disabled" state of users
        Delete any entries in the passdb_tdb file that don't exist in the config file.
        """
        if await self.middleware.call('smb.getparm', 'passdb backend', 'global') == 'ldapsam':
            return

        conf_users = await self.middleware.call('user.query', [
            ['OR', [
                ('smbhash', '~', r'^.+:.+:[X]{32}:.+$'),
                ('smbhash', '~', r'^.+:.+:[A-F0-9]{32}:.+$'),
            ]]
        ])
        for u in conf_users:
            await self.middleware.call('smb.update_passdb_user', u['username'])

        pdb_users = await self.passdb_list()
        if len(pdb_users) > len(conf_users):
            for entry in pdb_users:
                if not any(filter(lambda x: entry['username'] == x['username'], conf_users)):
                    self.logger.debug('Synchronizing passdb with config file: deleting user [%s] from passdb.tdb', entry['username'])
                    deluser = await run([SMBCmd.PDBEDIT.value, '-d', '0', '-x', entry['username']], check=False)
                    if deluser.returncode != 0:
                        raise CallError(f'Failed to delete user {entry["username"]}: {deluser.stderr.decode()}')

    @private
    def getparm(self, parm, section):
        """
        Get a parameter from the smb4.conf file. This is more reliable than
        'testparm --parameter-name'. testparm will fail in a variety of
        conditions without returning the parameter's value.
        """
        try:
            res = param.LoadParm('/usr/local/etc/smb4.conf').get(parm, section)
            return res
        except Exception as e:
            raise CallError(f'Attempt to query smb4.conf parameter [{parm}] failed with error: {e}')

    @private
    async def get_smb_ha_mode(self):
        if await self.middleware.call('cache.has_key', 'SMB_HA_MODE'):
            return await self.middleware.call('cache.get', 'SMB_HA_MODE')

        if not await self.middleware.call('system.is_freenas') and await self.middleware.call('failover.licensed'):
            system_dataset = await self.middleware.call('systemdataset.config')
            if system_dataset['pool'] != 'freenas-boot':
                hamode = SMBHAMODE['UNIFIED'].name
            else:
                hamode = SMBHAMODE['LEGACY'].name
        else:
            hamode = SMBHAMODE['STANDALONE'].name

        await self.middleware.call('cache.put', 'SMB_HA_MODE', hamode)
        return hamode

    @private
    async def reset_smb_ha_mode(self):
        await self.middleware.call('cache.pop', 'SMB_HA_MODE')
        return await self.get_smb_ha_mode()

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
        Str('admin_group', required=False, default=None, null=True),
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
        """
        Update SMB Service Configuration.

        `netbiosname` defaults to the original hostname of the system.

        `workgroup` and `netbiosname` should have different values.

        `enable_smb1` allows legacy SMB clients to connect to the server when enabled.

        `localmaster` when set, determines if the system participates in a browser election.

        `domain_logons` is used to provide netlogin service for older Windows clients if enabled.

        `guest` attribute is specified to select the account to be used for guest access. It defaults to "nobody".

        `nullpw` when enabled allows the users to authorize access without a password.

        `zeroconf` should be enabled if macOS Clients will be connecting to the SMB share.

        `hostlookup` when enabled, allows using hostnames rather then IP addresses in "hostsallow"/"hostsdeny" fields
        of SMB Shares.
        """
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

        if new['admin_group'] and new['admin_group'] != old['admin_group']:
            await self.add_admin_group(new['admin_group'])

        if verrors:
            raise verrors

        # TODO: consider using bidict
        for k, v in LOGLEVEL_MAP.items():
            if new['loglevel'] == v:
                new['loglevel'] = k
                break

        await self.compress(new)

        await self._update_service(old, new)
        await self.reset_smb_ha_mode()

        return await self.config()

    @private
    async def compress(self, data):
        data['netbiosalias'] = ' '.join(data['netbiosalias'])
        data.pop('netbiosname_local', None)
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
        Bool('shadowcopy', default=False),
        Str('auxsmbconf'),
        Bool('default_permissions'),
        Bool('enabled', default=True),
        register=True
    ))
    async def do_create(self, data):
        """
        Create a SMB Share.

        `timemachine` when set, enables Time Machine backups for this share.

        `default_permissions` when set makes ACLs grant read and write for owner or group and read-only for others. It
        is advised to be disabled when creating shares on a sytem with custom ACLs.

        `ro` when enabled, prohibits write access to the share.

        `guestok` when enabled, allows access to this share without a password.

        `hostsallow` is a list of hostnames / IP addresses which have access to this share.

        `hostsdeny` is a list of hostnames / IP addresses which are not allowed access to this share. If a handful
        of hostnames are to be only allowed access, `hostsdeny` can be passed "ALL" which means that it will deny
        access to ALL hostnames except for the ones which have been listed in `hostsallow`.

        `vfsobjects` is a list of keywords which aim to provide virtual file system modules to enhance functionality.

        `auxsmbconf` is a string of additional smb4.conf parameters not covered by the system's API.
        """
        verrors = ValidationErrors()
        path = data['path']

        default_perms = data.pop('default_permissions', True)

        if 'noacl' in data['vfsobjects']:
            default_perms = False

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
        """
        Update SMB Share of `id`.
        """
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

        await self._service_change('cifs', 'reload')
        await self.apply_default_perms(default_perms, path, data['home'])

        return new

    @accepts(Int('id'))
    async def do_delete(self, id):
        """
        Delete SMB Share of `id`.
        """
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

        if 'noacl' in data['vfsobjects']:
            if not await self.middleware.call('filesystem.acl_is_trivial', data['path']):
                verrors.add(
                    f'{schema_name}.vfsobjects',
                    f'The "noacl" VFS module is incompatible with the extended ACL on {data["path"]}.'
                )

        if data.get('name') and data['name'].lower() in ['global', 'homes', 'printers']:
            verrors.add(
                f'{schema_name}.name',
                f'{data["name"]} is a reserved section name, please select another one'
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
        """
        Reset permissions on an SMB share to "default". This is a recursive
        operaton, and will replace any existing ACL on the share path and any
        sub-datasets. The default ACLS depends on whether this is a `[homes]`
        share. Shares that are not the special "homes" share have the
        following ACL:

        `owner@:full_set:fd:allow`

        `group@:full_set:fd:allow`

        The path to homes shares are dynamically generated via pam_mkhomedir
        The final path (the user's actual home directory) will only have the
        following ACE:

        `owner@:full_set:fd:allow`

        The actual ACL written on the path specified in the UI will vary for
        homes shares depending on whether Active Directory is enabled. In all
        cases, the ACL is written so that users have adequate permissions to
        traverse to their home directory and the actual home directory is only
        accessible by the user.

        If an SMB admin group has been selected, then it will also be added to the
        share's ACL.
        """
        if not default_perms:
            return

        acl = []
        admin = None
        smb = await self.middleware.call('smb.config')
        if smb['admin_group']:
            admin = await self.middleware.run_in_thread(grp.getgrnam, smb['admin_group'])
            acl.append({
                "tag": "GROUP",
                "id": admin[2],
                "type": "ALLOW",
                "perms": {"BASIC": "FULL_CONTROL"},
                "flags": {"BASIC": "INHERIT"}
            })

        acl.append({
            "tag": "owner@",
            "id": None,
            "type": "ALLOW",
            "perms": {"BASIC": "FULL_CONTROL"},
            "flags": {"BASIC": "INHERIT"},
        })

        if not is_home:
            acl.append({
                "tag": "group@",
                "id": None,
                "type": "ALLOW",
                "perms": {"BASIC": "FULL_CONTROL"},
                "flags": {"BASIC": "INHERIT"},
            })

        elif await self.middleware.call('activedirectory.get_state') != 'DISABLED':
            acl.extend([
                {
                    "tag": "group@",
                    "id": None,
                    "type": "ALLOW",
                    "perms": {"BASIC": "MODIFY"},
                    "flags": {'DIRECTORY_INHERIT': True, 'INHERIT_ONLY': True, 'NO_PROPAGATE_INHERIT': True}
                },
                {
                    "tag": "everyone@",
                    "id": None,
                    "type": "ALLOW",
                    "perms": {"BASIC": "TRAVERSE"},
                    "flags": {"BASIC": "NOINHERIT"}
                },
            ])

        else:
            acl.extend([
                {
                    "tag": "group@",
                    "id": None,
                    "type": "ALLOW",
                    "perms": {"BASIC": "MODIFY"},
                    "flags": {"BASIC": "NOINHERIT"}
                },
                {
                    "tag": "everyone@",
                    "id": None,
                    "type": "ALLOW",
                    "perms": {"BASIC": "TRAVERSE"},
                    "flags": {"BASIC": "NOINHERIT"}
                },
            ])

        await self.middleware.call('filesystem.setacl', {
            'path': path,
            'dacl': acl,
            'uid': None,
            'gid': None,
            'options': {'recursive': True, 'traverse': True}
        })

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

    @accepts()
    def vfsobjects_choices(self):
        """
        Returns a list of valid virtual file system module choices which can be used with SMB Shares to enable virtual
        file system modules.
        """
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


class SMBFSAttachmentDelegate(FSAttachmentDelegate):
    name = 'smb'
    title = 'SMB Share'
    service = 'cifs'

    async def query(self, path, enabled):
        results = []
        for smb in await self.middleware.call('sharing.smb.query', [['enabled', '=', enabled]]):
            if is_child(smb['path'], path):
                results.append(smb)

        return results

    async def get_attachment_name(self, attachment):
        return attachment['name']

    async def delete(self, attachments):
        for attachment in attachments:
            await self.middleware.call('datastore.delete', 'sharing.cifs_share', attachment['id'])

        await self._service_change('cifs', 'reload')

    async def toggle(self, attachments, enabled):
        for attachment in attachments:
            await self.middleware.call('datastore.update', 'sharing.cifs_share', attachment['id'],
                                       {'cifs_enabled': enabled})

        await self._service_change('cifs', 'reload')

        if not enabled:
            for attachment in attachments:
                await run(['smbcontrol', 'smbd', 'close-share', attachment['name']], check=False)


async def setup(middleware):
    await middleware.call('pool.dataset.register_attachment_delegate', SMBFSAttachmentDelegate(middleware))
    middleware.register_hook('pool.post_import_pool', pool_post_import, sync=True)
