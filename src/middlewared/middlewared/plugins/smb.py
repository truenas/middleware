import asyncio
import codecs
import errno
import middlewared.sqlalchemy as sa
import os
import re
from pathlib import Path
import uuid
import unicodedata

from copy import deepcopy

from middlewared.common.attachment import LockableFSAttachmentDelegate
from middlewared.common.listen import SystemServiceListenMultipleDelegate
from middlewared.schema import Bool, Dict, IPAddr, List, NetbiosName, NetbiosDomain, Ref, returns, SID, Str, Int, Patch
from middlewared.schema import Path as SchemaPath
# List schema defaults to [], supplying NOT_PROVIDED avoids having audit update that
# defaults for ignore_list or watch_list from overrwriting previous value
from middlewared.schema.utils import NOT_PROVIDED
from middlewared.service import accepts, job, pass_app, private, SharingService
from middlewared.service import ConfigService, ValidationError, ValidationErrors
from middlewared.service_exception import CallError, MatchNotFound
from middlewared.plugins.directoryservices_.all import get_enabled_ds
from middlewared.plugins.smb_.constants import (
    NETIF_COMPLETE_SENTINEL,
    CONFIGURED_SENTINEL,
    SMB_AUDIT_DEFAULTS,
    INVALID_SHARE_NAME_CHARACTERS,
    LOGLEVEL_MAP,
    RESERVED_SHARE_NAMES,
    SMBHAMODE,
    SMBCmd,
    SMBPath,
    SMBSharePreset
)
from middlewared.plugins.smb_.constants import SMBBuiltin  # noqa (imported so may be imported from here)
from middlewared.plugins.smb_.util_param import smbconf_getparm, lpctx_validate_global_parm
from middlewared.plugins.smb_.util_net_conf import reg_delshare, reg_listshares, reg_setparm
from middlewared.plugins.smb_.util_smbconf import generate_smb_conf_dict
from middlewared.plugins.smb_.utils import apply_presets, is_time_machine_share, smb_strip_comments
from middlewared.plugins.tdb.utils import TDBError
from middlewared.plugins.idmap_.idmap_constants import IDType, SID_LOCAL_USER_PREFIX, SID_LOCAL_GROUP_PREFIX
from middlewared.utils.directoryservices.constants import DSStatus, DSType
from middlewared.utils import filter_list, run
from middlewared.utils.mount import getmnttree
from middlewared.utils.path import FSLocation, path_location, is_child_realpath
from middlewared.utils.privilege import credential_has_full_admin


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


