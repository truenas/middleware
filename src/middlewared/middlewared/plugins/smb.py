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
import os
import platform
import re
import subprocess
import uuid

try:
    from samba import param
except ImportError:
    param = None

IS_LINUX = platform.system().lower() == 'linux'

LOGLEVEL_MAP = {
    '0': 'NONE',
    '1': 'MINIMUM',
    '2': 'NORMAL',
    '3': 'FULL',
    '10': 'DEBUG',
}
RE_NETBIOSNAME = re.compile(r"^[a-zA-Z0-9\.\-_!@#\$%^&\(\)'\{\}~]{1,15}$")


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
    NET = 'net'
    PDBEDIT = 'pdbedit'
    SHARESEC = 'sharesec'
    SMBCONTROL = 'smbcontrol'
    SMBPASSWD = 'smbpasswd'
    WBINFO = 'wbinfo'


class SMBPath(enum.Enum):
    GLOBALCONF = ('/usr/local/etc/smb4.conf', '/etc/smb.conf')
    SHARECONF = ('/usr/local/etc/smb4_share.conf', '/etc/smb_share.conf')
    STATEDIR = ('/var/db/system/samba4', '/var/db/system/samba4')
    PRIVATEDIR = ('/var/db/system/samba4/private', '/var/db/system/samba4')
    LEGACYPRIVATE = ('/root/samba/private', '/root/samba/private')
    RUNDIR = ('/var/run/samba4', '/var/run/samba')
    LOCKDIR = ('/var/lock', '/var/lock')
    LOGDIR = ('/var/log/samba4', '/var/log/samba')

    def platform(self):
        return self.value[1] if IS_LINUX else self.value[0]


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
    def getparm(self, parm, section):
        """
        Get a parameter from the smb4.conf file. This is more reliable than
        'testparm --parameter-name'. testparm will fail in a variety of
        conditions without returning the parameter's value.
        """
        try:
            if section.upper() == 'GLOBAL':
                return param.LoadParm(SMBPath.GLOBALCONF.platform()).get(parm, section)
            else:
                return self.middleware.call_sync('sharing.smb.reg_getparm', section, parm)

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
