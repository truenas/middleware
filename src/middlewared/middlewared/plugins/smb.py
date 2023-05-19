import asyncio
import codecs
import enum
import os
import re
from pathlib import Path
import stat
import subprocess
import uuid

from samba import param

from middlewared.common.attachment import LockableFSAttachmentDelegate
from middlewared.common.listen import SystemServiceListenMultipleDelegate
from middlewared.schema import Bool, Dict, IPAddr, List, Str, Int, Patch
from middlewared.schema import Path as SchemaPath
from middlewared.service import accepts, job, private, SharingService
from middlewared.service import TDBWrapConfigService, ValidationErrors, filterable
from middlewared.service_exception import CallError, MatchNotFound
from middlewared.plugins.smb_.smbconf.reg_global_smb import LOGLEVEL_MAP
import middlewared.sqlalchemy as sa
from middlewared.utils import filter_list, osc, Popen, run
from middlewared.utils.osc import getmntinfo
from middlewared.utils.path import FSLocation, path_location, is_child_realpath

RE_NETBIOSNAME = re.compile(r"^[a-zA-Z0-9\.\-_!@#\$%^&\(\)'\{\}~]{1,15}$")
CONFIGURED_SENTINEL = '/var/run/samba/.configured'


class SMBHAMODE(enum.IntEnum):
    """
    'standalone' - Not an HA system.
    'legacy' - Two samba instances simultaneously running on active and standby controllers with no shared state.
    'unified' - Single set of state files migrating between controllers. Single netbios name.
    """
    STANDALONE = 0
    UNIFIED = 2
    CLUSTERED = 3


class SMBCmd(enum.Enum):
    NET = 'net'
    PDBEDIT = 'pdbedit'
    SHARESEC = 'sharesec'
    SMBCACLS = 'smbcacls'
    SMBCONTROL = 'smbcontrol'
    SMBPASSWD = 'smbpasswd'
    STATUS = 'smbstatus'
    WBINFO = 'wbinfo'


class SMBBuiltin(enum.Enum):
    ADMINISTRATORS = ('builtin_administrators', 'S-1-5-32-544')
    GUESTS = ('builtin_guests', 'S-1-5-32-546')
    USERS = ('builtin_users', 'S-1-5-32-545')

    def unix_groups():
        return [x.value[0] for x in SMBBuiltin]

    def sids():
        return [x.value[1] for x in SMBBuiltin]

    def by_rid(rid):
        for x in SMBBuiltin:
            if x.value[1].endswith(str(rid)):
                return x

        return None


class SMBPath(enum.Enum):
    GLOBALCONF = ('/etc/smb4.conf', 0o755, False)
    STUBCONF = ('/usr/local/etc/smb4.conf', 0o755, False)
    SHARECONF = ('/etc/smb4_share.conf', 0o755, False)
    STATEDIR = ('/var/db/system/samba4', 0o755, True)
    PRIVATEDIR = ('/var/db/system/samba4/private', 0o700, True)
    LEGACYSTATE = ('/root/samba', 0o755, True)
    LEGACYPRIVATE = ('/root/samba/private', 0o700, True)
    CACHE_DIR = ('/var/run/samba-cache', 0o755, True)
    PASSDB_DIR = ('/var/run/samba-cache/private', 0o700, True)
    MSG_SOCK = ('/var/db/system/samba4/private/msg.sock', 0o700, False)
    RUNDIR = ('/var/run/samba', 0o755, True)
    LOCKDIR = ('/var/run/samba-lock', 0o755, True)
    LOGDIR = ('/var/log/samba4', 0o755, True)
    IPCSHARE = ('/tmp', 0o1777, True)
    WINBINDD_PRIVILEGED = ('/var/db/system/samba4/winbindd_privileged', 0o750, True)

    def platform(self):
        return self.value[0]

    def mode(self):
        return self.value[1]

    def is_dir(self):
        return self.value[2]


class SMBSharePreset(enum.Enum):
    NO_PRESET = {"verbose_name": "No presets", "params": {
        'auxsmbconf': '',
    }, "cluster": False}
    DEFAULT_CLUSTER_SHARE = {"verbose_name": "Default parameters for cluster share", "params": {
        'path_suffix': '',
        'home': False,
        'ro': False,
        'browsable': True,
        'timemachine': False,
        'recyclebin': False,
        'abe': False,
        'hostsallow': [],
        'hostsdeny': [],
        'aapl_name_mangling': False,
        'acl': True,
        'durablehandle': True,
        'shadowcopy': False,
        'streams': True,
        'fsrvp': False,
        'auxsmbconf': '',
    }, "cluster": True}
    DEFAULT_SHARE = {"verbose_name": "Default share parameters", "params": {
        'path_suffix': '',
        'home': False,
        'ro': False,
        'browsable': True,
        'timemachine': False,
        'recyclebin': False,
        'abe': False,
        'hostsallow': [],
        'hostsdeny': [],
        'aapl_name_mangling': False,
        'acl': True,
        'durablehandle': True,
        'shadowcopy': True,
        'streams': True,
        'fsrvp': False,
        'auxsmbconf': '',
    }, "cluster": False}
    TIMEMACHINE = {"verbose_name": "Basic time machine share", "params": {
        'path_suffix': '',
        'timemachine': True,
        'auxsmbconf': '',
    }, "cluster": False}
    ENHANCED_TIMEMACHINE = {"verbose_name": "Multi-user time machine", "params": {
        'path_suffix': '%U',
        'timemachine': True,
        'auxsmbconf': '\n'.join([
            'zfs_core:zfs_auto_create=true'
        ])
    }, "cluster": False}
    MULTI_PROTOCOL_NFS = {"verbose_name": "Multi-protocol (NFSv4/SMB) shares", "params": {
        'streams': True,
        'durablehandle': False,
        'auxsmbconf': '',
    }, "cluster": False}
    PRIVATE_DATASETS = {"verbose_name": "Private SMB Datasets and Shares", "params": {
        'path_suffix': '%U',
        'auxsmbconf': '\n'.join([
            'ixnas:zfs_auto_homedir=true' if osc.IS_FREEBSD else 'zfs_core:zfs_auto_create=true'
        ])
    }, "cluster": False}
    READ_ONLY = {"verbose_name": "Read-only share", "params": {
        'ro': True,
        'shadowcopy': False,
        'auxsmbconf': '',
    }, "cluster": True}
    WORM_DROPBOX = {"verbose_name": "SMB WORM. Files become readonly via SMB after 5 minutes", "params": {
        'path_suffix': '',
        'auxsmbconf': '\n'.join([
            'worm:grace_period = 300',
        ])
    }, "cluster": False}


class SMBModel(sa.Model):
    __tablename__ = 'services_cifs'

    id = sa.Column(sa.Integer(), primary_key=True)
    cifs_srv_netbiosname = sa.Column(sa.String(120))
    cifs_srv_netbiosalias = sa.Column(sa.String(120), nullable=True)
    cifs_srv_workgroup = sa.Column(sa.String(120))
    cifs_srv_description = sa.Column(sa.String(120))
    cifs_srv_unixcharset = sa.Column(sa.String(120), default="UTF-8")
    cifs_srv_loglevel = sa.Column(sa.String(120), default="0")
    cifs_srv_syslog = sa.Column(sa.Boolean(), default=False)
    cifs_srv_aapl_extensions = sa.Column(sa.Boolean(), default=False)
    cifs_srv_localmaster = sa.Column(sa.Boolean(), default=False)
    cifs_srv_guest = sa.Column(sa.String(120), default="nobody")
    cifs_srv_filemask = sa.Column(sa.String(120))
    cifs_srv_dirmask = sa.Column(sa.String(120))
    cifs_srv_smb_options = sa.Column(sa.Text())
    cifs_srv_bindip = sa.Column(sa.MultiSelectField())
    cifs_SID = sa.Column(sa.String(120), nullable=True)
    cifs_srv_ntlmv1_auth = sa.Column(sa.Boolean(), default=False)
    cifs_srv_enable_smb1 = sa.Column(sa.Boolean(), default=False)
    cifs_srv_admin_group = sa.Column(sa.String(120), nullable=True, default="")
    cifs_srv_next_rid = sa.Column(sa.Integer(), nullable=False)
    cifs_srv_secrets = sa.Column(sa.EncryptedText(), nullable=True)
    cifs_srv_multichannel = sa.Column(sa.Boolean, default=False)


