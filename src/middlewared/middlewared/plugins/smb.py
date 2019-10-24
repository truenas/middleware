from middlewared.common.attachment import FSAttachmentDelegate
from middlewared.schema import Bool, Dict, IPAddr, List, Str, Int, Patch
from middlewared.service import (SystemServiceService, ValidationErrors,
                                 accepts, filterable, private, periodic, CRUDService)
from middlewared.async_validators import check_path_resides_within_volume
from middlewared.service_exception import CallError
from middlewared.utils import Popen, run, filter_list
from middlewared.utils.path import is_child

import asyncio
import codecs
import enum
import errno
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
RE_SHAREACLENTRY = re.compile(r"^ACL:(?P<ae_who_sid>.+):(?P<ae_type>.+)\/0x0\/(?P<ae_perm>.+)$")


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
    SHARESEC = '/usr/local/bin/sharesec'
    SMBCONTROL = '/usr/local/bin/smbcontrol'
    SMBPASSWD = '/usr/local/bin/smbpasswd'
    WBINFO = '/usr/local/bin/wbinfo'


class SIDType(enum.IntEnum):
    """
    Defined in MS-SAMR (2.2.2.3) and lsa.idl
    Samba's group mapping database will primarily contain SID_NAME_ALIAS entries (local groups)
    """
    NONE = 0
    USER = 1
    DOM_GROUP = 2
    DOMAIN = 3
    ALIAS = 4
    WELL_KNOWN_GROUP = 5
    DELETED = 6
    INVALID = 7
    UNKNOWN = 8
    COMPUTER = 9
    LABEL = 10


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

    @accepts()
    async def bindip_choices(self):
        """
        List of valid choices for IP addresses to which to bind the SMB service.
        Addresses assigned by DHCP are excluded from the results.
        """
        choices = {}
        for i in await self.middleware.call('interface.query'):
            for alias in i['aliases']:
                choices[alias['address']] = alias['address']
        return choices

    @accepts()
    async def domain_choices(self):
        """
        List of domains visible to winbindd. Returns empty list if winbindd is
        stopped.
        """
        domains = []
        wb = await run([SMBCmd.WBINFO.value, '-m'], check=False)
        if wb.returncode == 0:
            domains = wb.stdout.decode().splitlines()

        return domains

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
            [SMBCmd.NET.value, 'groupmap', 'listmem', 'S-1-5-32-544'],
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
                    [SMBCmd.NET.value, 'groupmap', 'delmem', 'S-1-5-32-544', group],
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
        group = await self.middleware.call("dscache.get_uncached_group", admin_group)
        if not group:
            verrors.add('smb_update.admin_group', f"Failed to validate group: {admin_group}")
            raise verrors

        sid = await self.wbinfo_gidtosid(group['gr_gid'])
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
            [SMBCmd.NET.value, '-d', '0', 'groupmap', 'add', 'type=local', f'unixgroup={group}', f'ntgroup={group}'],
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
                try:
                    pdbentries.append({
                        'username': entry[0],
                        'full_name': entry[2],
                        'uid': entry[1],
                    })
                except Exception as e:
                    self.logger.debug('Failed to parse passdb entry [%s]: %s', p, e)

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
        Str('netbiosname', max_length=15),
        Str('netbiosname_b', max_length=15),
        List('netbiosalias', default=[], items=[Str('netbios_alias', max_length=15)]),
        Str('workgroup'),
        Str('description'),
        Bool('enable_smb1'),
        Str('unixcharset'),
        Str('loglevel', enum=['NONE', 'MINIMUM', 'NORMAL', 'FULL', 'DEBUG']),
        Bool('syslog'),
        Bool('localmaster'),
        Str('guest'),
        Str('admin_group', required=False, default=None, null=True),
        Str('filemask'),
        Str('dirmask'),
        Bool('zeroconf'),
        Bool('ntlmv1_auth'),
        List('bindip', items=[IPAddr('ip')], default=[]),
        Str('smb_options', max_length=None),
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

        if data.get('bindip'):
            bindip_choices = list((await self.bindip_choices()).keys())
            for idx, item in enumerate(data['bindip']):
                if item not in bindip_choices:
                    verrors.add(f'smb_update.bindip.{idx}', f'IP address [{item}] is not a configured address for this server')

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
        Str('name', max_length=80),
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
        List('vfsobjects', default=['ixnas', 'streams_xattr']),
        Bool('shadowcopy', default=False),
        Str('auxsmbconf', max_length=None),
        Bool('enabled', default=True),
        register=True
    ))
    async def do_create(self, data):
        """
        Create a SMB Share.

        `timemachine` when set, enables Time Machine backups for this share.

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

        return new

    @accepts(Int('id'))
    async def do_delete(self, id):
        """
        Delete SMB Share of `id`.
        """
        share = await self._get_instance(id)
        result = await self.middleware.call('datastore.delete', self._config.datastore, id)
        await self.middleware.call('smb.sharesec._delete', share['name'] if not share['home'] else 'homes')
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
        if 'share_acl' in data:
            data.pop('share_acl')

        return data

    @private
    async def compress(self, data):
        data['hostsallow'] = ' '.join(data['hostsallow'])
        data['hostsdeny'] = ' '.join(data['hostsdeny'])

        return data

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
        vfs_modules = [
            'audit',
            'catia',
            'crossrename',
            'dirsort',
            'fruit',
            'full_audit',
            'ixnas',
            'media_harmony',
            'noacl',
            'offline',
            'preopen',
            'shell_snap',
            'streams_xattr',
            'shadow_copy2',
            'winmsa',
            'zfs_space',
            'zfsacl'
        ]

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


class ShareSec(CRUDService):

    class Config:
        namespace = 'smb.sharesec'

    @private
    async def _parse_share_sd(self, sd, options=None):
        """
        Parses security descriptor text returned from 'sharesec'.
        Optionally will resolve the SIDs in the SD to names.
        """

        if len(sd) == 0:
            return {}
        parsed_share_sd = {'share_name': None, 'share_acl': []}
        if options is None:
            options = {'resolve_sids': True}

        sd_lines = sd.splitlines()
        # Share name is always enclosed in brackets. Remove them.
        parsed_share_sd['share_name'] = sd_lines[0][1:-1]

        # ACL entries begin at line 5 in the Security Descriptor
        for i in sd_lines[5:]:
            acl_entry = {}
            m = RE_SHAREACLENTRY.match(i)
            if m is None:
                self.logger.debug(f'{i} did not match regex')
                continue

            acl_entry.update(m.groupdict())
            if (options.get('resolve_sids', True)) is True:
                wb = await run([SMBCmd.WBINFO.value, '--sid-to-name', acl_entry['ae_who_sid']], check=False)
                if wb.returncode == 0:
                    wb_ret = wb.stdout.decode()[:-3].split('\\')
                    sidtypeint = int(wb.stdout.decode().strip()[-1:])
                    acl_entry['ae_who_name'] = {'domain': None, 'name': None, 'sidtype': SIDType.NONE}
                    acl_entry['ae_who_name']['domain'] = wb_ret[0]
                    acl_entry['ae_who_name']['name'] = wb_ret[1]
                    acl_entry['ae_who_name']['sidtype'] = SIDType(sidtypeint).name
                else:
                    self.logger.debug(
                        'Failed to resolve SID (%s) to name: (%s)' % (acl_entry['ae_who_sid'], wb.stderr.decode())
                    )

            parsed_share_sd['share_acl'].append(acl_entry)

        return parsed_share_sd

    @private
    async def _sharesec(self, **kwargs):
        """
        wrapper for sharesec(1). This manipulates share permissions on SMB file shares.
        The permissions are stored in share_info.tdb, and apply to the share as a whole.
        This is in contrast with filesystem permissions, which define the permissions for a file
        or directory, and in the latter case may also define permissions inheritance rules
        for newly created files in the directory. The SMB Share ACL only affects access through
        the SMB protocol.
        """
        action = kwargs.get('action')
        share = kwargs.get('share', '')
        args = kwargs.get('args', '')
        sharesec = await run([SMBCmd.SHARESEC.value, share, action, args], check=False)
        if sharesec.returncode != 0:
            raise CallError(f'sharesec {action} failed with error: {sharesec.stderr.decode()}')
        return sharesec.stdout.decode()

    @private
    async def _delete(self, share):
        """
        Delete stored SD for share. This should be performed when share is
        deleted.
        If share_info.tdb lacks an entry for the share, sharesec --delete
        will return -1 and NT_STATUS_NOT_FOUND. In this case, exception should not
        be raised.
        """
        try:
            await self._sharesec(action='--delete', share=share)
        except Exception as e:
            if 'NT_STATUS_NOT_FOUND' not in str(e):
                raise CallError(e)

    @private
    async def _view_all(self, options=None):
        """
        Return Security Descriptor for all shares.
        """
        share_sd_list = []
        idx = 1
        share_entries = (await self._sharesec(action='--view-all')).split('\n\n')
        for share in share_entries:
            parsed_sd = await self.middleware.call('smb.sharesec._parse_share_sd', share, options)
            if parsed_sd:
                parsed_sd.update({'id': idx})
                idx = idx + 1
                share_sd_list.append(parsed_sd)

        return share_sd_list

    @accepts(
        Str('share_name'),
        Dict(
            'options',
            Bool('resolve_sids', default=True)
        )
    )
    async def getacl(self, share_name, options):
        """
        View the ACL information for `share_name`. The share ACL is distinct from filesystem
        ACLs which can be viewed by calling `filesystem.getacl`. `ae_who_name` will appear
        as `None` if the SMB service is stopped or if winbind is unable  to resolve the SID
        to a name.

        If the `option` `resolve_sids` is set to `False` then the returned ACL will not
        contain names.
        """
        sharesec = await self._sharesec(action='--view', share=share_name)
        share_sd = f'[{share_name.upper()}]\n{sharesec}'
        return await self.middleware.call('smb.sharesec._parse_share_sd', share_sd, options)

    @private
    async def _ae_to_string(self, ae):
        """
        Convert aclentry in Securty Descriptor dictionary to string
        representation used by sharesec.
        """
        if not ae['ae_who_sid'] and not ae['ae_who_name']:
            raise CallError('ACL Entry must have ae_who_sid or ae_who_name.', errno.EINVAL)

        if not ae['ae_who_sid']:
            name = f'{ae["ae_who_name"]["domain"]}\\{ae["ae_who_name"]["name"]}'
            wbinfo = await run([SMBCmd.WBINFO.value, '--name-to-sid', name], check=False)
            if wbinfo.returncode != 0:
                raise CallError(f'SID lookup for {name} failed: {wbinfo.stderr.decode()}')
            ae['ae_who_sid'] = (wbinfo.stdout.decode().split())[0]

        return f'{ae["ae_who_sid"]}:{ae["ae_type"]}/0x0/{ae["ae_perm"]}'

    @private
    async def _string_to_ae(self, perm_str):
        """
        Convert string representation of SD into dictionary.
        """
        return (RE_SHAREACLENTRY.match(f'ACL:{perm_str}')).groupdict()

    @private
    async def setacl(self, data, db_commit=True):
        """
        Set an ACL on `share_name`. Changes are written to samba's share_info.tdb file.
        This only impacts SMB sessions. Either ae_who_sid or ae_who_name must be specified
        for each ACL entry in the `share_acl`. If both are specified, then ae_who_sid will be used.
        The SMB service must be started in order to convert ae_who_name to a SID if those are
        used.

        `share_name` the name of the share

        `share_acl` a list of ACL entries (dictionaries) with the following keys:

        `ae_who_sid` who the ACL entry applies to expressed as a Windows SID

        `ae_who_name` who the ACL entry applies to expressed as a name. `ae_who_name` must
        be prefixed with the domain that the user is a member of. Local users will have the
        netbios name of the SMB server as a prefix. Example `freenas\\smbusers`

        `ae_perm` string representation of the permissions granted to the user or group.
        `FULL` grants read, write, execute, delete, write acl, and change owner.
        `CHANGE` grants read, write, execute, and delete.
        `READ` grants read and execute.

        `ae_type` can be ALLOWED or DENIED.
        """
        ae_list = []
        data['share_name']
        for entry in data['share_acl']:
            ae_list.append(await self._ae_to_string(entry))

        await self._sharesec(share=data['share_name'], action='--replace', args=','.join(ae_list))
        if not db_commit:
            return

        config_share = await self.middleware.call('sharing.smb.query', [('name', '=', data['share_name'])], {'get': True})
        await self.middleware.call('datastore.update', 'sharing.cifs_share', config_share['id'],
                                   {'cifs_share_acl': ' '.join(ae_list)})

    @private
    async def _flush_share_info(self):
        """
        Write stored share acls to share_info.tdb. This should only be called
        if share_info.tdb contains default entries.
        """
        shares = await self.middleware.call('datastore.query', 'sharing.cifs_share', [], {'prefix': 'cifs_'})
        for share in shares:
            if share['share_acl']:
                await self._sharesec(
                    share=share['name'],
                    action='--replace',
                    args=','.join(share['share_acl'].split())
                )

    @periodic(3600, run_on_start=False)
    @private
    async def check_share_info_tdb(self):
        """
        Use cached mtime value for share_info.tdb to determine whether
        to sync it up with what is stored in the freenas configuration file.
        Samba will run normally if share_info.tdb does not exist (it will automatically
        generate entries granting full control to world in this case). In this situation,
        immediately call _flush_share_info.
        """
        old_mtime = 0
        statedir = await self.middleware.call('smb.getparm', 'state directory', 'global')
        shareinfo = f'{statedir}/share_info.tdb'
        if not os.path.exists(shareinfo):
            if not await self.middleware.call('service.started', 'cifs'):
                return
            else:
                await self._flush_share_info()
                return

        if await self.middleware.call('cache.has_key', 'SHAREINFO_MTIME'):
            old_mtime = await self.middleware.call('cache.get', 'SHAREINFO_MTIME')

        if old_mtime == (os.stat(shareinfo)).st_mtime:
            return

        await self.middleware.call('smb.sharesec.synchronize_acls')
        await self.middleware.call('cache.put', 'SHAREINFO_MTIME', (os.stat(shareinfo)).st_mtime)

    @accepts()
    async def synchronize_acls(self):
        """
        Synchronize the share ACL stored in the config database with Samba's running
        configuration as reflected in the share_info.tdb file.

        The only situation in which the configuration stored in the database will
        overwrite samba's running configuration is if share_info.tdb is empty. Samba
        fakes a single S-1-1-0:ALLOW/0x0/FULL entry in the absence of an entry for a
        share in share_info.tdb.
        """
        rc = await self.middleware.call('smb.sharesec._view_all', {'resolve_sids': False})
        write_share_info = True

        for i in rc:
            if len(i['share_acl']) > 1:
                write_share_info = False
                break

            if i['share_acl'][0]['ae_who_sid'] != 'S-1-1-0' or i['share_acl'][0]['ae_perm'] != 'FULL':
                write_share_info = False
                break

        if write_share_info:
            return await self._flush_share_info()

        shares = await self.middleware.call('datastore.query', 'sharing.cifs_share', [], {'prefix': 'cifs_'})
        for s in shares:
            rc_info = (list(filter(lambda x: s['name'] == x['share_name'], rc)))[0]
            rc_acl = ' '.join([(await self._ae_to_string(i)) for i in rc_info['share_acl']])
            if rc_acl != s['share_acl']:
                self.logger.debug('updating stored ACL on %s to %s', s['name'], rc_acl)
                await self.middleware.call(
                    'datastore.update',
                    'sharing.cifs_share',
                    s['id'],
                    {'cifs_share_acl': rc_acl}
                )

    @filterable
    async def query(self, filters=None, options=None):
        """
        Use query-filters to search the SMB share ACLs present on server.
        """
        share_acls = await self._view_all({'resolve_sids': True})
        ret = filter_list(share_acls, filters, options)
        return ret

    @accepts(Dict(
        'smbsharesec_create',
        Str('share_name', required=True),
        List(
            'share_acl',
            items=[
                Dict(
                    'aclentry',
                    Str('ae_who_sid', default=None),
                    Dict(
                        'ae_who_name',
                        Str('domain', default=''),
                        Str('name', default=''),
                        default=None
                    ),
                    Str('ae_perm', enum=['FULL', 'CHANGE', 'READ']),
                    Str('ae_type', enum=['ALLOWED', 'DENIED'])
                )
            ],
            default=[{'ae_who_sid': 'S-1-1-0', 'ae_perm': 'FULL', 'ae_type': 'ALLOWED'}])
    ))
    async def do_create(self, data):
        """
        Update the ACL on a given SMB share. Will write changes to both
        /var/db/system/samba4/share_info.tdb and the configuration file.
        Since an SMB share will _always_ have an ACL present, there is little
        distinction between the `create` and `update` methods apart from arguments.

        `share_name` - name of SMB share.

        `share_acl` a list of ACL entries (dictionaries) with the following keys:

        `ae_who_sid` who the ACL entry applies to expressed as a Windows SID

        `ae_who_name` who the ACL entry applies to expressed as a name. `ae_who_name` is
        a dictionary containing the following keys: `domain` that the user is a member of,
        `name` username in the domain. The domain for local users is the netbios name of
        the FreeNAS server.

        `ae_perm` string representation of the permissions granted to the user or group.
        `FULL` grants read, write, execute, delete, write acl, and change owner.
        `CHANGE` grants read, write, execute, and delete.
        `READ` grants read and execute.

        `ae_type` can be ALLOWED or DENIED.
        """
        await self.setacl(data)

    @accepts(
        Int('id', required=True),
        Dict(
            'smbsharesec_update',
            List(
                'share_acl',
                items=[
                    Dict(
                        'aclentry',
                        Str('ae_who_sid', default=None),
                        Dict(
                            'ae_who_name',
                            Str('domain', default=''),
                            Str('name', default=''),
                            default=None
                        ),
                        Str('ae_perm', enum=['FULL', 'CHANGE', 'READ']),
                        Str('ae_type', enum=['ALLOWED', 'DENIED']))
                ],
                default=[{'ae_who_sid': 'S-1-1-0', 'ae_perm': 'FULL', 'ae_type': 'ALLOWED'}]
            )
        )
    )
    async def do_update(self, id, data):
        """
        Update the ACL on the share specified by the numerical index `id`. Will write changes
        to both /var/db/system/samba4/share_info.tdb and the configuration file.
        """
        old_acl = await self._get_instance(id)
        await self.setacl({"share_name": old_acl["share_name"], "share_acl": data["share_acl"]})
        return await self.getacl(old_acl["share_name"])

    @accepts(Str('id_or_name', required=True))
    async def do_delete(self, id_or_name):
        """
        Replace share ACL for the specified SMB share with the samba default ACL of S-1-1-0/FULL
        (Everyone - Full Control). In this case, access will be fully determined
        by the underlying filesystem ACLs and smb4.conf parameters governing access control
        and permissions.
        Share can be deleted by name or numerical by numerical index.
        """
        new_acl = {'share_acl': [
            {'ae_who_sid': 'S-1-1-0', 'ae_perm': 'FULL', 'ae_type': 'ALLOWED'}
        ]}
        if not id_or_name.isdigit():
            old_acl = await self.getacl(id_or_name)
            new_acl.update({'share_name': id_or_name})
        else:
            old_acl = await self._get_instance(int(id_or_name))
            new_acl.update({'share_name': old_acl['share_name']})

        await self.setacl(new_acl)
        return old_acl


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
                await run([SMBCmd.SMBCONTROL.value, 'smbd', 'close-share', attachment['name']], check=False)


async def setup(middleware):
    await middleware.call('pool.dataset.register_attachment_delegate', SMBFSAttachmentDelegate(middleware))
    middleware.register_hook('pool.post_import_pool', pool_post_import, sync=True)
