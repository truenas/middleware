from middlewared.common.attachment import FSAttachmentDelegate
from middlewared.schema import Bool, Dict, IPAddr, List, Str, Int, Patch
from middlewared.service import (SystemServiceService, ValidationErrors,
                                 accepts, private, CRUDService)
from middlewared.async_validators import check_path_resides_within_volume
from middlewared.service_exception import CallError
import middlewared.sqlalchemy as sa
from middlewared.utils import Popen, run
from middlewared.utils.path import is_child

import asyncio
import codecs
import enum
import errno
import os
import re
import subprocess
import uuid

try:
    from samba import param
except ImportError:
    param = None

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
    'legacy' - Two samba instances simultaneously running on active and standby controllers with no shared state.
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


class SMBPath(enum.Enum):
    GLOBALCONF = '/usr/local/etc/smb4.conf'
    SHARECONF = '/usr/local/etc/smb4_share.conf'
    STATEDIR = '/var/db/system/samba4'
    PRIVATEDIR = '/var/db/system/samba4/private'
    LEGACYPRIVATE = '/root/samba/private'
    RUNDIR = '/var/run/samba4'
    LOCKDIR = '/var/lock'
    LOGDIR = '/var/log/samba4'


class SMBModel(sa.Model):
    __tablename__ = 'services_cifs'

    id = sa.Column(sa.Integer(), primary_key=True)
    cifs_srv_netbiosname = sa.Column(sa.String(120))
    cifs_srv_netbiosname_b = sa.Column(sa.String(120), nullable=True)
    cifs_srv_netbiosalias = sa.Column(sa.String(120), nullable=True)
    cifs_srv_workgroup = sa.Column(sa.String(120))
    cifs_srv_description = sa.Column(sa.String(120))
    cifs_srv_unixcharset = sa.Column(sa.String(120), default="UTF-8")
    cifs_srv_loglevel = sa.Column(sa.String(120), default="0")
    cifs_srv_syslog = sa.Column(sa.Boolean(), default=False)
    cifs_srv_localmaster = sa.Column(sa.Boolean(), default=False)
    cifs_srv_guest = sa.Column(sa.String(120), default="nobody")
    cifs_srv_filemask = sa.Column(sa.String(120))
    cifs_srv_dirmask = sa.Column(sa.String(120))
    cifs_srv_smb_options = sa.Column(sa.Text())
    cifs_srv_aio_enable = sa.Column(sa.Boolean(), default=False)
    cifs_srv_aio_rs = sa.Column(sa.Integer(), default=4096)
    cifs_srv_aio_ws = sa.Column(sa.Integer(), default=4096)
    cifs_srv_zeroconf = sa.Column(sa.Boolean(), default=True)
    cifs_srv_bindip = sa.Column(sa.MultiSelectField(), nullable=True)
    cifs_SID = sa.Column(sa.String(120), nullable=True)
    cifs_srv_ntlmv1_auth = sa.Column(sa.Boolean(), default=False)
    cifs_srv_enable_smb1 = sa.Column(sa.Boolean(), default=False)
    cifs_srv_admin_group = sa.Column(sa.String(120), nullable=True, default="")


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
    async def groupmap_delete(self, ntgroup=None, sid=None):
        if not ntgroup and not sid:
            raise CallError("ntgroup or sid is required")

        if ntgroup:
            target = f"ntgroup={ntgroup}"
        elif sid:
            target = f"sid={sid}"

        gm_delete = await run(
            [SMBCmd.NET.value, '-d' '0', 'groupmap', 'delete', target], check=False
        )

        if gm_delete.returncode != 0:
            self.logger.debug(f'Failed to delete groupmap for [{target}]: ({gm_delete.stderr.decode()})')

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
            res = param.LoadParm(SMBPath.GLOBALCONF.value).get(parm, section)
            return res
        except Exception as e:
            raise CallError(f'Attempt to query smb4.conf parameter [{parm}] failed with error: {e}')

    @private
    async def get_smb_ha_mode(self):
        if await self.middleware.call('cache.has_key', 'SMB_HA_MODE'):
            return await self.middleware.call('cache.get', 'SMB_HA_MODE')

        if not await self.middleware.call('system.is_freenas') and await self.middleware.call('failover.licensed'):
            system_dataset = await self.middleware.call('systemdataset.config')
            if system_dataset['pool'] != await self.middleware.call('boot.pool_name'):
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