class SMBService(TDBWrapConfigService):

    tdb_defaults = {
        "id": 1,
        "netbiosname": "truenas",
        "netbiosalias": [],
        "workgroup": "WORKGROUP",
        "description": "TrueNAS Server",
        "unixcharset": "UTF-8",
        "loglevel": "MINIMUM",
        "syslog": False,
        "aapl_extensions": False,
        "localmaster": True,
        "guest": "nobody",
        "filemask": "",
        "dirmask": "",
        "smb_options": "",
        "bindip": [],
        "cifs_SID": "",
        "ntlmv1_auth": False,
        "enable_smb1": False,
        "admin_group": None,
        "next_rid": -1,
        "multichannel": False,
        "netbiosname_local": "truenas"
    }

    class Config:
        service = 'cifs'
        service_verb = 'restart'
        datastore = 'services.cifs'
        datastore_extend = 'smb.smb_extend'
        datastore_prefix = 'cifs_srv_'
        cli_namespace = 'service.smb'

    LP_CTX = param.LoadParm(SMBPath.STUBCONF.platform())

    @private
    def is_configured(self):
        return os.path.exists(CONFIGURED_SENTINEL)

    @private
    def set_configured(self):
        with open(CONFIGURED_SENTINEL, "w"):
            pass

    @private
    async def smb_extend(self, smb):
        """Extend smb for netbios."""
        smb['netbiosname_local'] = smb['netbiosname']
        smb['netbiosalias'] = (smb['netbiosalias'] or '').split()
        smb['loglevel'] = LOGLEVEL_MAP.get(smb['loglevel'])
        smb.pop('secrets', None)
        return smb

    @private
    async def validate_netbios_name(self, name):
        return RE_NETBIOSNAME.match(name)

    @accepts()
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
        ha_mode = await self.get_smb_ha_mode()

        if ha_mode == 'CLUSTERED':
            for i in await self.middleware.call('ctdb.general.ips'):
                choices[i['public_ip']] = i['public_ip']

            return choices

        elif ha_mode == 'UNIFIED':
            master, backup, init = await self.middleware.call('failover.vip.get_states')
            for master_iface in await self.middleware.call('interface.query', [["id", "in", master + backup]]):
                for i in master_iface['failover_virtual_aliases']:
                    choices[i['address']] = i['address']

            return choices

        for i in await self.middleware.call('interface.ip_in_use'):
            choices[i['address']] = i['address']

        return choices

    @accepts()
    async def domain_choices(self):
        """
        List of domains visible to winbindd. Returns empty list if winbindd is
        stopped.
        """
        domains = await self.middleware.call('idmap.known_domains')
        return [dom['netbios_domain'] for dom in domains]

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
        ldap = await self.middleware.call('ldap.config')
        if not ldap['enable']:
            return True

        set_pass = await run([SMBCmd.SMBPASSWD.value, '-w', ldap['bindpw']], check=False)
        if set_pass.returncode != 0:
            self.logger.debug(f"Failed to set set ldap bindpw in secrets.tdb: {set_pass.stdout.decode()}")
            return False

        return True

    @private
    async def getparm_file(self, parm):
        with open(SMBPath.GLOBALCONF.platform(), "r") as f:
            for line in f:
                line = line.strip()
                if not line or line[0] in ["[", "#", ";"]:
                    continue

                try:
                    k, v = line.split("=", 1)
                except ValueError:
                    self.logger.warning("%s, SMB configuration file contains invalid line.", line)
                    continue

                k = k.strip()
                v = v.strip()

                if k.casefold() != parm.casefold():
                    continue

                if v.lower() in ("off", "false", "no"):
                    return False

                if v.lower() in ("on", "true", "yes"):
                    return True

                if v.isnumeric():
                    return int(v)

                return v

        raise MatchNotFound(parm)

    @private
    async def getparm(self, parm, section):
        """
        Get a parameter from the smb4.conf file. This is more reliable than
        'testparm --parameter-name'. testparm will fail in a variety of
        conditions without returning the parameter's value.

        First we try to retrieve the parameter from the registry. The registry will be populated
        with parameters that are explicilty set. It will not return for a value for an implicit default.

        Some basic global configuration parameters (such as "clustering") are not stored in the
        registry. This means that we need to read them from the configuration file. This only
        applies to global section.

        Finally, we fall through to retrieving the default value in Samba's param table
        through samba's param binding. This is initialized under a non-default loadparm context
        based on empty smb4.conf file.
        """
        ret = None
        try:
            ret = await self.middleware.call('sharing.smb.reg_getparm', section, parm)
        except Exception as e:
            if not section.upper() == 'GLOBAL':
                raise CallError(f'Attempt to query smb4.conf parameter [{parm}] failed with error: {e}')

        if ret:
            return ret

        try:
            if section.upper() == 'GLOBAL':
                return await self.getparm_file(parm)
        except MatchNotFound:
            pass
        except FileNotFoundError:
            self.logger.debug("%s: smb.conf file not generated. Returning default value.", parm)

        return self.LP_CTX.get(parm)

    @private
    async def get_next_rid(self, objtype, id):
        base_rid = 20000 if objtype == 'USER' else 200000
        return base_rid + id

    @private
    async def setup_directories(self):
        def create_dirs(spec, path):
            try:
                os.chmod(path, spec.mode())
                if os.stat(path).st_uid != 0:
                    self.logger.warning("%s: invalid owner for path. Correcting.", path)
                    os.chown(path, 0, 0)
            except FileNotFoundError:
                if spec.is_dir():
                    os.mkdir(path, spec.mode())

        await self.reset_smb_ha_mode()
        await self.middleware.call('etc.generate', 'smb')

        for p in SMBPath:
            if p == SMBPath.STATEDIR:
                path = await self.middleware.call("smb.getparm", "state directory", "global")
            elif p == SMBPath.PRIVATEDIR:
                path = await self.middleware.call("smb.getparm", "privatedir", "global")
            else:
                path = p.platform()

            try:
                if not await self.middleware.call('filesystem.acl_is_trivial', path):
                    self.logger.warning("Inappropriate ACL detected on path [%s] stripping ACL", path)
                    stripacl = await run(['setfacl', '-b', path], check=False)
                    if stripacl.returncode != 0:
                        self.logger.warning("Failed to strip ACL from path %s: %s", path,
                                            stripacl.stderr.decode())
            except CallError:
                # Currently only time CallError is raise here is on ENOENT, which may be expected
                pass

            await self.middleware.run_in_thread(create_dirs, p, path)

    @private
    async def import_conf_to_registry(self):
        drop = await run([SMBCmd.NET.value, 'conf', 'drop'], check=False)
        if drop.returncode != 0:
            self.logger.warning('failed to drop existing share config: %s',
                                drop.stderr.decode())
        load = await run([SMBCmd.NET.value, 'conf', 'import',
                          SMBPath.SHARECONF.platform()], check=False)
        if load.returncode != 0:
            self.logger.warning('failed to load share config: %s',
                                load.stderr.decode())

    @private
    async def ctdb_wait(self):
        while True:
            healthy = await self.middleware.call('ctdb.general.healthy')
            if healthy:
                return

            await asyncio.sleep(1)

    @private
    @job(lock="smb_configure")
    async def configure(self, job, create_paths=True):
        """
        Many samba-related tools will fail if they are unable to initialize
        a messaging context, which will happen if the samba-related directories
        do not exist or have incorrect permissions.
        """
        data = await self.config()
        ha_mode = SMBHAMODE[(await self.middleware.call('smb.get_smb_ha_mode'))]
        job.set_progress(0, 'Setting up SMB directories.')
        if create_paths:
            await self.setup_directories()

        job.set_progress(10, 'Generating stub SMB config.')
        await self.middleware.call('etc.generate', 'smb')

        """
        smb4.conf registry setup. The smb config is split between five
        different middleware plugins (smb, idmap, ad, ldap, sharing.smb).
        This initializes them in the above order so that configuration errors
        do not occur.
        """
        if ha_mode == SMBHAMODE.CLUSTERED:
            """
            Cluster should be healthy before we start synchonizing configuration.
            """
            job.set_progress(15, 'Waiting for ctdb to become healthy.')
            await self.ctdb_wait()

        job.set_progress(25, 'generating SMB, idmap, and directory service config.')
        await self.middleware.call('smb.initialize_globals')
        ad_enabled = (await self.middleware.call('activedirectory.config'))['enable']
        if ad_enabled:
            await self.middleware.call('activedirectory.synchronize')
            ldap_enabled = False
        else:
            ldap_enabled = (await self.middleware.call('ldap.config'))['enable']
            if ldap_enabled:
                await self.middleware.call('ldap.synchronize')

        await self.middleware.call('idmap.synchronize')

        """
        Since some NSS modules will default to setting home directory to /var/empty,
        verify that this path is immutable during setup for SMB service (prior to
        initializing directory services).
        """
        try:
            is_immutable = await self.middleware.call('filesystem.is_immutable', '/var/empty')
            if not is_immutable:
                await self.middleware.call('filesystem.set_immutable', True, '/var/empty')
        except Exception:
            self.logger.warning("Failed to set immutable flag on /var/empty", exc_info=True)

        job.set_progress(30, 'Setting up server SID.')
        await self.middleware.call('smb.set_sid', data['cifs_SID'])

        """
        If the ldap passdb backend is being used, then the remote LDAP server
        will provide the SMB users and groups. We skip these steps to avoid having
        samba potentially try to write our local users and groups to the remote
        LDAP server.

        Local users and groups are skipped on clustered servers. The assumption here is that
        other cluster nodes are maintaining state on users / groups.
        """
        passdb_backend = await self.middleware.call('smb.getparm', 'passdb backend', 'global')
        if ha_mode != SMBHAMODE.CLUSTERED and passdb_backend.startswith("tdbsam"):
            job.set_progress(40, 'Synchronizing passdb and groupmap.')
            await self.middleware.call('etc.generate', 'user')
            pdb_job = await self.middleware.call("smb.synchronize_passdb")
            grp_job = await self.middleware.call("smb.synchronize_group_mappings")
            await pdb_job.wait()
            await grp_job.wait()

        """
        The following steps ensure that we cleanly import our SMB shares
        into the registry.
        This step is not required when underlying database is clustered (cluster node should
        just recover with info from other nodes on reboot).
        """
        await self.middleware.call('smb.set_configured')
        job.set_progress(60, 'generating SMB share configuration.')
        await self.middleware.call('sharing.smb.sync_registry')

        """
        It is possible that system dataset was migrated or an upgrade
        wiped our secrets.tdb file. Re-import directory service secrets
        if they are missing from the current running configuration.
        """
        job.set_progress(65, 'Initializing directory services')
        await self.middleware.call(
            "directoryservices.initialize",
            {"activedirectory": ad_enabled, "ldap": ldap_enabled}
        )

        job.set_progress(70, 'Checking SMB server status.')
        if await self.middleware.call("service.started_or_enabled", "cifs"):
            job.set_progress(80, 'Restarting SMB service.')
            await self.middleware.call("service.restart", "cifs")
        job.set_progress(100, 'Finished configuring SMB.')

    @private
    async def configure_wait(self):
        """
        This method is possibly called by cifs service and idmap service start
        depending on whether system dataset setup was successful. Although
        a partially configured system dataset is a somewhat undefined state,
        it's best to at least try to get the SMB service working properly.

        Callers use response here to determine whether to make the start / restart
        operation a no-op.
        """
        if await self.middleware.call("smb.is_configured"):
            return True

        in_progress = await self.middleware.call("core.get_jobs", [
            ["method", "=", "smb.configure"],
            ["state", "=", "RUNNING"]
        ])
        if in_progress:
            return False

        self.logger.warning(
            "SMB service was not properly initialized. "
            "Attempting to configure SMB service."
        )
        conf_job = await self.middleware.call("smb.configure")
        await conf_job.wait(raise_error=True)
        return True

    @private
    async def get_smb_ha_mode(self):
        try:
            return await self.middleware.call('cache.get', 'SMB_HA_MODE')
        except KeyError:
            pass

        gl_enabled = (await self.middleware.call(
            'service.query', [('service', '=', 'glusterd')], {'get': True}
        ))['enable']

        if gl_enabled:
            hamode = SMBHAMODE['CLUSTERED'].name
        elif await self.middleware.call('failover.licensed'):
            hamode = SMBHAMODE['UNIFIED'].name

        else:
            hamode = SMBHAMODE['STANDALONE'].name

        await self.middleware.call('cache.put', 'SMB_HA_MODE', hamode)
        return hamode

    @private
    async def cluster_check(self):
        ha_mode = SMBHAMODE[(await self.middleware.call('smb.get_smb_ha_mode'))]
        if ha_mode != SMBHAMODE.CLUSTERED:
            return

        ctdb_healthy = await self.middleware.call('ctdb.general.healthy')
        if not ctdb_healthy:
            raise CallError("SMB-related changes are not permitted while cluster unhealthy.")

    @private
    async def reset_smb_ha_mode(self):
        await self.middleware.call('cache.pop', 'SMB_HA_MODE')
        return await self.get_smb_ha_mode()

    @private
    async def apply_aapl_changes(self):
        shares = await self.middleware.call('sharing.smb.query')
        for share in shares:
            diff = await self.middleware.call(
                'sharing.smb.diff_middleware_and_registry', share['name'], share
            )

            if diff is None:
                self.logger.warning("Share [%s] does not exist in registry.",
                                    share['name'])
                continue

            share_name = share['name'] if not share['home'] else 'homes'
            await self.middleware.call('sharing.smb.apply_conf_diff',
                                       share_name, diff)

    @private
    async def validate_smb(self, new, verrors):
        try:
            await self.middleware.call('sharing.smb.validate_aux_params',
                                       new['smb_options'],
                                       'smb_update.smb_options')
        except ValidationErrors as errs:
            verrors.add_child('smb_update.smb_options', errs)

        if new.get('unixcharset') and new['unixcharset'] not in await self.unixcharset_choices():
            verrors.add(
                'smb_update.unixcharset',
                'Please provide a valid value for unixcharset'
            )

        for i in ('workgroup', 'netbiosname', 'netbiosalias'):
            """
            There are two cases where NetBIOS names must be rejected:
            1. They contain invalid characters for NetBIOS protocol
            2. The name is identical to the NetBIOS workgroup.
            """
            if not new.get(i):
                """
                Skip validation on NULL or empty string. If parameter is required for
                the particular server configuration, then a separate validation error
                will be added in a later validation step.
                """
                continue

            if i == 'netbiosalias':
                for idx, item in enumerate(new[i]):
                    if not await self.validate_netbios_name(item):
                        verrors.add(f'smb_update.{i}.{idx}', f'Invalid NetBIOS name: {item}')
                    if item.casefold() == new['workgroup'].casefold():
                        verrors.add(
                            f'smb_update.{i}.{idx}',
                            f'NetBIOS alias [{item}] conflicts with workgroup name.'
                        )
            else:
                if not await self.validate_netbios_name(new[i]):
                    verrors.add(f'smb_update.{i}', f'Invalid NetBIOS name: {new[i]}')

                if i != 'workgroup' and new[i].casefold() == new['workgroup'].casefold():
                    verrors.add(
                        f'smb_update.{i}',
                        f'NetBIOS name [{new[i]}] conflicts with workgroup name.'
                    )

        if new['guest']:
            if new['guest'] == 'root':
                verrors.add('smb_update.guest', '"root" is not a permitted guest account')

            try:
                await self.middleware.call("user.get_user_obj", {"username": new["guest"]})
            except KeyError:
                verrors.add('smb_update.guest', f'{new["guest"]}: user does not exist')

        if new.get('bindip'):
            bindip_choices = list((await self.bindip_choices()).keys())
            for idx, item in enumerate(new['bindip']):
                if item not in bindip_choices:
                    verrors.add(
                        f'smb_update.bindip.{idx}',
                        f'IP address [{item}] is not a configured address for this server'
                    )

        if not new.get('workgroup'):
            verrors.add('smb_update.workgroup', 'workgroup field is required.')

        if not new.get('netbiosname'):
            verrors.add('smb_update.netbiosname', 'NetBIOS name is required.')

        for i in ('filemask', 'dirmask'):
            if not new[i]:
                continue
            try:
                if int(new[i], 8) & ~0o11777:
                    raise ValueError('Not an octet')
            except (ValueError, TypeError):
                verrors.add(f'smb_update.{i}', 'Not a valid mask')

        if not new['aapl_extensions']:
            filters = [['OR', [['afp', '=', True], ['timemachine', '=', True]]]]
            if await self.middleware.call('sharing.smb.query', filters, {'count': True}):
                verrors.add(
                    'smb_update.aapl_extensions',
                    'This option must be enabled when AFP or time machine shares are present'
                )

    @accepts(Dict(
        'smb_update',
        Str('netbiosname', max_length=15),
        Str('netbiosname_b', max_length=15),
        List('netbiosalias', items=[Str('netbios_alias', max_length=15)]),
        Str('workgroup'),
        Str('description'),
        Bool('enable_smb1'),
        Str('unixcharset'),
        Str('loglevel', enum=['NONE', 'MINIMUM', 'NORMAL', 'FULL', 'DEBUG']),
        Bool('syslog'),
        Bool('aapl_extensions'),
        Bool('localmaster'),
        Str('guest'),
        Str('admin_group', required=False, default=None, null=True),
        Str('filemask'),
        Str('dirmask'),
        Bool('ntlmv1_auth'),
        Bool('multichannel', default=False),
        List('bindip', items=[IPAddr('ip')]),
        Str('smb_options', max_length=None),
        update=True,
    ))
    async def do_update(self, data):
        """
        Update SMB Service Configuration.

        `netbiosname` defaults to the original hostname of the system.

        `netbiosalias` a list of netbios aliases. If Server is joined to an AD domain, additional Kerberos
        Service Principal Names will be generated for these aliases.

        `workgroup` specifies the NetBIOS workgroup to which the TrueNAS server belongs. This will be
        automatically set to the correct value during the process of joining an AD domain.
        NOTE: `workgroup` and `netbiosname` should have different values.

        `enable_smb1` allows legacy SMB clients to connect to the server when enabled.

        `aapl_extensions` enables support for SMB2 protocol extensions for MacOS clients. This is not a
        requirement for MacOS support, but is currently a requirement for time machine support.

        `localmaster` when set, determines if the system participates in a browser election.

        `guest` attribute is specified to select the account to be used for guest access. It defaults to "nobody".

        The group specified as the SMB `admin_group` will be automatically added as a foreign group member
        of S-1-5-32-544 (builtin\admins). This will afford the group all privileges granted to a local admin.
        Any SMB group may be selected (including AD groups).

        `ntlmv1_auth` enables a legacy and insecure authentication method, which may be required for legacy or
        poorly-implemented SMB clients.

        `smb_options` smb.conf parameters that are not covered by the above supported configuration options may be
        added as an smb_option. Not all options are tested or supported, and behavior of smb_options may change
        between releases. Stability of smb.conf options is not guaranteed.
        """
        old = await self.config()

        new = old.copy()
        new.update(data)
        await self.middleware.call("smb.cluster_check")

        verrors = ValidationErrors()
        # Skip this check if we're joining AD
        ad_state = await self.middleware.call('activedirectory.get_state')
        if ad_state in ['HEALTHY', 'FAULTED']:
            for i in ('workgroup', 'netbiosname', 'netbiosalias'):
                if old[i] != new[i]:
                    verrors.add(f'smb_update.{i}',
                                'This parameter may not be changed after joining Active Directory (AD). '
                                'If it must be changed, the proper procedure is to leave the AD domain '
                                'and then alter the parameter before re-joining the domain.')

        await self.validate_smb(new, verrors)
        verrors.check()

        new['netbiosalias'] = ' '.join(new['netbiosalias'])

        await self.compress(new)
        await self.direct_update(new)

        new_config = await self.config()
        await self.middleware.call('smb.reg_update', new_config)
        await self.reset_smb_ha_mode()

        """
        Toggling aapl_extensions will require changes to all shares
        on server (enabling vfs_fruit and possibly changing catia params).
        """
        if old['aapl_extensions'] != new['aapl_extensions']:
            await self.apply_aapl_changes()

        if old['netbiosname_local'] != new_config['netbiosname_local']:
            new_sid = await self.middleware.call("smb.get_system_sid")
            await self.middleware.call("smb.set_database_sid", new_sid)
            new_config["cifs_SID"] = new_sid
            await self.middleware.call("smb.synchronize_group_mappings")
            srv = (await self.middleware.call("network.configuration.config"))["service_announcement"]
            await self.middleware.call("network.configuration.toggle_announcement", srv)

        if new['admin_group'] and new['admin_group'] != old['admin_group']:
            job = await self.middleware.call('smb.synchronize_group_mappings')
            await job.wait()

        await self._service_change(self._config.service, 'restart')
        return new_config

    @private
    async def compress(self, data):
        data.pop('netbiosname_local', None)
        data.pop('netbiosname_b', None)
        data.pop('next_rid')
        data['loglevel'] = LOGLEVEL_MAP.inv.get(data['loglevel'], 1)
        return data