class SMBService(ConfigService):

    class Config:
        service = 'cifs'
        service_verb = 'restart'
        datastore = 'services.cifs'
        datastore_extend = 'smb.smb_extend'
        datastore_prefix = 'cifs_srv_'
        cli_namespace = 'service.smb'
        role_prefix = 'SHARING_SMB'

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

    @accepts()
    async def unixcharset_choices(self):
        return await self.generate_choices(
            ['UTF-8', 'ISO-8859-1', 'ISO-8859-15', 'GB2312', 'EUC-JP', 'ASCII']
        )

    @private
    def generate_smb_configuration(self):
        if self.middleware.call_sync('failover.status') not in ('SINGLE', 'MASTER'):
            return {'netbiosname': 'TN_STANDBY'}

        enabled_ds = get_enabled_ds()
        if enabled_ds is None:
            enabled_ds_name = None
            ds_config = {}
        else:
            match enabled_ds.name:
                case DSType.AD.value:
                    ds_config = enabled_ds.config
                case DSType.LDAP.value:
                    ds_config = enabled_ds.config
                case DSType.IPA.value:
                    ds_config = enabled_ds.config | {'domain_info': enabled_ds.get_smb_domain_info()}
                case _:
                    raise ValueError(f'{enabled_ds.name}: Unexpected directory service')

            enabled_ds_name = enabled_ds.name

        idmap_config = self.middleware.call_sync('idmap.query')
        smb_config = self.middleware.call_sync('smb.config')
        smb_shares = self.middleware.call_sync('sharing.smb.query')
        bind_ip_choices = self.middleware.call_sync('smb.bindip_choices')

        return generate_smb_conf_dict(
            enabled_ds_name, ds_config, smb_config, smb_shares, bind_ip_choices, idmap_config
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

        if ha_mode == 'UNIFIED':
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

        proc = await run(['/usr/bin/iconv', '-l'], check=False)
        output = proc.stdout.decode()

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
    def getparm(self, parm, section):
        """
        Get a parameter from the smb4.conf file. This is more reliable than
        'testparm --parameter-name'. testparm will fail in a variety of
        conditions without returning the parameter's value.
        """
        return smbconf_getparm(parm, section)

    @private
    async def get_next_rid(self, objtype, id_):
        base_rid = 20000 if objtype == 'USER' else 200000
        return base_rid + id_

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
            if p == SMBPath.STUBCONF:
                continue

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
    async def netif_wait(self, timeout=120):
        """
        Wait for for the ix-netif sentinel file
        and confirm connectivity with some targeted tests.
        All must be completed before the timeout.
        """
        found_sentinel = False
        while timeout >= 0 and not found_sentinel:
            if await self.middleware.run_in_thread(os.path.exists, NETIF_COMPLETE_SENTINEL):
                found_sentinel = True

            timeout -= 1
            if timeout <= 0:
                self.logger.warning('Failed to get netif completion sentinal.')
            elif not found_sentinel:
                await asyncio.sleep(1)

        """
        Confirm at least one network interface is UP
        """
        while timeout >= 0:
            if any((
                i['state']['link_state'] == 'LINK_STATE_UP' for i in await self.middleware.call('interface.query')
            )):
                break
            else:
                timeout -= 1
                if timeout <= 0:
                    self.logger.warning('Failed to detect any connected network interfaces.')
                else:
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
        job.set_progress(25, 'generating SMB, idmap, and directory service config.')
        await self.middleware.call('etc.generate', 'smb')

        """
        We cannot continue without network.
        Wait here until we see the ix-netif completion sentinel.
        """
        job.set_progress(20, 'Wait for ix-netif completion.')
        await self.netif_wait()

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

        """
        passdb_backend = await self.middleware.call('smb.getparm', 'passdb backend', 'global')
        if passdb_backend.startswith("tdbsam"):
            job.set_progress(40, 'Synchronizing passdb and groupmap.')
            await self.middleware.call('etc.generate', 'user')
            pdb_job = await self.middleware.call("smb.synchronize_passdb", True)
            grp_job = await self.middleware.call("smb.synchronize_group_mappings", True)
            await pdb_job.wait()
            await grp_job.wait()

        """
        The following steps ensure that we cleanly import our SMB shares
        into the registry.
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
        ad_enabled = (await self.middleware.call('activedirectory.config'))['enable']
        if ad_enabled:
            ldap_enabled = False
        else:
            ldap_enabled = (await self.middleware.call('ldap.config'))['enable']

        ds_job = await self.middleware.call(
            "directoryservices.initialize",
            {"activedirectory": ad_enabled, "ldap": ldap_enabled}
        )
        await ds_job.wait()

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

        if not await self.middleware.call('systemdataset.sysdataset_path'):
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

        if await self.middleware.call('failover.licensed'):
            hamode = SMBHAMODE['UNIFIED'].name
        else:
            hamode = SMBHAMODE['STANDALONE'].name

        await self.middleware.call('cache.put', 'SMB_HA_MODE', hamode)
        return hamode

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
                    if item.casefold() == new['workgroup'].casefold():
                        verrors.add(
                            f'smb_update.{i}.{idx}',
                            f'NetBIOS alias [{item}] conflicts with workgroup name.'
                        )
            else:
                if i != 'workgroup' and new[i].casefold() == new['workgroup'].casefold():
                    verrors.add(
                        f'smb_update.{i}',
                        f'NetBIOS name [{new[i]}] conflicts with workgroup name.'
                    )

        if new['guest'] is not None:
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
            if await self.middleware.call(
                'sharing.smb.query', filters, {'count': True, 'select': ['afp', 'timemachine']}
            ):
                verrors.add(
                    'smb_update.aapl_extensions',
                    'This option must be enabled when AFP or time machine shares are present'
                )

        if new['enable_smb1']:
            if audited_shares := await self.middleware.call(
                'sharing.smb.query', [['audit.enable', '=', True]], {'select': ['audit', 'name']}
            ):
                verrors.add(
                    'smb_update.enable_smb1',
                    f'The following SMB shares have auditing enabled: {", ".join([x["name"] for x in audited_shares])}'
                )

    @accepts(Dict(
        'smb_update',
        NetbiosName('netbiosname', max_length=15),
        NetbiosName('netbiosname_b', max_length=15),
        List('netbiosalias', items=[NetbiosName('netbios_alias')]),
        NetbiosDomain('workgroup'),
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
    @pass_app(rest=True)
    async def do_update(self, app, data):
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
        of S-1-5-32-544 (builtin\\admins). This will afford the group all privileges granted to a local admin.
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

        verrors = ValidationErrors()
        # Skip this check if we're joining AD
        ds = await self.middleware.call('directoryservices.status')
        if ds['type'] == DSType.AD.value.upper() and ds['status'] in ('HEALTHY', 'FAULTED'):
            for i in ('workgroup', 'netbiosname', 'netbiosalias'):
                if old[i] != new[i]:
                    verrors.add(f'smb_update.{i}',
                                'This parameter may not be changed after joining Active Directory (AD). '
                                'If it must be changed, the proper procedure is to leave the AD domain '
                                'and then alter the parameter before re-joining the domain.')

        if app and not credential_has_full_admin(app.authenticated_credentials):
            if old['smb_options'] != new['smb_options']:
                verrors.add(
                    'smb_update.smb_options',
                    'Changes to auxiliary parameters for the SMB service are restricted '
                    'to users with full administrative privileges.'
                )

        await self.validate_smb(new, verrors)
        verrors.check()

        await self.compress(new)
        await self.middleware.call(
            'datastore.update', self._config.datastore,
            new['id'], new, {'prefix': 'cifs_srv_'}
        )

        await self.middleware.call('etc.generate', 'smb')
        new_config = await self.config()
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
            await self.middleware.call('idmap.gencache.flush')
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
        data['netbiosalias'] = ' '.join(data['netbiosalias'])
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
    cifs_afp = sa.Column(sa.Boolean())
    cifs_audit = sa.Column(sa.JSON(dict), default=SMB_AUDIT_DEFAULTS)


class SharingSMBService(SharingService):

    share_task_type = 'SMB'
    path_field = 'path_local'
    allowed_path_types = [FSLocation.EXTERNAL, FSLocation.LOCAL]

    class Config:
        namespace = 'sharing.smb'
        datastore = 'sharing.cifs_share'
        datastore_prefix = 'cifs_'
        datastore_extend = 'sharing.smb.extend'
        cli_namespace = 'sharing.smb'
        role_prefix = 'SHARING_SMB'

    @accepts(
        Dict(
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
            Bool('afp', default=False),
            Dict(
                'audit',
                Bool('enable'),
                List('watch_list', default=NOT_PROVIDED),
                List('ignore_list', default=NOT_PROVIDED)
            ),
            register=True
        )
    )
    @pass_app(rest=True)
    async def do_create(self, app, data):
        """
        Create a SMB Share.

        `purpose` applies common configuration presets depending on intended purpose.

        `path` path to export over the SMB protocol.

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

        `audit` object contains configuration parameters related to SMB share auditing. It contains the
        following keys: `enable`, `watch_list` and `ignore_list`. Enable is boolean and controls whether
        audit messages will be generated for the share. `watch_list` is a list of groups for which to
        generate audit messages (defaults to all groups). `ignore_list` is a list of groups to ignore
        when auditing. If conflict arises between watch_list and ignore_list (based on user group
        membershipt), then watch_list will take precedence and ops will be audited.
        NOTE: auditing may not be enabled if SMB1 support is enabled for the server.

        `auxsmbconf` is a string of additional smb4.conf parameters not covered by the system's API.
        """
        audit_info = deepcopy(SMB_AUDIT_DEFAULTS) | data.get('audit')
        data['audit'] = audit_info

        verrors = ValidationErrors()

        if app and not credential_has_full_admin(app.authenticated_credentials):
            if data['auxsmbconf']:
                verrors.add(
                    'smb_update.auxsmbconf',
                    'Changes to auxiliary parameters for SMB shares are restricted '
                    'to users with full administrative privileges.'
                )

        await self.add_path_local(data)
        await self.validate(data, 'sharingsmb_create', verrors)
        await self.legacy_afp_check(data, 'sharingsmb_create', verrors)

        verrors.check()

        data['vuid'] = str(uuid.uuid4())
        compressed = await self.compress(data)

        data['id'] = await self.middleware.call(
            'datastore.insert', self._config.datastore, compressed,
            {'prefix': self._config.datastore_prefix})

        data['auxsmbconf'] = smb_strip_comments(data['auxsmbconf'])
        try:
            await self.middleware.call('sharing.smb.reg_addshare', data)
        except CallError as e:
            if e.errno != errno.EINVAL:
                raise e from None

            # Share contained garbage auxiliary parameters treat as ValidationError
            await self.middleware.call('datastore.delete', self._config.datastore, data['id'])
            raise ValidationError('sharingsmb_create.auxsmbconf', e.errmsg)

        do_global_reload = await self.must_reload_globals(data)

        if do_global_reload:
            ds = await self.middleware.call('directoryservices.status')
            if ds['type'] == DSType.AD.value.upper() and ds['status'] == 'HEALTHY':
                if data['home']:
                    await self.middleware.call('etc.generate', 'smb')
                    await self.middleware.call('idmap.clear_idmap_cache')

            await self._service_change('cifs', 'restart')
        else:
            await self._service_change('cifs', 'reload')

        if is_time_machine_share(data):
            await self.middleware.call('service.reload', 'mdns', {'ha_propagate': False})

        return await self.get_instance(data['id'])

    @private
    async def apply_share_changes(self, old_is_locked, new_is_locked, oldname, newname, old, new):
        if not old_is_locked and not new_is_locked:
            if oldname != newname:
                # This is disruptive change. Share is actually being removed and replaced.
                # Forcibly closes any existing SMB sessions.
                await self.toggle_share(oldname, False)
                try:
                    await self.middleware.call('smb.sharesec.dup_share_acl', oldname, newname)
                except MatchNotFound:
                    pass

                try:
                    await self.middleware.run_in_thread(reg_delshare, oldname)
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
                    # This is special return when share doesn't exist
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
            await self.toggle_share(newname, True)

        elif not old_is_locked and new_is_locked:
            await self.toggle_share(newname, False)

        if new['enabled'] != old['enabled']:
            if not new['enabled']:
                await self.toggle_share(newname, False)

    @accepts(
        Int('id'),
        Patch(
            'sharingsmb_create',
            'sharingsmb_update',
            ('attr', {'update': True})
        )
    )
    @pass_app(rest=True)
    async def do_update(self, app, id_, data):
        """
        Update SMB Share of `id`.
        """
        ha_mode = SMBHAMODE[(await self.middleware.call('smb.get_smb_ha_mode'))]

        verrors = ValidationErrors()
        old = await self.query([('id', '=', id_)], {'get': True, 'extra': {'ha_mode': ha_mode.name}})
        old_audit = old['audit']

        new = old.copy()
        new.update(data)
        new['audit'] = old_audit | data.get('audit', {})

        oldname = 'homes' if old['home'] else old['name']
        newname = 'homes' if new['home'] else new['name']

        await self.add_path_local(new)
        await self.validate(new, 'sharingsmb_update', verrors, old=old)
        await self.legacy_afp_check(new, 'sharingsmb_update', verrors)
        check_mdns = False

        if app and not credential_has_full_admin(app.authenticated_credentials):
            if old['auxsmbconf'] != new['auxsmbconf']:
                verrors.add(
                    'smb_update.auxsmbconf',
                    'Changes to auxiliary parameters for SMB shares are restricted '
                    'to users with full administrative privileges.'
                )

        verrors.check()

        guest_changed = old['guestok'] != new['guestok']

        old_is_locked = (await self.get_instance(id_))['locked']
        if old['path'] != new['path']:
            new_is_locked = await self.middleware.call('pool.dataset.path_in_locked_datasets', new['path'])
        else:
            new_is_locked = old_is_locked

        compressed = await self.compress(new)
        await self.middleware.call(
            'datastore.update', self._config.datastore, id_, compressed,
            {'prefix': self._config.datastore_prefix})

        new['auxsmbconf'] = smb_strip_comments(new['auxsmbconf'])
        if not new_is_locked:
            """
            Enabling AAPL SMB2 extensions globally affects SMB shares. If this
            happens, the SMB service _must_ be restarted. Skip this step if dataset
            underlying the new path is encrypted.
            """
            do_global_reload = guest_changed or await self.must_reload_globals(new)
        else:
            do_global_reload = False

        if old_is_locked and new_is_locked:
            """
            Configuration change only impacts a locked SMB share. From standpoint of
            running config, this is a no-op. No need to restart or reload service.
            """
            return await self.get_instance(id_)

        try:
            await self.apply_share_changes(old_is_locked, new_is_locked, oldname, newname, old, new)
        except CallError as e:
            if e.errno != errno.EINVAL:
                raise e from None

            compressed = await self.compress(old)
            await self.middleware.call(
                'datastore.update', self._config.datastore, id_, compressed,
                {'prefix': self._config.datastore_prefix}
            )
            raise ValidationError('sharingsmb_update.auxsmbconf', e.errmsg)

        if new['enabled'] != old['enabled']:
            check_mdns = True

        # Homes shares require pam restrictions to be enabled (global setting)
        # so that we auto-generate the home directory via pam_mkhomedir.
        # Hence, we need to redo the global settings after changing homedir.
        if new.get('home') is not None and old['home'] != new['home']:
            do_global_reload = True

        if do_global_reload:
            ds = await self.middleware.call('directoryservices.status')
            if ds['type'] == DSType.AD.value.upper() and ds['status'] == 'HEALTHY':
                if new['home'] or old['home']:
                    await self.middleware.call('idmap.clear_idmap_cache')

            await self._service_change('cifs', 'restart')
        else:
            await self._service_change('cifs', 'reload')

        if check_mdns or old['timemachine'] != new['timemachine']:
            await self.middleware.call('service.reload', 'mdns')

        return await self.get_instance(id_)

    @accepts(Int('id'))
    async def do_delete(self, id_):
        """
        Delete SMB Share of `id`. This will forcibly disconnect SMB clients
        that are accessing the share.
        """
        share = await self.get_instance(id_)
        result = await self.middleware.call('datastore.delete', self._config.datastore, id_)

        share_name = 'homes' if share['home'] else share['name']
        share_list = await self.middleware.run_in_thread(reg_listshares)
        if share_name in share_list:
            await self.toggle_share(share_name, False)
            try:
                await self.middleware.call('smb.sharesec.remove', share_name)
            except RuntimeError as e:
                # TDB library sets arg0 to TDB errno and arg1 to TDB strerr
                if e.args[0] != TDBError.NOEXIST:
                    self.logger.warning('%s: Failed to remove share ACL', share_name, exc_info=True)
            except Exception:
                self.logger.debug('Failed to delete share ACL for [%s].', share_name, exc_info=True)

            try:
                await self.middleware.run_in_thread(reg_delshare, share_name)
            except MatchNotFound:
                pass
            except Exception:
                self.logger.warn('Failed to remove registry entry for [%s].', share_name, exc_info=True)

        if is_time_machine_share(share):
            await self.middleware.call('service.reload', 'mdns', {'ha_propagate': False})

        if share_name == 'homes':
            await self.middleware.call('etc.generate', 'smb')

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
    async def toggle_share(self, share_name, available):
        if not available:
            await self.close_share(share_name)

        await self.middleware.run_in_thread(reg_setparm, {
            'service': share_name,
            'parameters': {'available': {'parsed': available}}
        })

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
                """
                param = kv[0].strip()
                value = kv[1].strip()
                try:
                    await self.middleware.run_in_thread(
                        lpctx_validate_global_parm, param, value
                    )
                except RuntimeError:
                    verrors.add(
                        f'{schema_name}.auxsmbconf',
                        f'{param}: unable to set parameter to value: [{value}]'
                    )

        verrors.check()

    @private
    def validate_mount_info(self, verrors, schema, path):
        def validate_child(mnt):
            if '@' in mnt['mount_source']:
                return

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

            for c in mnt['children']:
                validate_child(c)

        def get_acl_type(sb_info):
            if 'NFS4ACL' in sb_info:
                return 'NFSV4'

            if 'POSIXACL' in sb_info:
                return 'POSIX'

            return 'OFF'

        st = self.middleware.call_sync('filesystem.stat', path)
        if st['type'] == 'SYMLINK':
            verrors.add(schema, f'{path}: is symbolic link.')
            return

        this_mnt = getmnttree(st['mount_id'])
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

        current_acltype = get_acl_type(this_mnt['super_opts'])
        for child in this_mnt['children']:
            validate_child(child)

    @private
    async def get_path_field(self, data):
        if self.path_field in data:
            return data[self.path_field]

        resolved = await self.add_path_local({'path': data['path']})
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
        except CallError as e:
            if e.errno == errno.ENOENT and e.errmsg == f'Path {path} not found':
                verrors.add(name, 'Path does not exist.')
            else:
                raise

    @private
    async def validate_share_name(self, name, schema_name, verrors, exist_ok=True):
        # Standards for SMB share name are defined in MS-FSCC 2.1.6
        # We are slighly more strict in that blacklist all unicode control characters
        if name.lower() in RESERVED_SHARE_NAMES:
            verrors.add(
                f'{schema_name}.name',
                f'{name} is a reserved section name, please select another one'
            )

        if len(name) == 0:
            verrors.add(
                f'{schema_name}.name',
                'Share name may not be an empty string.'
            )

        invalid_characters = INVALID_SHARE_NAME_CHARACTERS & set(name)
        if invalid_characters:
            verrors.add(
                f'{schema_name}.name',
                f'Share name contains the following invalid characters: {", ".join(invalid_characters)}'
            )

        if any(unicodedata.category(char) == 'Cc' for char in name):
            verrors.add(
                f'{schema_name}.name', 'Share name contains unicode control characters.'
            )

        if not exist_ok and await self.query([['name', 'C=', name]], {'select': ['name']}):
            verrors.add(
                f'{schema_name}.name', 'Share with this name already exists.', errno.EEXIST
            )

    @private
    async def validate(self, data, schema_name, verrors, old=None):
        """
        Path is a required key in almost all cases. There is a special edge case for LDAP
        [homes] shares. In this case we allow an empty path. Samba interprets this to mean
        that the path should be dynamically set to the user's home directory on the LDAP server.
        Local user auth to SMB shares is prohibited when LDAP is enabled with a samba schema.
        """
        if await self.home_exists(data['home'], schema_name, verrors, old):
            verrors.add(f'{schema_name}.home',
                        'Only one share is allowed to be a home share.')

        if await self.query([['name', 'C=', data['name']], ['id', '!=', data.get('id', 0)]]):
            verrors.add(f'{schema_name}.name', 'Share names are case-insensitive and must be unique')

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

        if data.get('name') is not None:
            await self.validate_share_name(data['name'], schema_name, verrors)

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

        smb_config = await self.middleware.call('smb.config')

        if data['audit']['enable']:
            if smb_config['enable_smb1']:
                verrors.add(
                    f'{schema_name}.audit.enable',
                    'SMB auditing is not supported if SMB1 protocol is enabled'
                )
            for key in ['watch_list', 'ignore_list']:
                for idx, group in enumerate(data['audit'][key]):
                    try:
                        await self.middleware.call('group.get_group_obj', {'groupname': group})
                    except KeyError:
                        verrors.add(f'{schema_name}.audit.{key}.{idx}',
                                    f'{group}: group does not exist.')

        if data['afp'] and not smb_config['aapl_extensions']:
            verrors.add(
                f'{schema_name}.afp',
                'Apple SMB2/3 protocol extension support is required by this parameter. '
                'This feature may be enabled in the general SMB server configuration.'
            )

        if data['timemachine'] or data['purpose'] in ('TIMEMACHINE', 'ENHANCED_TIMEMACHINE'):
            if not smb_config['aapl_extensions']:
                verrors.add(
                    f'{schema_name}.timemachine',
                    'Apple SMB2/3 protocol extension support is required by this parameter. '
                    'This feature may be enabled in the general SMB server configuration.'
                )

    @private
    @accepts(Dict('share_validate_payload', Str('name')), roles=['READONLY_ADMIN'])
    async def share_precheck(self, data):
        verrors = ValidationErrors()
        ad_enabled = (await self.middleware.call('activedirectory.config'))['enable']
        if not ad_enabled:
            local_smb_user_cnt = await self.middleware.call(
                'user.query',
                [['smb', '=', True]],
                {'count': True}
            )
            if local_smb_user_cnt == 0:
                verrors.add(
                    'sharing.smb.share_precheck',
                    'TrueNAS server must be joined to Active Directory or have '
                    'at least one local SMB user before creating an SMB share.'
                )

        if data.get('name') is not None:
            await self.validate_share_name(data['name'], 'sharing.smb.share_precheck', verrors, False)

        verrors.check()

    @private
    async def home_exists(self, home, schema_name, verrors, old=None):
        if not home:
            return

        home_filters = [('home', '=', True)]

        if old:
            home_filters.append(('id', '!=', old['id']))

        return await self.middleware.call(
            'datastore.query', self._config.datastore,
            home_filters, {'prefix': self._config.datastore_prefix}
        )

    @private
    async def add_path_local(self, data):
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

        for key, val in [('enable', False), ('watch_list', []), ('ignore_list', [])]:
            if key not in data['audit']:
                data['audit'][key] = val

        if data['purpose'] in ('TIMEMACHINE', 'ENHANCED_TIMEMACHINE'):
            # backstop to ensure all checks for time machine being enabled succeed
            data['timemachine'] = True

        return await self.add_path_local(data)

    @private
    async def compress(self, data_in):
        original_aux = data_in['auxsmbconf']
        data = apply_presets(data_in)

        data['hostsallow'] = ' '.join(data['hostsallow'])
        data['hostsdeny'] = ' '.join(data['hostsdeny'])
        data.pop(self.locked_field, None)
        data.pop('path_local', None)
        data['auxsmbconf'] = original_aux

        return data

    @accepts(roles=['SHARING_SMB_READ'])
    async def presets(self):
        """
        Retrieve pre-defined configuration sets for specific use-cases. These parameter
        combinations are often non-obvious, but beneficial in these scenarios.
        """
        return {x.name: x.value for x in SMBSharePreset}

    @accepts(Dict(
        'smb_share_acl',
        Str('share_name', required=True),
        List('share_acl', items=[
            Dict(
                'aclentry',
                SID('ae_who_sid', default=None),
                Dict(
                    'ae_who_id',
                    Str('id_type', enum=['USER', 'GROUP', 'BOTH']),
                    Int('id')
                ),
                Str('ae_perm', enum=['FULL', 'CHANGE', 'READ'], required=True),
                Str('ae_type', enum=['ALLOWED', 'DENIED'], required=True)
            ),
        ], default=[{'ae_who_sid': 'S-1-1-0', 'ae_perm': 'FULL', 'ae_type': 'ALLOWED'}]),
        register=True
    ), roles=['SHARING_SMB_WRITE'])
    @returns(Ref('smb_share_acl'))
    async def setacl(self, data):
        """
        Set an ACL on `share_name`. This only impacts access through the SMB protocol.
        Either ae_who_sid, ae_who_id must, ae_who_str be specified for each ACL entry in the
        share_acl. If multiple are specified, preference is in the following order: SID,
        unix id, name.

        `share_name` the name of the share

        `share_acl` a list of ACL entries (dictionaries) with the following keys:

        `ae_who_sid` who the ACL entry applies to expressed as a Windows SID

        `ae_who_id` Unix ID information for user or group to which the ACL entry applies.

        `ae_perm` string representation of the permissions granted to the user or group.
        FULL - grants read, write, execute, delete, write acl, and change owner.
        CHANGE - grants read, write, execute, and delete.
        READ - grants read and execute.

        `ae_type` can be ALLOWED or DENIED.
        """
        verrors = ValidationErrors()

        normalized_acl = []
        idmaps = await self.middleware.call('idmap.convert_unixids', [
            entry['ae_who_id'] for entry in data['share_acl'] if entry.get('ae_who_id')
        ])
        for idx, entry in enumerate(data['share_acl']):
            sid = None

            normalized_entry = {
                'ae_perm': entry['ae_perm'],
                'ae_type': entry['ae_type'],
                'ae_who_sid': entry.get('ae_who_sid')
            }

            if not set(entry.keys()) & set(['ae_who_str', 'ae_who_id']):
                verrors.add(
                    f'sharing_smb_setacl.share_acl.{idx}.sid',
                    'Either a SID or Unix ID must be specified for ACL entry.'
                )
                continue

            if normalized_entry['ae_who_sid']:
                if normalized_entry['ae_who_sid'].startswith((SID_LOCAL_USER_PREFIX, SID_LOCAL_GROUP_PREFIX)):
                    verrors.add(
                        f'sharing_smb_setacl.share_acl.{idx}.sid',
                        'SID entries for SMB Share ACLs may not be specially-encoded Unix User IDs or Groups.'
                    )
                else:
                    normalized_acl.append(normalized_entry)
                continue

            idmap_entry = idmaps['mapped'].get(f'{IDType[entry["ae_who_id"]["id_type"]].wbc_str()}:{entry["ae_who_id"]["id"]}')
            if not idmap_entry:
                verrors.add(
                    f'sharing_smb_setacl.share_acl.{idx}.ae_who_id',
                    'User or group does must exist and be an SMB account.'
                )
                continue

            sid = idmap_entry['sid']
            if sid.startswith((SID_LOCAL_USER_PREFIX, SID_LOCAL_GROUP_PREFIX)):
                verrors.add(
                    f'sharing_smb_setacl.share_acl.{idx}.ae_who_id',
                    'User or group must be explicitly configured as an SMB '
                    'account in order to be used in an SMB share ACL.'
                )

            normalized_entry['ae_who_sid'] = sid
            normalized_acl.append(normalized_entry)

        if data['share_name'].upper() == 'HOMES':
            share_filter = [['home', '=', True]]
        else:
            share_filter = [['name', 'C=', data['share_name']]]

        try:
            await self.middleware.call(
                'sharing.smb.query', share_filter, {'get': True, 'select': ['home', 'name']}
            )
        except MatchNotFound:
            verrors.add(
                'smb_share_acl.share_name',
                'Share does not exist'
            )

        verrors.check()
        if not normalized_acl:
            try:
                await self.middleware.call('smb.sharesec.remove', data['share_name'])
            except RuntimeError as e:
                # TDB library sets arg0 to TDB errno and arg1 to TDB strerr
                if e.args[0] != TDBError.NOEXIST:
                    raise
        else:
            await self.middleware.call('smb.sharesec.setacl', {
                'share_name': data['share_name'],
                'share_acl': normalized_acl
            })
        return await self.getacl({'share_name': data['share_name']})

    @accepts(Dict('smb_getacl', Str('share_name', required=True)), roles=['SHARING_SMB_READ'])
    @returns(Ref('smb_share_acl'))
    async def getacl(self, data):
        verrors = ValidationErrors()

        if data['share_name'].upper() == 'HOMES':
            share_filter = [['home', '=', True]]
        else:
            share_filter = [['name', 'C=', data['share_name']]]

        try:
            await self.middleware.call(
                'sharing.smb.query', share_filter, {'get': True, 'select': ['home', 'name']}
            )
        except MatchNotFound:
            verrors.add(
                'sharing_smb_getacl.share_name',
                'Share does not exist'
            )

        verrors.check()

        acl = await self.middleware.call('smb.sharesec.getacl', data['share_name'])
        sids = set([x['ae_who_sid'] for x in acl['share_acl'] if x['ae_who_sid'] != 'S-1-1-0'])
        if sids:
            try:
                conv = await self.middleware.call('idmap.convert_sids', list(sids))
            except CallError as e:
                # ENOTCONN means that winbindd is not running
                if e.errno != errno.ENOTCONN:
                    raise

                conv = {'mapped': {}}
        else:
            conv = None

        for entry in acl['share_acl']:
            if entry.get('ae_who_sid') == 'S-1-1-0':
                entry['ae_who_id'] = None
                entry['ae_who_str'] = 'everyone@'
                continue

            if not (unix_entry := conv['mapped'].get(entry['ae_who_sid'])):
                entry['ae_who_id'] = None
                entry['ae_who_str'] = None
                continue

            entry['ae_who_id'] = {
                'id_type': unix_entry['id_type'],
                'id': unix_entry['id']
            }

            entry['ae_who_str'] = await self.middleware.call(
                'idmap.id_to_name',
                unix_entry['id'],
                unix_entry['id_type']
            )

        return acl

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

        registry_shares = await self.middleware.run_in_thread(reg_listshares)

        cf_db = set([x['name'].casefold() for x in db_shares])
        cf_active = set([x['name'].casefold() for x in active_shares])
        cf_reg = set([x.casefold() for x in registry_shares])
        to_add = cf_active - cf_reg
        to_del = cf_reg - cf_active
        to_preserve = cf_db & to_del
        to_sync = cf_active - to_add

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
            except ValueError:
                self.logger.warning("Share [%s] has invalid configuration.", share, exc_info=True)
            except Exception:
                self.logger.warning("Failed to add SMB share [%s] while synchronizing registry config",
                                    share, exc_info=True)

        for share in to_del:
            await self.middleware.call('sharing.smb.toggle_share', share, False)
            if share in to_preserve:
                continue

            try:
                await self.middleware.run_in_thread(reg_delshare, share)
            except Exception:
                self.middleware.logger.warning('Failed to remove stale share [%s]',
                                               share, exc_info=True)

        for share in to_sync:
            share_conf = filter_list(active_shares, [['name', 'C=', share]])
            conf_diff = await self.middleware.call('sharing.smb.diff_middleware_and_registry', share, share_conf[0])
            try:
                await self.middleware.call('sharing.smb.apply_conf_diff', share, conf_diff)
            except Exception:
                self.middleware.logger.warning('Failed to sync configuration for share %s', share, exc_info=True)


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
    ], {'extra': {'use_cached_locked_datasets': False}}):
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

    async def is_child_of_path(self, resource, path, check_parent, exact_match):
        return await super().is_child_of_path(resource, path, check_parent, exact_match) if resource.get(
            self.path_field
        ) else False


async def setup(middleware):
    await middleware.call(
        'interface.register_listen_delegate',
        SystemServiceListenMultipleDelegate(middleware, 'smb', 'bindip'),
    )
    await middleware.call('pool.dataset.register_attachment_delegate', SMBFSAttachmentDelegate(middleware))
    middleware.register_hook('pool.post_import', pool_post_import, sync=True)