class SharingSMBModel(sa.Model):
    __tablename__ = 'sharing_cifs_share'

    id = sa.Column(sa.Integer(), primary_key=True)
    cifs_path = sa.Column(sa.String(255), nullable=True)
    cifs_home = sa.Column(sa.Boolean(), default=False)
    cifs_name = sa.Column(sa.String(120))
    cifs_comment = sa.Column(sa.String(120))
    cifs_ro = sa.Column(sa.Boolean(), default=False)
    cifs_browsable = sa.Column(sa.Boolean(), default=True)
    cifs_recyclebin = sa.Column(sa.Boolean(), default=False)
    cifs_showhiddenfiles = sa.Column(sa.Boolean(), default=False)
    cifs_guestok = sa.Column(sa.Boolean(), default=False)
    cifs_guestonly = sa.Column(sa.Boolean(), default=False)
    cifs_hostsallow = sa.Column(sa.Text())
    cifs_hostsdeny = sa.Column(sa.Text())
    cifs_vfsobjects = sa.Column(sa.MultiSelectField(), default=['ixnas', 'streams_xattr'])
    cifs_auxsmbconf = sa.Column(sa.Text())
    cifs_abe = sa.Column(sa.Boolean())
    cifs_timemachine = sa.Column(sa.Boolean(), default=False)
    cifs_vuid = sa.Column(sa.String(36))
    cifs_shadowcopy = sa.Column(sa.Boolean())
    cifs_fsrvp = sa.Column(sa.Boolean())
    cifs_enabled = sa.Column(sa.Boolean(), default=True)
    cifs_share_acl = sa.Column(sa.Text())


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
        Str('comment', default=''),
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
        Bool('shadowcopy', default=True),
        Bool('fsrvp', default=False),
        Str('auxsmbconf', max_length=None, default=''),
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

        await self.reg_addshare(data)
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
        oldname = 'homes' if old['home'] else old['name']
        newname = 'homes' if new['home'] else new['name']

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

        if newname != oldname:
            # This is disruptive change. Share is actually being removed and replaced.
            # Forcibly closes any existing SMB sessions.
            await self.close_share(oldname)
            try:
                await self._reg_delshare(oldname)
            except Exception:
                self.logger.warn('Failed to remove stale share [%]',
                                 old['name'], exc_info=True)
            await self.reg_addshare(new)
        else:
            diff = await self.diff_middleware_and_registry(new['name'], new)
            await self.apply_conf_diff('REGISTRY', new['name'], diff)

        await self.extend(new)  # same here ?

        await self._service_change('cifs', 'reload')

        return new

    @accepts(Int('id'))
    async def do_delete(self, id):
        """
        Delete SMB Share of `id`. This will forcibly disconnect SMB clients
        that are accessing the share.
        """
        share = await self._get_instance(id)
        result = await self.middleware.call('datastore.delete', self._config.datastore, id)
        await self.close_share(share['name'])
        try:
            await self.middleware.call('smb.sharesec._delete', share['name'] if not share['home'] else 'homes')
        except Exception:
            self.logger.debug('Failed to delete share ACL for [%s].', share['name'], exc_info=True)

        try:
            await self._reg_delshare(share['name'] if not share['home'] else 'home')
        except Exception:
            self.logger.warn('Failed to remove registry entry for [%s].', share['name'], exc_info=True)

        if share['timemachine']:
            await self.middleware.call('mdnsadvertise.restart')

        return result

    @private
    async def close_share(self, share_name):
        c = await run([SMBCmd.SMBCONTROL.value, 'smbd', 'close-share', share_name], check=False)
        if c.returncode != 0:
            self.logger.warn('Failed to close smb share [%s]: [%s]',
                             share_name, c.stderr.decode().strip())

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

    @private
    async def netconf(self, **kwargs):
        """
        wrapper for net(8) conf. This manages the share configuration, which is stored in
        samba's registry.tdb file.
        """
        action = kwargs.get('action')
        if action not in ['listshares', 'showshare', 'addshare', 'delshare', 'setparm', 'delparm']:
            raise CallError(f'Action [{action}] is not permitted.', errno.EPERM)

        share = kwargs.get('share')
        args = kwargs.get('args', [])
        cmd = [SMBCmd.NET.value, 'conf', action]

        if share:
            cmd.append(share)

        if args:
            cmd.extend(args)

        netconf = await run(cmd, check=False)
        if netconf.returncode != 0:
            self.logger.debug('netconf failure stdout: %s', netconf.stdout.decode())
            raise CallError(
                f'net conf {action} failed with error: {netconf.stderr.decode()}'
            )

        return netconf.stdout.decode()

    @private
    async def reg_listshares(self):
        return (await self.netconf(action='listshares')).splitlines()

    @private
    async def reg_addshare(self, data):
        conf = await self.share_to_smbconf(data)
        path = conf.pop('path')
        name = 'homes' if data['home'] else data['name']
        await self.netconf(
            action='addshare',
            share=name,
            args=[path, f'writeable={"N" if data["ro"] else "y"}',
                  f'guest_ok={"y" if data["guestok"] else "N"}']
        )
        for k, v in conf.items():
            await self.reg_setparm(name, k, v)

    @private
    async def _reg_delshare(self, share):
        return await self.netconf(action='delshare', share=share)

    @private
    async def _reg_showshare(self, share):
        ret = {}
        to_list = ['vfs objects', 'hosts allow', 'hosts deny']
        net = await self.netconf(action='showshare', share=share)
        for param in net.splitlines()[1:]:
            kv = param.strip().split('=', 1)
            k = kv[0].strip()
            v = kv[1].strip()
            ret[k] = v if k not in to_list else v.split()

        return ret

    @private
    async def reg_setparm(self, share, parm, value):
        if type(value) == list:
            value = ' '.join(value)
        return await self.netconf(action='setparm', share=share, args=[parm, value])

    @private
    async def reg_delparm(self, share, parm):
        return await self.netconf(action='delparm', share=share, args=[parm])

    @private
    async def get_global_params(self, globalconf):
        if globalconf is None:
            globalconf = {}

        gl = {}
        gl.update({
            'fruit_enabled': globalconf.get('fruit_enabled', None),
            'ad_enabled': globalconf.get('ad_enabled', None),
            'afp_shares': globalconf.get('afp_shares', None),
            'nfs_exports': globalconf.get('nfs_exports', None),
            'smb_shares': globalconf.get('nfs_exports', None)
        })
        if gl['afp_shares'] is None:
            gl['afp_shares'] = await self.middleware.call('sharing.afp.query', [['enabled', '=', True]])
        if gl['nfs_exports'] is None:
            gl['nfs_exports'] = await self.middleware.call('sharing.nfs.query', [['enabled', '=', True]])
        if gl['smb_shares'] is None:
            gl['smb_shares'] = await self.middleware.call('sharing.smb.query', [['enabled', '=', True]])
        if gl['ad_enabled'] is None:
            gl['ad_enabled'] = False if (await self.middleware.call('activedirectory.get_state')) == "DISABLED" else True

        if gl['fruit_enabled'] is None:
            for share in gl['smb_shares']:
                if "fruit" in share['vfsobjects'] or share['timemachine']:
                    gl['fruit_enabled'] = True
                    break
        return gl

    @private
    async def order_vfs_objects(self, vfs_objects):
        vfs_objects_special = ('shadow_copy_zfs', 'catia', 'zfs_space', 'noacl', 'ixnas', 'zfsacl',
                               'fruit', 'streams_xattr', 'crossrename', 'recycle')
        vfs_objects_ordered = []

        if 'fruit' in vfs_objects:
            if 'streams_xattr' not in vfs_objects:
                vfs_objects.append('streams_xattr')

        if 'noacl' in vfs_objects:
            if 'ixnas' in vfs_objects:
                vfs_objects.remove('ixnas')

        for obj in vfs_objects:
            if obj not in vfs_objects_special:
                vfs_objects_ordered.append(obj)

        for obj in vfs_objects_special:
            if obj in vfs_objects:
                vfs_objects_ordered.append(obj)

        return vfs_objects_ordered

    @private
    async def diff_middleware_and_registry(self, share, data):
        if share is None:
            raise CallError('Share name must be specified.')

        if data is None:
            data = await self.query([('name', '=', share)], {'get': True})

        share_conf = await self.share_to_smbconf(data)
        reg_conf = await self._reg_showshare(share)
        s_keys = set(share_conf.keys())
        r_keys = set(reg_conf.keys())
        intersect = s_keys.intersection(r_keys)
        return {
            'added': {x: share_conf[x] for x in s_keys - r_keys},
            'removed': {x: reg_conf[x] for x in r_keys - s_keys},
            'modified': {x: (share_conf[x], reg_conf[x]) for x in intersect if share_conf[x] != reg_conf[x]},
        }

    @private
    async def apply_conf_registry(self, share, diff):
        for k, v in diff['added'].items():
            await self.reg_setparm(share, k, v)

        for k, v in diff['removed'].items():
            await self.reg_delparm(share, k)

        for k, v in diff['modified'].items():
            await self.reg_setparm(share, k, v[0])

    @private
    async def apply_conf_diff(self, target, share, confdiff):
        self.logger.trace('target: [%s], share: [%s], diff: [%s]',
                          target, share, confdiff)
        if target not in ['REGISTRY', 'FNCONF']:
            raise CallError(f'Invalid target: [{target}]', errno.EINVAL)

        if target == 'FNCONF':
            # TODO: add ability to convert the registry back to our sqlite table
            raise CallError('FNCONF target not implemented')

        return await self.apply_conf_registry(share, confdiff)

    @private
    async def share_to_smbconf(self, data, globalconf=None):
        gl = await self.get_global_params(globalconf)
        conf = {}
        conf['path'] = data['path']
        if data['comment']:
            conf["comment"] = data['comment']
        if not data['browsable']:
            conf["browseable"] = "no"
        if data['guestonly']:
            conf["guest only"] = "yes"
        if data['showhiddenfiles']:
            conf["hide dot files"] = "no"
        if data['abe']:
            conf["access based share enum"] = "yes"
        if data['hostsallow']:
            conf["hosts allow"] = data['hostsallow']
        if data['hostsdeny']:
            conf["hosts deny"] = data['hostsdeny']
        conf["read only"] = "no" if data['ro'] else "yes"
        conf["guest ok"] = "yes" if data['guestok'] else "no"

        if any(filter(lambda x: f"{x['path']}/" in f"{conf['path']}/" or f"{conf['path']}/" in f"{x['path']}/", gl['afp_shares'])):
            self.logger.debug("SMB share [%s] is also an AFP share. "
                              "Applying parameters for mixed-protocol share.", data['name'])
            conf.update({
                "fruit:locking": "netatalk",
                "strict locking": "auto",
                "streams_xattr:prefix": "user.",
                "streams_xattr:store_stream_type": "no"
            })

        nfs_path_list = []
        for export in gl['nfs_exports']:
            nfs_path_list.extend(export['paths'])

        if any(filter(lambda x: f"{conf['path']}/" in f"{x}/", nfs_path_list)):
            self.logger.debug("SMB share [%s] is also an NFS export. "
                              "Applying parameters for mixed-protocol share.", data['name'])
            conf.update({
                "strict locking": "yes",
                "level2 oplocks": "no",
                "oplocks": "no"
            })

        if gl['fruit_enabled']:
            if "fruit" not in data['vfsobjects']:
                data['vfsobjects'].append('fruit')

        if data['recyclebin']:
            # crossrename is required for 'recycle' to work across sub-datasets
            # FIXME: crossrename imposes 20MB limit on filesize moves across mountpoints
            # This really needs to be addressed with a zfs-aware recycle bin.
            data['vfsobjects'].extend(['recycle', 'crossrename'])

        if data['shadowcopy'] or data['fsrvp']:
            data['vfsobjects'].append('shadow_copy_zfs')

        if data['fsrvp']:
            data['vfsobjects'].append('zfs_fsrvp')
            conf.update({
                "shadow:ignore_empty_snaps": "false",
                "shadow:include": "fss-*",
            })

        conf["vfs objects"] = await self.order_vfs_objects(data['vfsobjects'])
        if gl['fruit_enabled']:
            conf["fruit:metadata"] = "stream"
            conf["fruit:resource"] = "stream"

        if data['timemachine']:
            conf["fruit:time machine"] = "yes"
            conf["fruit:volume_uuid"] = data['vuid']

        if data['recyclebin']:
            conf.update({
                "recycle:repository": ".recycle/%D/%U" if gl['ad_enabled'] else ".recycle/%U",
                "recycle:keeptree": "yes",
                "recycle:keepversions": "yes",
                "recycle:touch": "yes",
                "recycle:directory_mode": "0777",
                "recycle:subdir_mode": "0700"
            })

        conf.update({
            "nfs4:chown": "true",
            "nfs4:acedup": "merge",
            "aio write size": "0",
            "mangled names": "illegal",
            "ea support": "false",
        })

        if data['home'] and gl['ad_enabled']:
            conf["path"] = f'{data["path"]}/%D/%U'
        elif data['home']:
            conf["path"] = f'{data["path"]}/%U'

        for param in data['auxsmbconf'].splitlines():
            if not param.strip():
                continue
            try:
                kv = param.split('=', 1)
                conf[kv[0].strip()] = kv[1].strip()
            except Exception:
                self.logger.debug("[%s] contains invalid auxiliary parameter: [%s]",
                                  data['name'], param)

        return conf

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
    middleware.register_hook('pool.post_import', pool_post_import, sync=True)