class SharingSMBModel(sa.Model):
    __tablename__ = 'sharing_cifs_share'

    id = sa.Column(sa.Integer(), primary_key=True)
    cifs_purpose = sa.Column(sa.String(120))
    cifs_path = sa.Column(sa.String(255), nullable=True)
    cifs_path_suffix = sa.Column(sa.String(255), nullable=False)
    cifs_home = sa.Column(sa.Boolean(), default=False)
    cifs_name = sa.Column(sa.String(120))
    cifs_comment = sa.Column(sa.String(120))
    cifs_ro = sa.Column(sa.Boolean(), default=False)
    cifs_browsable = sa.Column(sa.Boolean(), default=True)
    cifs_recyclebin = sa.Column(sa.Boolean(), default=False)
    cifs_guestok = sa.Column(sa.Boolean(), default=False)
    cifs_hostsallow = sa.Column(sa.Text())
    cifs_hostsdeny = sa.Column(sa.Text())
    cifs_auxsmbconf = sa.Column(sa.Text())
    cifs_aapl_name_mangling = sa.Column(sa.Boolean())
    cifs_abe = sa.Column(sa.Boolean())
    cifs_acl = sa.Column(sa.Boolean())
    cifs_durablehandle = sa.Column(sa.Boolean())
    cifs_streams = sa.Column(sa.Boolean())
    cifs_timemachine = sa.Column(sa.Boolean(), default=False)
    cifs_timemachine_quota = sa.Column(sa.Integer(), default=0)
    cifs_vuid = sa.Column(sa.String(36))
    cifs_shadowcopy = sa.Column(sa.Boolean())
    cifs_fsrvp = sa.Column(sa.Boolean())
    cifs_enabled = sa.Column(sa.Boolean(), default=True)
    cifs_share_acl = sa.Column(sa.Text())
    cifs_cluster_volname = sa.Column(sa.String(255))
    cifs_afp = sa.Column(sa.Boolean())


class SharingSMBService(SharingService):

    share_task_type = 'SMB'
    path_field = 'path_local'
    allowed_path_types = [FSLocation.CLUSTER, FSLocation.EXTERNAL, FSLocation.LOCAL]

    class Config:
        namespace = 'sharing.smb'
        datastore = 'sharing.cifs_share'
        datastore_prefix = 'cifs_'
        datastore_extend = 'sharing.smb.extend'
        cli_namespace = 'sharing.smb'

    LP_CTX = param.LoadParm(SMBPath.STUBCONF.platform())

    @private
    async def strip_comments(self, data):
        parsed_config = ""
        for entry in data['auxsmbconf'].splitlines():
            if entry == "" or entry.startswith(('#', ';')):
                continue
            parsed_config += entry if len(parsed_config) == 0 else f'\n{entry}'

        data['auxsmbconf'] = parsed_config

    @accepts(Dict(
        'sharingsmb_create',
        Str('purpose', enum=[x.name for x in SMBSharePreset], default=SMBSharePreset.DEFAULT_SHARE.name),
        SchemaPath('path', required=True),
        Str('path_suffix', default=''),
        Bool('home', default=False),
        Str('name', max_length=80, required=True),
        Str('comment', default=''),
        Bool('ro', default=False),
        Bool('browsable', default=True),
        Bool('timemachine', default=False),
        Int('timemachine_quota', default=0),
        Bool('recyclebin', default=False),
        Bool('guestok', default=False),
        Bool('abe', default=False),
        List('hostsallow'),
        List('hostsdeny'),
        Bool('aapl_name_mangling', default=False),
        Bool('acl', default=True),
        Bool('durablehandle', default=True),
        Bool('shadowcopy', default=True),
        Bool('streams', default=True),
        Bool('fsrvp', default=False),
        Str('auxsmbconf', max_length=None, default=''),
        Bool('enabled', default=True),
        Str('cluster_volname', default=''),
        Bool('afp', default=False),
        register=True
    ))
    async def do_create(self, data):
        """
        Create a SMB Share.

        `purpose` applies common configuration presets depending on intended purpose.

        `path` path to export over the SMB protocol. If server is clustered, then this path will be
        relative to the `cluster_volname`.

        `timemachine` when set, enables Time Machine backups for this share.

        `ro` when enabled, prohibits write access to the share.

        `guestok` when enabled, allows access to this share without a password.

        `hostsallow` is a list of hostnames / IP addresses which have access to this share.

        `hostsdeny` is a list of hostnames / IP addresses which are not allowed access to this share. If a handful
        of hostnames are to be only allowed access, `hostsdeny` can be passed "ALL" which means that it will deny
        access to ALL hostnames except for the ones which have been listed in `hostsallow`.

        `acl` enables support for storing the SMB Security Descriptor as a Filesystem ACL.

        `streams` enables support for storing alternate datastreams as filesystem extended attributes.

        `fsrvp` enables support for the filesystem remote VSS protocol. This allows clients to create
        ZFS snapshots through RPC.

        `shadowcopy` enables support for the volume shadow copy service.

        `auxsmbconf` is a string of additional smb4.conf parameters not covered by the system's API.
        """
        ha_mode = SMBHAMODE[(await self.middleware.call('smb.get_smb_ha_mode'))]
        await self.middleware.call("smb.cluster_check")

        verrors = ValidationErrors()

        await self.clean(data, 'sharingsmb_create', verrors)
        await self.validate(data, 'sharingsmb_create', verrors)
        await self.apply_presets(data)
        await self.legacy_afp_check(data, 'sharingsmb_create', verrors)

        verrors.check()

        await self.compress(data)
        if ha_mode != SMBHAMODE.CLUSTERED:
            vuid = await self.generate_vuid(data['timemachine'])
            data.update({'vuid': vuid})
            data['id'] = await self.middleware.call(
                'datastore.insert', self._config.datastore, data,
                {'prefix': self._config.datastore_prefix})

        await self.strip_comments(data)
        await self.middleware.call('sharing.smb.reg_addshare', data)
        do_global_reload = await self.must_reload_globals(data)

        if do_global_reload:
            await self.middleware.call('smb.initialize_globals')
            if (await self.middleware.call('activedirectory.get_state')) == 'HEALTHY':
                await self.middleware.call('activedirectory.synchronize')
                if data['home']:
                    await self.middleware.call('idmap.clear_idmap_cache')

            await self._service_change('cifs', 'restart')
        else:
            await self._service_change('cifs', 'reload')

        if ha_mode == SMBHAMODE.CLUSTERED:
            ret = await self.query([('name', '=', data['name'])],
                                   {'get': True, 'extra': {'ha_mode': ha_mode.name}})
        else:
            ret = await self.get_instance(data['id'])

        if data['timemachine']:
            await self.middleware.call('service.restart', 'mdns')

        return ret

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
        await self.middleware.call("smb.cluster_check")
        ha_mode = SMBHAMODE[(await self.middleware.call('smb.get_smb_ha_mode'))]

        verrors = ValidationErrors()
        old = await self.query([('id', '=', id)], {'get': True, 'extra': {'ha_mode': ha_mode.name}})

        new = old.copy()
        new.update(data)

        oldname = 'homes' if old['home'] else old['name']
        newname = 'homes' if new['home'] else new['name']

        new['vuid'] = await self.generate_vuid(new['timemachine'], new['vuid'])
        await self.clean(new, 'sharingsmb_update', verrors, id=id)
        if old['purpose'] != new['purpose']:
            await self.apply_presets(new)

        await self.validate(new, 'sharingsmb_update', verrors, old=old)
        await self.legacy_afp_check(new, 'sharingsmb_update', verrors)
        check_mdns = False

        verrors.check()

        guest_changed = old['guestok'] != new['guestok']

        if ha_mode == SMBHAMODE.CLUSTERED:
            diff = await self.middleware.call(
                'sharing.smb.diff_middleware_and_registry', new['name'], new
            )
            share_name = new['name'] if not new['home'] else 'homes'
            await self.middleware.call('sharing.smb.apply_conf_diff',
                                       share_name, diff)

            do_global_reload = guest_changed or await self.must_reload_globals(new)
            if do_global_reload:
                await self.middleware.call('smb.initialize_globals')
                await self._service_change('cifs', 'restart')
            else:
                await self._service_change('cifs', 'reload')

            return await self.query([('name', '=', share_name)],
                                    {'get': True, 'extra': {'ha_mode': ha_mode.name}})

        old_is_locked = (await self.get_instance(id))['locked']
        if old['path'] != new['path']:
            new_is_locked = await self.middleware.call('pool.dataset.path_in_locked_datasets', new['path'])
        else:
            new_is_locked = old_is_locked

        await self.compress(new)
        await self.middleware.call(
            'datastore.update', self._config.datastore, id, new,
            {'prefix': self._config.datastore_prefix})

        await self.strip_comments(new)
        if not new_is_locked:
            """
            Enabling AAPL SMB2 extensions globally affects SMB shares. If this
            happens, the SMB service _must_ be restarted. Skip this step if dataset
            underlying the new path is encrypted.
            """
            do_global_reload = guest_changed or await self.must_reload_globals(new)
        else:
            do_global_reload = False

        """
        OLD    NEW   = dataset path is encrypted
         ----------
         -      -    = pre-12 behavior. Remove and replace if name changed, else update.
         -      X    = Delete share from running configuration
         X      -    = Add share to running configuration
         X      X    = no-op
        """
        if old_is_locked and new_is_locked:
            """
            Configuration change only impacts a locked SMB share. From standpoint of
            running config, this is a no-op. No need to restart or reload service.
            """
            return await self.get_instance(id)

        elif not old_is_locked and not new_is_locked:
            """
            Default behavior before changes for locked datasets.
            """
            if newname != oldname:
                # This is disruptive change. Share is actually being removed and replaced.
                # Forcibly closes any existing SMB sessions.
                await self.close_share(oldname)
                try:
                    await self.middleware.call('smb.sharesec.dup_share_acl', oldname, newname)
                except MatchNotFound:
                    pass

                try:
                    await self.middleware.call('sharing.smb.reg_delshare', oldname)
                except MatchNotFound:
                    pass
                except Exception:
                    self.logger.warning('Failed to remove stale share [%s]',
                                        old['name'], exc_info=True)
                await self.middleware.call('sharing.smb.reg_addshare', new)
            else:
                diff = await self.middleware.call(
                    'sharing.smb.diff_middleware_and_registry', new['name'], new
                )
                if diff is None:
                    await self.middleware.call('sharing.smb.reg_addshare', new)
                else:
                    share_name = new['name'] if not new['home'] else 'homes'
                    await self.middleware.call('sharing.smb.apply_conf_diff',
                                               share_name, diff)

        elif old_is_locked and not new_is_locked:
            """
            Since the old share was not in our running configuration, we need
            to add it.
            """
            check_mdns = True
            await self.middleware.call('smb.sharesec.toggle_share', newname, True)
            await self.middleware.call('sharing.smb.reg_addshare', new)

        elif not old_is_locked and new_is_locked:
            await self.close_share(newname)
            await self.middleware.call('smb.sharesec.toggle_share', newname, False)
            try:
                await self.middleware.call('sharing.smb.reg_delshare', oldname)
                check_mdns = True
            except Exception:
                self.logger.warning('Failed to remove locked share [%s]',
                                    old['name'], exc_info=True)

        if new['enabled'] != old['enabled']:
            if not new['enabled']:
                await self.close_share(newname)

            await self.middleware.call('smb.sharesec.toggle_share', newname, new['enabled'])
            check_mdns = True

        if do_global_reload:
            await self.middleware.call('smb.initialize_globals')
            if (await self.middleware.call('activedirectory.get_state')) == 'HEALTHY':
                await self.middleware.call('activedirectory.synchronize')
                if new['home'] or old['home']:
                    await self.middleware.call('idmap.clear_idmap_cache')

            await self._service_change('cifs', 'restart')
        else:
            await self._service_change('cifs', 'reload')

        if check_mdns or old['timemachine'] != new['timemachine']:
            await self.middleware.call('service.restart', 'mdns')

        return await self.get_instance(id)

    @accepts(Int('id'))
    async def do_delete(self, id):
        """
        Delete SMB Share of `id`. This will forcibly disconnect SMB clients
        that are accessing the share.
        """
        await self.middleware.call("smb.cluster_check")
        ha_mode = SMBHAMODE[(await self.middleware.call('smb.get_smb_ha_mode'))]
        if ha_mode != SMBHAMODE.CLUSTERED:
            share = await self.get_instance(id)
            result = await self.middleware.call('datastore.delete', self._config.datastore, id)
        else:
            share = await self.query([('id', '=', id)], {'get': True})
            result = id

        share_name = 'homes' if share['home'] else share['name']
        share_list = await self.middleware.call('sharing.smb.reg_listshares')
        if share_name in share_list:
            await self.close_share(share_name)
            try:
                await self.middleware.call('smb.sharesec._delete', share_name)
            except Exception:
                self.logger.debug('Failed to delete share ACL for [%s].', share_name, exc_info=True)

            try:
                await self.middleware.call('sharing.smb.reg_delshare', share_name)

            except MatchNotFound:
                pass
            except Exception:
                self.logger.warn('Failed to remove registry entry for [%s].', share_name, exc_info=True)

        if share['timemachine']:
            await self.middleware.call('service.restart', 'mdns')

        return result

    @filterable
    async def query(self, filters, options):
        """
        Query shares with filters. In clustered environments, local datastore query
        is bypassed in favor of clustered registry.
        """
        extra = options.get('extra', {})
        ha_mode_str = extra.get('ha_mode')
        if ha_mode_str is None:
            ha_mode = SMBHAMODE[(await self.middleware.call('smb.get_smb_ha_mode'))]
        else:
            ha_mode = SMBHAMODE[ha_mode_str]

        if ha_mode == SMBHAMODE.CLUSTERED:
            result = await self.middleware.call(
                'sharing.smb.reg_query', filters, options
            )
        else:
            return await super().query(filters, options)
        return result

    @private
    async def legacy_afp_check(self, data, schema, verrors):
        to_check = Path(data['path']).resolve(strict=False)
        legacy_afp = await self.query([
            ("afp", "=", True),
            ("enabled", "=", True),
            ("id", "!=", data.get("id"))
        ])
        for share in legacy_afp:
            if share['afp'] == data['afp']:
                continue
            s = Path(share['path']).resolve(strict=(not share['locked']))
            if s.is_relative_to(to_check) or to_check.is_relative_to(s):
                verrors.add(
                    f"{schema}.afp",
                    "Compatibility settings for legacy AFP shares (paths that once hosted "
                    "AFP shares that have been converted to SMB shares) must be "
                    "consistent with the legacy AFP compatibility settings of any existing SMB "
                    f"share that exports the same paths. The new share [{data['name']}] conflicts "
                    f"with share [{share['name']}] on path [{share['path']}]."
                )

    @private
    async def must_reload_globals(self, data):
        """
        Check whether the combination of payload and current SMB settings requires
        that we reconfigure the SMB server globally. There are currently two situations
        where this will happen:

        1) guest access is enabled on a share for the first time. In this case, the SMB
           server must be reconfigured to allow mapping of bad users to the guest account.

        2) vfs_fruit (currently in the form of time machine) is enabled on an SMB share.
           Support for SMB2/3 apple extensions is negotiated on client's first SMB tree
           connection. This means that settings are de-facto global in scope and we must
           reload.
        """
        aapl_extensions = (await self.middleware.call('smb.config'))['aapl_extensions']

        if not aapl_extensions and data['timemachine']:
            await self.middleware.call('smb.direct_update', {'aapl_extensions': True})
            return True

        if data['guestok']:
            """
            Verify that running configuration has required setting for guest access.
            """
            guest_mapping = await self.middleware.call('smb.getparm', 'map to guest', 'GLOBAL')
            if guest_mapping != 'Bad User':
                return True

        if data['home']:
            return True

        return False

    @private
    async def close_share(self, share_name):
        c = await run([SMBCmd.SMBCONTROL.value, 'smbd', 'close-share', share_name], check=False)
        if c.returncode != 0:
            if "Can't find pid" in c.stderr.decode():
                # smbd is not running. Don't log error message.
                return

            self.logger.warn('Failed to close smb share [%s]: [%s]',
                             share_name, c.stderr.decode().strip())

    @private
    async def clean(self, data, schema_name, verrors, id=None):
        data['name'] = await self.name_exists(data, schema_name, verrors, id)
        await self.add_path_local(data)

    @private
    async def validate_aux_params(self, data, schema_name):
        """
        libsmbconf expects to be provided with key-value pairs.
        """
        verrors = ValidationErrors()
        aux_blacklist = [
            'state directory',
            'private directory',
            'lock directory',
            'lock dir',
            'config backend',
            'private dir',
            'log level',
            'cache directory',
            'clustering',
            'ctdb socket',
            'socket options',
            'include',
            'interfaces',
            'wide links',
            'insecure wide links'
        ]
        freebsd_vfs_objects = [
            'noacl',
        ]
        for entry in data.splitlines():
            if entry == '' or entry.startswith(('#', ';')):
                continue

            kv = entry.split('=', 1)
            if len(kv) != 2:
                verrors.add(
                    f'{schema_name}.auxsmbconf',
                    f'Auxiliary parameters must be in the format of "key = value": {entry}'
                )
                continue

            if kv[0].strip() in aux_blacklist:
                """
                This one checks our ever-expanding enumeration of badness.
                Parameters are blacklisted if incorrect values can prevent smbd from starting.
                """
                verrors.add(
                    f'{schema_name}.auxsmbconf',
                    f'{kv[0]} is a blacklisted auxiliary parameter. Changes to this parameter '
                    'are not permitted.'
                )

            if kv[0].strip() == 'vfs objects':
                for i in kv[1].split():
                    if i in freebsd_vfs_objects:
                        verrors.add(
                            f'{schema_name}.auxsmbconf',
                            f'[{i}] is not a permitted VFS object on SCALE.'
                        )

            if schema_name == 'smb_update.smb_options' and ':' not in kv[0]:
                """
                lib/param doesn't validate params containing a colon.
                this dump_a_parameter() wraps around the respective lp_ctx
                function in samba that checks the known parameter table.
                This should be a lightweight validation of GLOBAL params.
                """
                try:
                    self.LP_CTX.dump_a_parameter(kv[0].strip())
                except RuntimeError as e:
                    verrors.add(
                        f'{schema_name}.auxsmbconf',
                        str(e)
                    )

        verrors.check()

    @private
    async def cluster_share_validate(self, data, schema_name, verrors):
        ha_mode = SMBHAMODE[(await self.middleware.call('smb.get_smb_ha_mode'))]
        if ha_mode != SMBHAMODE.CLUSTERED:
            return

        if data['shadowcopy']:
            verrors.add(
                f'{schema_name}.shadowcopy',
                'Shadow Copies are not implemented for clustered shares.'
            )
        if data['home']:
            verrors.add(
                f'{schema_name}.home',
                'Home shares are not implemented for clustered shares.'
            )
        if data['fsrvp']:
            verrors.add(
                f'{schema_name}.fsrvp',
                'FSRVP support is not implemented for clustered shares.'
            )
        if not data['cluster_volname']:
            verrors.add(
                f'{schema_name}.cluster_volname',
                'Cluster volume name is required for clustered shares.'
            )
            return

        cluster_volumes = await self.middleware.call('gluster.volume.list')

        try:
            cluster_volumes.remove('ctdb_shared_vol')
        except ValueError:
            pass

        if data['cluster_volname'] not in cluster_volumes:
            verrors.add(
                f'{schema_name}.cluster_volname',
                f'{data["cluster_volname"]}: cluster volume does not exist. '
                f'Choices are: {cluster_volumes}.'
            )

    @private
    def validate_mount_info(self, verrors, schema, path):
        def get_acl_type(sb_info):
            if 'NFS4ACL' in sb_info:
                return 'NFSV4'

            if 'POSIXACL' in sb_info:
                return 'POSIX'

            return 'OFF'

        st = os.lstat(path)
        if stat.S_ISLNK(st.st_mode):
            verrors.add(schema, f'{path}: is symbolic link.')
            return

        mntinfo = getmntinfo()
        this_mnt = mntinfo[st.st_dev]
        if this_mnt['fs_type'] != 'zfs':
            verrors.add(schema, f'{this_mnt["fstype"]}: path is not a ZFS dataset')

        if not is_child_realpath(path, this_mnt['mountpoint']):
            verrors.add(
                schema,
                f'Mountpoint {this_mnt["mountpoint"]} not within path {path}. '
                'This may indicate that the path of the SMB share contains a '
                'symlink component.'
            )

        if 'XATTR' not in this_mnt['super_opts']:
            verrors.add(schema, 'Extended attribute support is required for SMB shares')

        k8s_dataset = self.middleware.call_sync('kubernetes.config')['dataset']
        if k8s_dataset and Path(this_mnt['mount_source']) in Path(k8s_dataset).parents:
            verrors.add(schema, 'SMB shares containing the apps dataset are not permitted')
            return

        current_acltype = get_acl_type(this_mnt['super_opts'])
        child_mounts = filter_list(list(mntinfo.values()), [['mountpoint', '^', f'{path}/']])
        for mnt in child_mounts:
            if '@' in mnt['mount_source']:
                continue

            child_acltype = get_acl_type(mnt['super_opts'])
            if child_acltype != current_acltype:
                verrors.add(
                    schema,
                    f'ACL type mismatch with child mountpoint at {mnt["mountpoint"]}: '
                    f'{this_mnt["mount_source"]} - {current_acltype}, {mnt["mount_source"]} - {child_acltype}'
                )

            if mnt['fs_type'] != 'zfs':
                verrors.add(
                    schema, f'{mnt["mountpoint"]}: child mount is not a ZFS dataset.'
                )

            if 'XATTR' not in mnt['super_opts']:
                verrors.add(
                    schema, f'{mnt["mountpoint"]}: extended attribute support is disabled on child mount.'
                )

    @private
    async def get_path_field(self, data):
        if self.path_field in data:
            return data[self.path_field]

        resolved = await self.add_path_local({'path': data['path'], 'cluster_volname': data['cluster_volname']})
        return resolved[self.path_field]

    @private
    async def validate_external_path(self, verrors, name, path):
        proxy_list = path.split(',')
        for proxy in proxy_list:
            if len(proxy.split('\\')) != 2:
                verrors.add(name, f'{proxy}: DFS proxy must be of format SERVER\\SHARE')

            if proxy.startswith('\\') or proxy.endswith('\\'):
                verrors.add(name, f'{proxy}: DFS proxy must be of format SERVER\\SHARE')

        if len(proxy_list) == 0:
            verrors.add(name, 'At least one DFS proxy must be specified')

    @private
    async def validate_local_path(self, verrors, name, path):
        await super().validate_local_path(verrors, name, path)
        """
        This is a very rough check is to prevent users from sharing unsupported
        filesystems over SMB as behavior with our default VFS options in such
        a situation is undefined.
        """
        try:
            await self.middleware.run_in_thread(
                self.validate_mount_info, verrors, name, path
            )
        except FileNotFoundError:
            verrors.add(name, 'Path does not exist.')

    @private
    async def validate_cluster_path(self, verrors, name, volname, path):
        await super().validate_cluster_path(verrors, name, volname, path)

        if path == '/':
            verrors.add(name, 'Sharing root of gluster volume is not permitted.')

    @private
    async def validate(self, data, schema_name, verrors, old=None):
        """
        Path is a required key in almost all cases. There is a special edge case for LDAP
        [homes] shares. In this case we allow an empty path. Samba interprets this to mean
        that the path should be dynamically set to the user's home directory on the LDAP server.
        Local user auth to SMB shares is prohibited when LDAP is enabled with a samba schema.
        """
        smb_config = None

        home_result = await self.home_exists(
            data['home'], schema_name, verrors, old)

        if home_result:
            verrors.add(f'{schema_name}.home',
                        'Only one share is allowed to be a home share.')

        if await self.query([['name', 'C=', data['name']], ['id', '!=', data.get('id', 0)]]):
            verrors.add(f'{schema_name}.name', 'Share names are case-insensitive and must be unique')

        await self.cluster_share_validate(data, schema_name, verrors)

        await self.validate_path_field(data, schema_name, verrors)

        if data['auxsmbconf']:
            try:
                await self.validate_aux_params(data['auxsmbconf'],
                                               f'{schema_name}.auxsmbconf')
            except ValidationErrors as errs:
                verrors.add_child(f'{schema_name}.auxsmbconf', errs)

        if not data['acl'] and not await self.middleware.call('filesystem.acl_is_trivial', data['path']):
            verrors.add(
                f'{schema_name}.acl',
                f'ACL detected on {data["path"]}. ACLs must be stripped prior to creation '
                'of SMB share.'
            )

        if data.get('name') and data['name'].lower() in ['global', 'homes', 'printers']:
            verrors.add(
                f'{schema_name}.name',
                f'{data["name"]} is a reserved section name, please select another one'
            )

        if data.get('path_suffix') and len(data['path_suffix'].split('/')) > 2:
            verrors.add(f'{schema_name}.name',
                        'Path suffix may not contain more than two components.')

        if data['timemachine'] and data['enabled']:
            ngc = await self.middleware.call('network.configuration.config')
            if not ngc['service_announcement']['mdns']:
                verrors.add(
                    f'{schema_name}.timemachine',
                    'mDNS must be enabled in order to use an SMB share as a time machine target.'
                )

        for entry in ['afp', 'timemachine']:
            if not data[entry]:
                continue
            if not smb_config:
                smb_config = await self.middleware.call('smb.config')

            if smb_config['aapl_extensions']:
                continue

            verrors.add(
                f'{schema_name}.{entry}',
                'Apple SMB2/3 protocol extension support is required by this parameter. '
                'This feature may be enabled in the general SMB server configuration.'
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
    async def auxsmbconf_dict(self, aux, direction="TO"):
        ret = None
        if direction == 'TO':
            ret = {}
            for entry in aux.splitlines():
                if entry == '':
                    continue

                if entry.startswith(('#', ';')):
                    # Special handling for comments
                    ret[entry] = None
                    continue

                kv = entry.split('=', 1)
                ret[kv[0].strip()] = kv[1].strip()

            return ret

        if direction == 'FROM':
            return '\n'.join([f'{k}={v}' if v is not None else k for k, v in aux.items()])

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
    async def add_path_local(self, data):
        if data['cluster_volname']:
            data['path_local'] = f'CLUSTER:{data["cluster_volname"]}/{data["path"]}'
        else:
            data['path_local'] = data['path']

        return data

    @private
    async def extend(self, data):
        data['hostsallow'] = data['hostsallow'].split()
        data['hostsdeny'] = data['hostsdeny'].split()
        if data['fsrvp']:
            data['shadowcopy'] = True

        if 'share_acl' in data:
            data.pop('share_acl')

        return await self.add_path_local(data)

    @private
    async def compress(self, data):
        data['hostsallow'] = ' '.join(data['hostsallow'])
        data['hostsdeny'] = ' '.join(data['hostsdeny'])
        data.pop(self.locked_field, None)
        data.pop('path_local', None)

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
    async def apply_presets(self, data):
        """
        Apply settings from presets. Only include auxiliary parameters
        from preset if user-defined aux parameters already exist. In this
        case user-defined takes precedence.
        """
        params = (SMBSharePreset[data["purpose"]].value)["params"].copy()
        if data.get('home'):
            params.pop('path_suffix', None)

        aux = params.pop("auxsmbconf")
        data.update(params)
        if data["auxsmbconf"]:
            preset_aux = await self.auxsmbconf_dict(aux, direction="TO")
            data_aux = await self.auxsmbconf_dict(data["auxsmbconf"], direction="TO")
            preset_aux.update(data_aux)
            data["auxsmbconf"] = await self.auxsmbconf_dict(preset_aux, direction="FROM")

        return data

    @accepts()
    async def presets(self):
        """
        Retrieve pre-defined configuration sets for specific use-cases. These parameter
        combinations are often non-obvious, but beneficial in these scenarios.
        """
        return {x.name: x.value for x in SMBSharePreset}

    @private
    @job(lock='sync_smb_registry')
    async def sync_registry(self, job):
        """
        Synchronize registry config with the share configuration in the truenas config
        file. This method simply reconciles lists of shares, removing from and adding to
        the registry as-needed.
        """
        if not await self.middleware.run_in_thread(os.path.exists, SMBPath.GLOBALCONF.platform()):
            self.logger.warning("smb.conf does not exist. Skipping registry synchronization."
                                "This may indicate that SMB service has not completed initialization.")
            return

        db_shares = await self.query()

        for share in db_shares:
            if share['home']:
                share['name'] = 'HOMES'

        active_shares = filter_list(db_shares, [
            ('locked', '=', False),
            ('enabled', '=', True),
            ('path', '!=', '')
        ])

        registry_shares = await self.middleware.call('sharing.smb.reg_listshares')

        cf_db = set([x['name'].casefold() for x in db_shares])
        cf_active = set([x['name'].casefold() for x in active_shares])
        cf_reg = set([x.casefold() for x in registry_shares])
        to_add = cf_active - cf_reg
        to_del = cf_reg - cf_active
        to_preserve_acl = cf_db & to_del

        for share in to_add:
            share_conf = filter_list(active_shares, [['name', 'C=', share]])
            if path_location(share_conf[0][self.path_field]) is FSLocation.LOCAL:
                if not await self.middleware.run_in_thread(os.path.exists, share_conf[0]['path']):
                    self.logger.warning("Path [%s] for share [%s] does not exist. "
                                        "Refusing to add share to SMB configuration.",
                                        share_conf[0]['path'], share_conf[0]['name'])
                    continue

            try:
                await self.middleware.call('sharing.smb.reg_addshare', share_conf[0])
                await self.middleware.call('smb.sharesec.toggle_share', share, True)
            except ValueError:
                self.logger.warning("Share [%s] has invalid configuration.", share, exc_info=True)
            except Exception:
                self.logger.warning("Failed to add SMB share [%s] while synchronizing registry config",
                                    share, exc_info=True)

        for share in to_del:
            await self.middleware.call('sharing.smb.close_share', share)
            try:
                if share in to_preserve_acl:
                    await self.middleware.call('smb.sharesec.toggle_share', share, False)

                await self.middleware.call('sharing.smb.reg_delshare', share)
            except Exception:
                self.middleware.logger.warning('Failed to remove stale share [%s]',
                                               share, exc_info=True)


async def pool_post_import(middleware, pool):
    """
    Makes sure to reload SMB if a pool is imported and there are shares configured for it.
    """
    if pool is None:
        """
        By the time the post-import hook is called, the smb.configure should have
        already completed and initialized the SMB service.
        """
        await middleware.call('smb.disable_acl_if_trivial')
        middleware.create_task(middleware.call('sharing.smb.sync_registry'))
        return

    smb_is_configured = await middleware.call("smb.is_configured")
    if not smb_is_configured:
        middleware.logger.warning(
            "Skipping SMB share config sync because SMB service "
            "has not been fully initialized."
        )
        return

    path = f'/mnt/{pool["name"]}'
    if await middleware.call('sharing.smb.query', [
        ('OR', [
            ('path', '=', path),
            ('path', '^', f'{path}/'),
        ])
    ]):
        await middleware.call('smb.disable_acl_if_trivial')
        middleware.create_task(middleware.call('sharing.smb.sync_registry'))


class SMBFSAttachmentDelegate(LockableFSAttachmentDelegate):
    name = 'smb'
    title = 'SMB Share'
    service = 'cifs'
    service_class = SharingSMBService

    async def restart_reload_services(self, attachments):
        """
        libsmbconf will handle any required notifications to clients if
        shares are added or deleted.
        mDNS may need to be reloaded if a time machine share is located on
        the share being attached.
        """
        await self.middleware.call('smb.disable_acl_if_trivial')
        smb_is_configured = await self.middleware.call("smb.is_configured")
        if not smb_is_configured:
            self.logger.warning(
                "Skipping SMB share config sync because SMB service "
                "has not been fully initialized."
            )
            return

        reg_sync = await self.middleware.call('sharing.smb.sync_registry')
        await reg_sync.wait()
        await self.middleware.call('service.reload', 'mdns')

    async def is_child_of_path(self, resource, path, check_parent):
        return await super().is_child_of_path(resource, path, check_parent) if resource.get(
            self.path_field
        ) else False


async def setup(middleware):
    await middleware.call(
        'interface.register_listen_delegate',
        SystemServiceListenMultipleDelegate(middleware, 'smb', 'bindip'),
    )
    await middleware.call('pool.dataset.register_attachment_delegate', SMBFSAttachmentDelegate(middleware))
    middleware.register_hook('pool.post_import', pool_post_import, sync=True)
