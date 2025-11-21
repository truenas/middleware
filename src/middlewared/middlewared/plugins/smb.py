import asyncio
from copy import deepcopy
import errno
import os
from pathlib import Path
import uuid
import middlewared.sqlalchemy as sa

from middlewared.api import api_method
from middlewared.api.current import (
    SharingSMBGetaclArgs, SharingSMBGetaclResult,
    SharingSMBSetaclArgs, SharingSMBSetaclResult,
    SmbServiceEntry, SMBUpdateArgs, SMBUpdateResult,
    SMBUnixcharsetChoicesArgs, SMBUnixcharsetChoicesResult,
    SMBBindipChoicesArgs, SMBBindipChoicesResult,
    SharingSMBPresetsArgs, SharingSMBPresetsResult,
    SharingSMBSharePrecheckArgs, SharingSMBSharePrecheckResult,
    SmbShareEntry, SharingSMBCreateArgs, SharingSMBCreateResult,
    SharingSMBUpdateArgs, SharingSMBUpdateResult,
    SharingSMBDeleteArgs, SharingSMBDeleteResult,
)
from middlewared.common.attachment import LockableFSAttachmentDelegate
from middlewared.common.listen import SystemServiceListenMultipleDelegate
from middlewared.service import job, pass_app, private, SharingService
from middlewared.service import ConfigService, ValidationError, ValidationErrors
from middlewared.service_exception import CallError, MatchNotFound
from middlewared.plugins.smb_.constants import (
    NETIF_COMPLETE_SENTINEL,
    CONFIGURED_SENTINEL,
    SMB_AUDIT_DEFAULTS,
    SMBCmd,
    SMBPath,
)
from middlewared.plugins.smb_.constants import VEEAM_REPO_BLOCKSIZE
from middlewared.plugins.smb_.constants import SMBShareField as share_field
from middlewared.plugins.smb_.sharesec import remove_share_acl
from middlewared.plugins.smb_.util_param import (
    AUX_PARAM_BLACKLIST,
    smbconf_getparm,
    smbconf_list_shares,
    smbconf_sanity_check,
    lpctx_validate_parm
)
from middlewared.plugins.smb_.util_smbconf import generate_smb_conf_dict
from middlewared.plugins.smb_.utils import get_share_name, is_time_machine_share, smb_strip_comments
from middlewared.plugins.idmap_.idmap_constants import SID_LOCAL_USER_PREFIX, SID_LOCAL_GROUP_PREFIX
from middlewared.utils import run
from middlewared.utils.directoryservices.constants import DSStatus, DSType
from middlewared.utils.mount import getmnttree
from middlewared.utils.path import FSLocation, is_child_realpath
from middlewared.utils.privilege import credential_has_full_admin
from middlewared.utils.smb import SMBUnixCharset, SMBSharePurpose
from middlewared.utils.tdb import TDBError


BASE_SHARE_PARAMS = frozenset(['id', 'name', 'purpose', 'enabled', 'comment', 'ro', 'browsable', 'abe', 'audit', 'path'])


class SMBModel(sa.Model):
    __tablename__ = 'services_cifs'

    id = sa.Column(sa.Integer(), primary_key=True)
    cifs_srv_netbiosname = sa.Column(sa.String(120))
    cifs_srv_netbiosalias = sa.Column(sa.String(120), nullable=True)
    cifs_srv_workgroup = sa.Column(sa.String(120))
    cifs_srv_description = sa.Column(sa.String(120))
    cifs_srv_unixcharset = sa.Column(sa.String(120), default="UTF-8")
    cifs_srv_debug = sa.Column(sa.Boolean(), default=False)
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
    cifs_srv_secrets = sa.Column(sa.EncryptedText(), nullable=True)
    cifs_srv_multichannel = sa.Column(sa.Boolean, default=False)
    cifs_srv_encryption = sa.Column(sa.String(120), nullable=True)


class SMBService(ConfigService):

    class Config:
        service = 'cifs'
        service_verb = 'restart'
        datastore = 'services.cifs'
        datastore_extend = 'smb.smb_extend'
        datastore_prefix = 'cifs_srv_'
        cli_namespace = 'service.smb'
        role_prefix = 'SHARING_SMB'
        entry = SmbServiceEntry

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
        smb['guest'] = smb['guest'] or 'nobody'
        smb['netbiosalias'] = (smb['netbiosalias'] or '').split()
        smb['encryption'] = smb['encryption'] or 'DEFAULT'
        smb['server_sid'] = smb.pop('cifs_SID')
        smb['dirmask'] = smb['dirmask'] or 'DEFAULT'
        smb['filemask'] = smb['filemask'] or 'DEFAULT'
        smb.pop('secrets', None)
        return smb

    @api_method(SMBUnixcharsetChoicesArgs, SMBUnixcharsetChoicesResult)
    async def unixcharset_choices(self):
        return {str(charset): charset for charset in SMBUnixCharset}

    @private
    def generate_smb_configuration(self):
        if self.middleware.call_sync('failover.status') in ('SINGLE', 'MASTER'):
            smb_shares = self.middleware.call_sync('sharing.smb.query')
        else:
            # Do not include SMB shares in configuration on standby controller
            smb_shares = []

        ds_config = self.middleware.call_sync('directoryservices.config')
        smb_config = self.middleware.call_sync('smb.config')
        smb_shares = self.middleware.call_sync('sharing.smb.query', [
            [share_field.ENABLED, '=', True], [share_field.LOCKED, '=', False]
        ])
        bind_ip_choices = self.middleware.call_sync('smb.bindip_choices')
        is_enterprise = self.middleware.call_sync('system.is_enterprise')
        security_config = self.middleware.call_sync('system.security.config')
        veeam_repo_errors = []

        # admins may change ZFS recordsize from shell, UI, or API. Make sure we generate or clear any alerts.
        # we already have validation on SMB share create / update to check recordsize.
        for share in smb_shares:
            if share[share_field.PURPOSE] != SMBSharePurpose.VEEAM_REPOSITORY_SHARE:
                continue

            try:
                if os.statvfs(share[share_field.PATH]).f_bsize != VEEAM_REPO_BLOCKSIZE:
                    veeam_repo_errors.append(share[share_field.NAME])
            except FileNotFoundError:
                # possibly dataset not mounted
                pass
            except Exception:
                self.logger.debug('%s: statvfs for SMB share path failed', share[share_field.PATH], exc_info=True)
                pass

        if veeam_repo_errors:
            # These don't need to be fatal, but we should raise an alert so that admin can fix the record size
            self.middleware.call_sync('alert.oneshot_create', 'SMBVeeamFastClone', {
                'shares': ', '.join(veeam_repo_errors)
            })
        else:
            self.middleware.call_sync('alert.oneshot_delete', 'SMBVeeamFastClone')

        return generate_smb_conf_dict(
            ds_config,
            smb_config,
            smb_shares,
            bind_ip_choices,
            is_enterprise,
            security_config,
        )

    @api_method(SMBBindipChoicesArgs, SMBBindipChoicesResult)
    async def bindip_choices(self):
        """
        List of valid choices for IP addresses to which to bind the SMB service.
        Addresses assigned by DHCP are excluded from the results.
        """
        choices = {}

        if await self.middleware.call('failover.licensed'):
            master, backup, init = await self.middleware.call('failover.vip.get_states')
            for master_iface in await self.middleware.call('interface.query', [["id", "in", master + backup]]):
                for i in master_iface['failover_virtual_aliases']:
                    choices[i['address']] = i['address']

            return choices

        for i in await self.middleware.call('interface.ip_in_use'):
            choices[i['address']] = i['address']

        return choices

    @private
    async def domain_choices(self):
        """
        List of domains visible to winbindd. Returns empty list if winbindd is
        stopped.
        """
        domains = await self.middleware.call('idmap.known_domains')
        return [dom['netbios_domain'] for dom in domains]

    @private
    def getparm(self, parm, section):
        """
        Get a parameter from the smb4.conf file. This is more reliable than
        'testparm --parameter-name'. testparm will fail in a variety of
        conditions without returning the parameter's value.
        """
        return smbconf_getparm(parm, section)

    @private
    async def setup_directories(self):
        def create_dirs(spec, path):
            try:
                os.chmod(path, spec.mode)
                if os.stat(path).st_uid != 0:
                    self.logger.warning("%s: invalid owner for path. Correcting.", path)
                    os.chown(path, 0, 0)
            except FileNotFoundError:
                if spec.is_dir:
                    os.mkdir(path, spec.mode)

        await self.middleware.call('etc.generate', 'smb')

        for p in SMBPath:
            if p == SMBPath.STUBCONF:
                continue

            path = p.path
            await self.middleware.run_in_thread(create_dirs, p, path)

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

            timeout -= 1
            if timeout <= 0:
                self.logger.warning('Failed to detect any connected network interfaces.')
            else:
                await asyncio.sleep(1)

    @private
    @job(lock="smb_configure")
    async def configure(self, config_job):
        """
        Many samba-related tools will fail if they are unable to initialize
        a messaging context, which will happen if the samba-related directories
        do not exist or have incorrect permissions.
        """
        config_job.set_progress(0, 'Setting up SMB directories.')
        await self.setup_directories()

        """
        We may have failed over and changed our netbios name, which would also
        change the system SID. Flush out gencache entries before proceeding with
        local user account setup, otherwise we may end up with the incorrect
        domain SID for the guest account.
        """
        try:
            await self.middleware.call('idmap.gencache.flush')
        except Exception:
            self.logger.warning('SMB gencache flush failed', exc_info=True)

        """
        We cannot continue without network.
        Wait here until we see the ix-netif completion sentinel.
        """
        config_job.set_progress(20, 'Wait for ix-netif completion.')
        await self.netif_wait()

        config_job.set_progress(30, 'Setting up server SID.')
        await self.middleware.call('smb.set_system_sid')

        config_job.set_progress(40, 'Synchronizing passdb and groupmap.')
        await self.middleware.call('etc.generate', 'user')
        await self.middleware.call('smb.apply_account_policy')
        pdb_job = await self.middleware.call("smb.synchronize_passdb", True)
        grp_job = await self.middleware.call("smb.synchronize_group_mappings", True)
        await pdb_job.wait()
        await grp_job.wait()

        await self.middleware.call('smb.set_configured')
        """
        It is possible that system dataset was migrated or an upgrade
        wiped our secrets.tdb file. Re-import directory service secrets
        if they are missing from the current running configuration.
        """
        config_job.set_progress(65, 'Initializing directory services')
        ds_job = await self.middleware.call("directoryservices.initialize")
        await ds_job.wait()

        config_job.set_progress(70, 'Checking SMB server status.')
        if await self.middleware.call("service.started_or_enabled", "cifs"):
            config_job.set_progress(80, 'Restarting SMB service.')
            svc_job = await self.middleware.call('service.control', 'RESTART', 'cifs', {'ha_propagate': False})
            await svc_job.wait(raise_error=True)

        # Ensure that winbind is running once we configure SMB service
        svc_job = await self.middleware.call('service.control', 'RESTART', 'idmap', {'ha_propagate': False})
        await svc_job.wait(raise_error=True)

        config_job.set_progress(100, 'Finished configuring SMB.')

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

        if new['enable_smb1'] and new['encryption'] == 'REQUIRED':
            verrors.add(
                'smb_update.encryption',
                'Encryption may not be set to REQUIRED while SMB1 support is enabled.'
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
            if new[i] == 'DEFAULT':
                continue
            try:
                if int(new[i], 8) & ~0o11777:
                    raise ValueError('Not an octet')
            except (ValueError, TypeError):
                verrors.add(f'smb_update.{i}', 'Not a valid mask')

        if not new['aapl_extensions']:
            filters = [['OR', [
                ['options.afp', '=', True], ['options.timemachine', '=', True],
                ['purpose', '=', 'TIMEMACHINE_SHARE'],
                ['purpose', '=', 'FCP_SHARE'],
            ]]]
            if await self.middleware.call(
                'sharing.smb.query', filters, {'count': True, 'select': ['purpose']}
            ):
                verrors.add(
                    'smb_update.aapl_extensions',
                    'This option must be enabled when AFP, time machine, or Final Cut Pro shares are present'
                )

        if new['enable_smb1']:
            if audited_shares := await self.middleware.call(
                'sharing.smb.query', [['audit.enable', '=', True]], {'select': ['audit', 'name']}
            ):
                verrors.add(
                    'smb_update.enable_smb1',
                    f'The following SMB shares have auditing enabled: {", ".join([x["name"] for x in audited_shares])}'
                )

    @api_method(SMBUpdateArgs, SMBUpdateResult, audit='Update SMB configuration')
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

        `encryption` set global server behavior with regard to SMB encrpytion. Options are DEFAULT (which
        follows the upstream defaults -- currently identical to NEGOTIATE), NEGOTIATE encrypts SMB transport
        only if requested by the SMB client, DESIRED encrypts SMB transport if supported by the SMB client,
        REQUIRED only allows encrypted transport to the SMB server. Mandatory SMB encryption is not
        compatible with SMB1 server support in TrueNAS.

        `smb_options` smb.conf parameters that are not covered by the above supported configuration options may be
        added as an smb_option. Not all options are tested or supported, and behavior of smb_options may change
        between releases. Stability of smb.conf options is not guaranteed.
        """
        old = await self.config()

        new = old.copy()
        new.update(data)

        verrors = ValidationErrors()
        ds = await self.middleware.call('directoryservices.config')
        if ds['enable']:
            if new['netbiosname'].casefold() != old['netbiosname'].casefold():
                verrors.add(
                    'smb_update.netbiosname',
                    f'{old["netbiosname"]} -> {new["netbiosname"]}: '
                    'NetBIOS name may not be changed while directory service is enabled.'
                )

            if len(new['netbiosalias']) != len(old['netbiosalias']):
                verrors.add(
                    'smb_update.netbiosalias',
                    f'{old["netbiosalias"]} -> {new["netbiosalias"]}: '
                    'NetBIOS aliases may not be changed while directory service is enabled.'
                )
            else:
                for idx, nbname in new['netbiosalias']:
                    if old['netbiosalias'][idx].casefold() != new['netbiosalias'][idx].casefold():
                        verrors.add(
                            f'smb_update.netbiosalias.{idx}',
                            f'{old["netbiosalias"][idx]} -> {new["netbiosalias"][idx]}: '
                            'NetBIOS aliases may not be changed while directory service is enabled.'
                        )

            if old['workgroup'].casefold() != new['workgroup'].casefold():
                verrors.add('smb_update.workgroup', 'Workgroup may not be changed while directory service is enabled')

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

        if old['netbiosname'] != new_config['netbiosname']:
            await self.middleware.call('smb.set_system_sid')
            # we need to update domain field in passdb.tdb
            pdb_job = await self.middleware.call('smb.synchronize_passdb')
            await pdb_job.wait()

            await self.middleware.call('idmap.gencache.flush')
            srv = (await self.middleware.call("network.configuration.config"))["service_announcement"]
            await self.middleware.call("network.configuration.toggle_announcement", srv)

        if new['admin_group'] and new['admin_group'] != old['admin_group']:
            grp_job = await self.middleware.call('smb.synchronize_group_mappings')
            await grp_job.wait()

        await self._service_change(self._config.service, 'restart')
        return new_config

    @private
    async def compress(self, data):
        if data['encryption'] == 'DEFAULT':
            data['encryption'] = None

        if data['dirmask'] == 'DEFAULT':
            data['dirmask'] = ''

        if data['filemask'] == 'DEFAULT':
            data['filemask'] = ''

        data.pop('server_sid')
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
    cifs_auto_quota = sa.Column(sa.Integer())
    cifs_auto_snapshot = sa.Column(sa.Boolean())
    cifs_auto_dataset_creation = sa.Column(sa.Boolean())
    cifs_worm_grace_period = sa.Column(sa.Integer())


class SharingSMBService(SharingService):

    share_task_type = 'SMB'
    allowed_path_types = [FSLocation.EXTERNAL, FSLocation.LOCAL]

    class Config:
        namespace = 'sharing.smb'
        datastore = 'sharing.cifs_share'
        datastore_prefix = 'cifs_'
        datastore_extend = 'sharing.smb.extend'
        cli_namespace = 'sharing.smb'
        role_prefix = 'SHARING_SMB'
        entry = SmbShareEntry

    @api_method(
        SharingSMBCreateArgs, SharingSMBCreateResult,
        audit='SMB share create',
        audit_extended=lambda data: data['name'],
        pass_app=True,
        pass_app_rest=True
    )
    async def do_create(self, app, data):
        audit_info = deepcopy(SMB_AUDIT_DEFAULTS) | data.get(share_field.AUDIT)
        data[share_field.AUDIT] = audit_info

        verrors = ValidationErrors()
        aux = data[share_field.OPTS].get(share_field.AUX)

        if app and not credential_has_full_admin(app.authenticated_credentials):
            if aux:
                verrors.add(
                    f'sharingsmb_create.{share_field.OPTS}.{share_field.AUX}',
                    'Changes to auxiliary parameters for SMB shares are restricted '
                    'to users with full administrative privileges.'
                )

        await self.validate(data, 'sharingsmb_create', verrors)
        await self.legacy_afp_check(data, 'sharingsmb_create', verrors)

        verrors.check()

        if data[share_field.PURPOSE] in (SMBSharePurpose.LEGACY_SHARE, SMBSharePurpose.TIMEMACHINE_SHARE):
            if not data[share_field.OPTS][share_field.VUID]:
                data[share_field.OPTS][share_field.VUID] = str(uuid.uuid4())
            else:
                try:
                    uuid.UUID(data[share_field.OPTS][share_field.VUID])
                except Exception as exc:
                    raise ValidationError('sharingsmb_create.options.vuid', 'Invalid UUID') from exc

        compressed = await self.compress(data)

        data['id'] = await self.middleware.call(
            'datastore.insert', self._config.datastore, compressed,
            {'prefix': self._config.datastore_prefix})

        do_global_reload = await self.must_reload_globals(data)
        await self.middleware.call('etc.generate', 'smb')

        if aux:
            # Auxiliary parameters may contain invalid values for known parameters
            # that fail in such a way that break ability to create a loadparm context.
            # This was seen in wild with user who was blindly copy-pasting things from
            # internet.
            try:
                await self.middleware.run_in_thread(smbconf_sanity_check)
            except ValueError as exc:
                # Delete the share and regenerate config so that we're not broken
                await self.middleware.call('datastore.delete', self._config.datastore, data['id'])
                await self.middleware.call('etc.generate', 'smb')
                raise ValidationError(
                    f'sharingsmb_create.{share_field.OPTS}.{share_field.AUX}',
                    'Auxiliary parameters rejected because they would break the SMB server'
                ) from exc

        if do_global_reload:
            ds = await self.middleware.call('directoryservices.status')
            if ds['type'] == DSType.AD.value and ds['status'] == DSStatus.HEALTHY.name:
                if data['options'].get('home'):
                    await self.middleware.call('idmap.clear_idmap_cache')

            await self._service_change('cifs', 'restart')
        else:
            await self._service_change('cifs', 'reload')

        if is_time_machine_share(data):
            mdns_reload = await self.middleware.call('service.control', 'RELOAD', 'mdns', {'ha_propagate': False})
            # Failure to reload mDNS shouldn't be passed to API consumer
            await mdns_reload.wait()

        return await self.get_instance(data['id'])

    @private
    def smbconf_list_shares(self):
        return smbconf_list_shares()

    @private
    async def apply_share_changes(self, old_is_locked, new_is_locked, oldname, newname, old, new):
        if oldname != newname:
            await self.middleware.call('smb.sharesec.flush_share_info')

        if not old_is_locked and not new_is_locked:
            if oldname != newname:
                # This is disruptive change. Share is actually being removed and replaced.
                # Forcibly closes any existing SMB sessions.
                await self.toggle_share(oldname, False)

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

    @api_method(
        SharingSMBUpdateArgs, SharingSMBUpdateResult,
        audit='SMB share update',
        audit_callback=True,
        pass_app=True,
        pass_app_rest=True
    )
    async def do_update(self, app, audit_callback, id_, data):
        old = await self.get_instance(id_)
        audit_callback(old[share_field.NAME])

        verrors = ValidationErrors()
        old_audit = old[share_field.AUDIT]

        new = old.copy()
        new.update(data)
        new[share_field.AUDIT] = old_audit | data.get(share_field.AUDIT, {})

        oldname = get_share_name(old)
        newname = get_share_name(new)
        old_aux = old[share_field.OPTS].get(share_field.AUX)
        new_aux = new[share_field.OPTS].get(share_field.AUX)

        await self.validate(new, 'sharingsmb_update', verrors)
        await self.legacy_afp_check(new, 'sharingsmb_update', verrors)
        check_mdns = False

        if app and not credential_has_full_admin(app.authenticated_credentials):
            if old_aux != new_aux:
                verrors.add(
                    f'sharingsmb_update.{share_field.OPTS}.{share_field.AUX}',
                    'Changes to auxiliary parameters for SMB shares are restricted '
                    'to users with full administrative privileges.'
                )

        if new[share_field.PURPOSE] in (SMBSharePurpose.LEGACY_SHARE, SMBSharePurpose.TIMEMACHINE_SHARE):
            # Ignore NULL value for VUID in legacy share since there's no reason to forcibly generate a new VUID
            if share_field.VUID in new[share_field.OPTS] and new[share_field.OPTS][share_field.VUID] is None:
                if old[share_field.OPTS].get(share_field.VUID):
                    # Ignore NULL value for VUID in legacy share since there's no reason to forcibly generate a new VUID
                    del new[share_field.OPTS][share_field.VUID]
                else:
                    # We're potentially changing share purpose and so need a VUID
                    new[share_field.OPTS][share_field.VUID] = str(uuid.uuid4())
            elif share_field.VUID in new[share_field.OPTS]:
                # API consumer is providing a volume UUID. We need to check it.
                try:
                    uuid.UUID(new[share_field.OPTS][share_field.VUID])
                except Exception:
                    verrors.add(f'sharingsmb_update.{share_field.OPTS}.{share_field.VUID}', 'Invalid UUID')

        verrors.check()

        old_guest = old[share_field.OPTS].get(share_field.GUESTOK)
        new_guest = new[share_field.OPTS].get(share_field.GUESTOK)
        guest_changed = old_guest != new_guest

        old_is_locked = (await self.get_instance(id_))[share_field.LOCKED]
        if old[share_field.PATH] != new[share_field.PATH]:
            new_is_locked = await self.middleware.call('pool.dataset.path_in_locked_datasets', new[share_field.PATH])
        else:
            new_is_locked = old_is_locked

        compressed = await self.compress(new)
        await self.middleware.call(
            'datastore.update', self._config.datastore, id_, compressed,
            {'prefix': self._config.datastore_prefix})

        if new[share_field.PURPOSE] == SMBSharePurpose.LEGACY_SHARE:
            new[share_field.OPTS][share_field.AUX] = smb_strip_comments(new[share_field.OPTS][share_field.AUX])

        if new_aux:
            # Auxiliary parameters may contain invalid values for known parameters
            # that fail in such a way that break ability to create a loadparm context.
            # This was seen in wild with user who was blindly copy-pasting things from
            # internet.
            await self.middleware.call('etc.generate', 'smb')
            try:
                await self.middleware.run_in_thread(smbconf_sanity_check)
            except ValueError as exc:
                # restore original configuration
                compressed = await self.compress(old)

                await self.middleware.call(
                    'datastore.update', self._config.datastore, id_, compressed,
                    {'prefix': self._config.datastore_prefix}
                )
                await self.middleware.call('etc.generate', 'smb')

                raise ValidationError(
                    f'sharingsmb_update.{share_field.OPTS}.{share_field.AUX}',
                    'Auxiliary parameters rejected because they would break the SMB server'
                ) from exc

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
            raise ValidationError('sharingsmb_update.auxsmbconf', e.errmsg) from e

        if new[share_field.ENABLED] != old[share_field.ENABLED]:
            check_mdns = True

        # Homes shares require pam restrictions to be enabled (global setting)
        # so that we auto-generate the home directory via pam_mkhomedir.
        # Hence, we need to redo the global settings after changing homedir.
        old_home = old[share_field.OPTS].get(share_field.HOME)
        new_home = new[share_field.OPTS].get(share_field.HOME)
        if new_home is not None and old_home != new_home:
            do_global_reload = True

        if do_global_reload:
            ds = await self.middleware.call('directoryservices.status')
            if ds['type'] == DSType.AD.value and ds['status'] == DSStatus.HEALTHY.name:
                await self.middleware.call('idmap.clear_idmap_cache')

            await self._service_change('cifs', 'restart')
        else:
            await self._service_change('cifs', 'reload')

        if check_mdns:
            await (await self.middleware.call('service.control', 'RELOAD', 'mdns')).wait(raise_error=True)

        return await self.get_instance(id_)

    @api_method(
        SharingSMBDeleteArgs, SharingSMBDeleteResult,
        audit='SMB share delete',
        audit_callback=True,
    )
    async def do_delete(self, audit_callback, id_):
        """
        Delete SMB Share of `id`. This will forcibly disconnect SMB clients
        that are accessing the share.
        """
        share = await self.get_instance(id_)
        audit_callback(share[share_field.NAME])

        result = await self.middleware.call('datastore.delete', self._config.datastore, id_)

        share_name = get_share_name(share)
        share_list = await self.middleware.call('sharing.smb.smbconf_list_shares')

        # if share is currently active we need to gracefully clean up config and clients
        if share_name in share_list:
            await self.toggle_share(share_name, False)
            try:
                await self.middleware.run_in_thread(remove_share_acl, share_name)
            except RuntimeError as e:
                # TDB library sets arg0 to TDB errno and arg1 to TDB strerr
                if e.args[0] != TDBError.NOEXIST:
                    self.logger.warning('%s: Failed to remove share ACL', share_name, exc_info=True)
            except Exception:
                self.logger.debug('Failed to delete share ACL for [%s].', share_name, exc_info=True)

        if is_time_machine_share(share):
            await (await self.middleware.call('service.control', 'RELOAD', 'mdns', {'ha_propagate': False})).wait(raise_error=True)

        await self.middleware.call('etc.generate', 'smb')
        return result

    @private
    async def legacy_afp_check(self, data, schema, verrors):
        to_check = Path(data[share_field.PATH]).resolve(strict=False)
        legacy_afp = await self.query([
            (f"{share_field.OPTS}.{share_field.AFP}", "=", True),
            (share_field.ENABLED, "=", True),
            ("id", "!=", data.get("id"))
        ])
        for share in legacy_afp:
            share_afp = share[share_field.OPTS].get(share_field.AFP, False)
            new_afp = data[share_field.OPTS].get(share_field.AFP, False)

            if share_afp is new_afp:
                # Shares have matching AFP settings
                continue

            s = Path(share[share_field.PATH]).resolve(strict=not share[share_field.LOCKED])
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

        2) homes share (requires changing global PAM-related settings)
        """
        if data[share_field.OPTS].get(share_field.GUESTOK):
            """
            Verify that running configuration has required setting for guest access.
            """
            guest_mapping = await self.middleware.call('smb.getparm', 'map to guest', 'GLOBAL')
            if guest_mapping != 'Bad User':
                return True

        if data[share_field.OPTS].get(share_field.HOME):
            return True

        return False

    @private
    async def close_share(self, share_name):
        c = await run([SMBCmd.SMBCONTROL.value, 'smbd', 'close-share', share_name], check=False)
        if c.returncode != 0:
            if "Can't find pid" in c.stderr.decode():
                # smbd is not running. Don't log error message.
                return

            self.logger.warning('Failed to close smb share [%s]: [%s]',
                                share_name, c.stderr.decode().strip())

    @private
    async def toggle_share(self, share_name, available):
        if not available:
            await self.close_share(share_name)

        await self.middleware.call('etc.generate', 'smb')

    @private
    async def validate_aux_params(self, data, schema_name):
        """
        libsmbconf expects to be provided with key-value pairs.
        """
        verrors = ValidationErrors()
        for entry in data.splitlines():
            if entry == '' or entry.startswith(('#', ';')):
                continue

            kv = entry.split('=', 1)
            if len(kv) != 2:
                verrors.add(
                    f'{schema_name}',
                    f'Auxiliary parameters must be in the format of "key = value": {entry}'
                )
                continue

            if kv[0].strip() in AUX_PARAM_BLACKLIST:
                """
                This one checks our ever-expanding enumeration of badness.
                Parameters are blacklisted if incorrect values can prevent smbd from starting.
                """
                verrors.add(
                    f'{schema_name}',
                    f'{kv[0]} is a blacklisted auxiliary parameter. Changes to this parameter '
                    'are not permitted.'
                )

            if schema_name == 'smb_update.smb_options' and ':' not in kv[0]:
                """
                lib/param doesn't validate params containing a colon.
                """
                section = 'GLOBAL' if schema_name == 'smb_update.smb_options' else 'SHARE'
                param = kv[0].strip()
                value = kv[1].strip()
                try:
                    await self.middleware.run_in_thread(
                        lpctx_validate_parm, param, value, section
                    )
                except RuntimeError:
                    verrors.add(
                        f'{schema_name}',
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
            verrors.add(schema, f'{this_mnt["fs_type"]}: path is not a ZFS dataset')

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
            # The child filesystem may or may not be mounted under the SMB share. Two relevant
            # cases:
            #
            # 1. Share path is a directory without any filesystems mounted under it. In this
            #    case we don't want to raise validation errors for datasets that aren't mounted
            #    under the share path.
            # 2. Share path is a directory, but admin has mounted a remote NFS export under it.
            #    In this case we want to raise a validation error.
            if is_child_realpath(child['mountpoint'], path):
                validate_child(child)

    @private
    async def validate_external_path(self, verrors, name, path):
        if path != 'EXTERNAL':
            verrors.add(name, f'{path}: Path must be set to "EXTERNAL"')

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
    async def validate_share_name(self, name, schema_name, verrors, old=None):
        filters = [['name', 'C=', name]]
        if old:
            filters.append(['id', '!=', old['id']])

        if await self.query(filters, {'select': ['name']}):
            verrors.add(
                f'{schema_name}.name', 'Share with this name already exists.', errno.EEXIST
            )

    @private
    async def legacy_share_validate(self, data, schema_name, verrors, old):
        if await self.home_exists(data[share_field.OPTS][share_field.HOME], old):
            verrors.add(f'{schema_name}.{share_field.OPTS}.{share_field.HOME}',
                        'Only one share is allowed to be a home share.')

        if data[share_field.OPTS][share_field.AUX]:
            schema = f'{schema_name}.{share_field.OPTS}.{share_field.AUX}'
            await self.validate_aux_params(data[share_field.OPTS][share_field.AUX], schema)

    @private
    async def validate(self, data, schema_name, verrors, old=None):
        if await self.query([[share_field.NAME, 'C=', data[share_field.NAME]], ['id', '!=', data.get('id', 0)]]):
            verrors.add(f'{schema_name}.name', 'Share names are case-insensitive and must be unique')

        await self.validate_path_field(data, schema_name, verrors)
        timemachine = is_time_machine_share(data)

        if data.get(share_field.PATH) and data[share_field.PURPOSE] != SMBSharePurpose.EXTERNAL_SHARE:
            if data[share_field.PATH].startswith('EXTERNAL'):
                verrors.add(
                    f'{schema_name}.path',
                    'External paths may only be set for shares with an EXTERNAL_SHARE purpose'
                )
            else:
                stat_info = await self.middleware.call('filesystem.stat', data[share_field.PATH])
                if not data[share_field.OPTS].get(share_field.ACL, True) and stat_info['acl']:
                    verrors.add(
                        f'{schema_name}.acl',
                        f'ACL detected on {data["path"]}. ACLs must be stripped prior to creation '
                        'of SMB share.'
                    )

            if data[share_field.PURPOSE] == SMBSharePurpose.VEEAM_REPOSITORY_SHARE:
                if not await self.middleware.call('system.is_enterprise'):
                    verrors.add(
                        f'{schema_name}.{share_field.PURPOSE}',
                        'Veeam repository shares require a TrueNAS enterprise license.'
                    )
                bsize = (await self.middleware.call('filesystem.statfs', data[share_field.PATH]))['blocksize']
                if bsize != VEEAM_REPO_BLOCKSIZE:
                    verrors.add(
                        f'{schema_name}.{share_field.PATH}',
                        'The ZFS dataset recordsize property for a dataset used by a Veeam Repository SMB share '
                        'must be set to 128 KiB.'
                    )

        if data.get(share_field.NAME) is not None:
            await self.validate_share_name(share_field.NAME, schema_name, verrors, old)

        if timemachine and data[share_field.ENABLED]:
            ngc = await self.middleware.call('network.configuration.config')
            if not ngc['service_announcement']['mdns']:
                verrors.add(
                    f'{schema_name}.purpose',
                    'mDNS must be enabled in order to use an SMB share as a time machine target.'
                )

        smb_config = await self.middleware.call('smb.config')

        if data[share_field.AUDIT][share_field.AUDIT_ENABLE]:
            if smb_config['enable_smb1']:
                verrors.add(
                    f'{schema_name}.audit.enable',
                    'SMB auditing is not supported if SMB1 protocol is enabled'
                )

            has_limit = False
            for key in [share_field.AUDIT_WATCH_LIST, share_field.AUDIT_IGNORE_LIST]:
                for idx, group in enumerate(data[share_field.AUDIT][key]):
                    try:
                        await self.middleware.call('group.get_group_obj', {'groupname': group})
                    except KeyError:
                        verrors.add(f'{schema_name}.audit.{key}.{idx}',
                                    f'{group}: group does not exist.')

                    has_limit = True

            if not has_limit:
                verrors.add(f'{schema_name}.audit.enable',
                            'Watch list or ignore list is required to enable '
                            'auditing for an SMB share.')

        if data[share_field.OPTS].get(share_field.AFP) and not smb_config['aapl_extensions']:
            verrors.add(
                f'{schema_name}.{share_field.OPTS}.{share_field.AFP}',
                'Apple SMB2/3 protocol extension support is required by this parameter. '
                'This feature may be enabled in the general SMB server configuration.'
            )

        if timemachine and not smb_config['aapl_extensions']:
            verrors.add(
                f'{schema_name}.purpose',
                'Apple SMB2/3 protocol extension support is required by this parameter. '
                'This feature may be enabled in the general SMB server configuration.'
            )

        if data[share_field.PURPOSE] == SMBSharePurpose.FCP_SHARE and not smb_config['aapl_extensions']:
            verrors.add(
                f'{schema_name}.purpose',
                'Apple SMB2/3 protocol extension support is required by this parameter. '
                'This feature may be enabled in the general SMB server configuration.'
            )

        if data[share_field.PURPOSE] == SMBSharePurpose.LEGACY_SHARE:
            await self.legacy_share_validate(data, schema_name, verrors, old)

    @api_method(SharingSMBSharePrecheckArgs, SharingSMBSharePrecheckResult, roles=['READONLY_ADMIN'])
    async def share_precheck(self, data):
        # This endpoint provides the UI a mechanism to determine whether popup prompting to create
        # SMB users should occur when auto-creating an SMB share in the datasets form.
        verrors = ValidationErrors()
        ds_enabled = (await self.middleware.call('directoryservices.config'))['enable']
        if not ds_enabled:
            local_smb_user_cnt = await self.middleware.call(
                'user.query',
                [['smb', '=', True], ['local', '=', True]],
                {'count': True}
            )
            if local_smb_user_cnt == 0:
                verrors.add(
                    'sharing.smb.share_precheck',
                    'TrueNAS server must be joined to a directory service or have '
                    'at least one local SMB user before creating an SMB share.'
                )

        if data.get(share_field.NAME) is not None:
            await self.validate_share_name(data[share_field.NAME], 'sharing.smb.share_precheck', verrors)

        verrors.check()

    @private
    async def home_exists(self, home, old=None):
        if not home:
            return

        # Since this is raw datastore query, it's `home` and not `options.home`
        home_filters = [('home', '=', True)]

        if old:
            home_filters.append(('id', '!=', old['id']))

        return await self.middleware.call(
            'datastore.query', self._config.datastore,
            home_filters, {'prefix': self._config.datastore_prefix}
        )

    @private
    async def extend(self, data):
        out = {}
        for key in BASE_SHARE_PARAMS:
            out[key] = data.pop(key)

        out[share_field.RO] = out.pop('ro')
        out[share_field.ABE] = out.pop('abe')
        out[share_field.OPTS] = {}

        match out[share_field.PURPOSE]:
            case SMBSharePurpose.DEFAULT_SHARE | SMBSharePurpose.MULTIPROTOCOL_SHARE | SMBSharePurpose.FCP_SHARE:
                out[share_field.OPTS][share_field.AAPL_MANGLING] = data[share_field.AAPL_MANGLING]
            case SMBSharePurpose.TIMEMACHINE_SHARE:
                out[share_field.OPTS] = {
                    share_field.AUTO_SNAP: data[share_field.AUTO_SNAP],
                    share_field.AUTO_DS: data[share_field.AUTO_DS],
                    share_field.DS_NAMING_SCHEMA: data[share_field.PATH_SUFFIX] or None,
                    share_field.TIMEMACHINE_QUOTA: data[share_field.TIMEMACHINE_QUOTA],
                    share_field.VUID: data[share_field.VUID] or None,
                }
            case SMBSharePurpose.TIME_LOCKED_SHARE:
                out[share_field.OPTS] = {
                    share_field.WORM_GRACE: data['worm_grace_period'] or 900,
                    share_field.AAPL_MANGLING: data[share_field.AAPL_MANGLING],
                }
            case SMBSharePurpose.PRIVATE_DATASETS_SHARE:
                out[share_field.OPTS] = {
                    share_field.DS_NAMING_SCHEMA: data[share_field.PATH_SUFFIX] or None,
                    share_field.AUTO_QUOTA: data[share_field.AUTO_QUOTA],
                    share_field.AAPL_MANGLING: data[share_field.AAPL_MANGLING],
                }
            case SMBSharePurpose.EXTERNAL_SHARE:
                if out[share_field.PATH].startswith('EXTERNAL:'):
                    remote_path = out[share_field.PATH].removeprefix('EXTERNAL:').split(',')
                else:
                    remote_path = None

                out[share_field.OPTS] = {
                    share_field.REMOTE_PATH: remote_path,
                }
                out[share_field.PATH] = 'EXTERNAL'
            case SMBSharePurpose.LEGACY_SHARE:
                # catchall for all of old options
                data.pop('share_acl', None)
                data[share_field.HOSTSALLOW] = data[share_field.HOSTSALLOW].split()
                data[share_field.HOSTSDENY] = data[share_field.HOSTSDENY].split()
                data[share_field.PATH_SUFFIX] = data[share_field.PATH_SUFFIX] or None
                data[share_field.VUID] = data[share_field.VUID] or None
                for param in (
                    share_field.AUTO_QUOTA,
                    share_field.AUTO_DS,
                    share_field.AUTO_SNAP,
                    'worm_grace_period',
                ):
                    data.pop(param)

                out[share_field.OPTS] = data

        for key, default in [
            (share_field.AUDIT_ENABLE, False),
            (share_field.AUDIT_WATCH_LIST, []),
            (share_field.AUDIT_IGNORE_LIST, [])
        ]:
            if key not in out[share_field.AUDIT]:
                out[share_field.AUDIT][key] = default

        return out

    @private
    async def compress(self, data_in):
        data = data_in.copy()
        opts = data.pop(share_field.OPTS, {})

        if share_field.DS_NAMING_SCHEMA in opts:
            data[share_field.PATH_SUFFIX] = opts.pop(share_field.DS_NAMING_SCHEMA, '')
        else:
            data[share_field.PATH_SUFFIX] = opts.pop(share_field.PATH_SUFFIX, '')

        # handle explicit NULL from API
        if data[share_field.PATH_SUFFIX] is None:
            data[share_field.PATH_SUFFIX] = ''

        data[share_field.AAPL_MANGLING] = opts.pop(share_field.AAPL_MANGLING, False)

        data['ro'] = data.pop(share_field.RO)
        data['abe'] = data.pop(share_field.ABE)
        data[share_field.TIMEMACHINE_QUOTA] = opts.pop(share_field.TIMEMACHINE_QUOTA, 0)

        # normalize VUID to uuid or empty string. May be None type prior to compression
        if share_field.VUID in opts:
            data[share_field.VUID] = opts[share_field.VUID] or ''

        match data[share_field.PURPOSE]:
            case SMBSharePurpose.LEGACY_SHARE:
                data[share_field.HOSTSALLOW] = ' '.join(opts.pop(share_field.HOSTSALLOW, []))
                data[share_field.HOSTSDENY] = ' '.join(opts.pop(share_field.HOSTSDENY, []))
            case SMBSharePurpose.TIME_LOCKED_SHARE:
                data['worm_grace_period'] = opts.pop(share_field.WORM_GRACE, 900)
            case SMBSharePurpose.EXTERNAL_SHARE:
                data[share_field.PATH] = f'EXTERNAL:{",".join(opts.pop(share_field.REMOTE_PATH, []))}'
            case _:
                pass

        # Set defaults for our legacy fields y4
        for param in (share_field.DURABLEHANDLE, share_field.SHADOWCOPY, share_field.STREAMS):
            if param not in data:
                data[param] = True

        data.pop(self.locked_field, None)
        data.update(opts)

        if data[share_field.PURPOSE] != SMBSharePurpose.LEGACY_SHARE:
            # Make sure to set these keys to defaults for sake of DB consistency
            # These ones default to True
            for param in (share_field.DURABLEHANDLE, share_field.SHADOWCOPY, share_field.STREAMS, share_field.ACL):
                data[param] = True

            # These ones default to False
            for param in (
                share_field.HOME, share_field.GUESTOK, share_field.FSRVP, share_field.AFP, share_field.RECYCLE,
                share_field.TIMEMACHINE
            ):
                data[param] = False

        return data

    @api_method(SharingSMBPresetsArgs, SharingSMBPresetsResult, roles=['SHARING_SMB_READ'])
    async def presets(self):
        """
        Retrieve pre-defined configuration sets for specific use-cases. These parameter
        combinations are often non-obvious, but beneficial in these scenarios.
        """
        return {x.name: {'verbose_name': x.value} for x in SMBSharePurpose}

    @api_method(
        SharingSMBSetaclArgs, SharingSMBSetaclResult,
        roles=['SHARING_SMB_WRITE'],
        audit='Setacl SMB share',
        audit_extended=lambda data: data['share_name']
    )
    async def setacl(self, data):
        """
        Set an ACL on `share_name`. This only impacts access through the SMB protocol.

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

            match entry['ae_who_id']['id_type']:
                case 'USER':
                    method = 'user.query'
                    key = 'uid'
                case 'GROUP' | 'BOTH':
                    method = 'group.query'
                    key = 'gid'
                case _:
                    raise ValueError(f'{entry["ae_who_id"]["id_type"]}: unexpected ID type')

            sid = (await self.middleware.call(method, [[key, '=', entry['ae_who_id']['id']]], {'get': True}))['sid']
            if sid is None:
                verrors.add(
                    f'sharing_smb_setacl.share_acl.{idx}.ae_who_id',
                    'User or group does must exist and be an SMB account.'
                )
                continue

            if sid.startswith((SID_LOCAL_USER_PREFIX, SID_LOCAL_GROUP_PREFIX)):
                verrors.add(
                    f'sharing_smb_setacl.share_acl.{idx}.ae_who_id',
                    'User or group must be explicitly configured as an SMB '
                    'account in order to be used in an SMB share ACL.'
                )

            normalized_entry['ae_who_sid'] = sid
            normalized_acl.append(normalized_entry)

        if data['share_name'].upper() == 'HOMES':
            share_filter = [['options.home', '=', True]]
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
                await self.middleware.run_in_thread(remove_share_acl, data['share_name'])
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

    @api_method(
        SharingSMBGetaclArgs, SharingSMBGetaclResult,
        roles=['SHARING_SMB_READ'],
        audit='Getacl SMB share',
        audit_extended=lambda data: data['share_name']
    )
    async def getacl(self, data):
        verrors = ValidationErrors()

        if data['share_name'].upper() == 'HOMES':
            share_filter = [['options.home', '=', True]]
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
        sids = set(x['ae_who_sid'] for x in acl['share_acl'] if x['ae_who_sid'] != 'S-1-1-0')
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
        await middleware.call('etc.generate', 'smb')
        return

    if not await middleware.call("smb.is_configured"):
        middleware.logger.warning(
            "Skipping SMB share config sync because SMB service "
            "has not been fully initialized."
        )
        return

    path = f'/mnt/{pool["name"]}'
    if await middleware.call(
        'sharing.smb.query',
        [('OR', [
            (share_field.PATH, '=', path),
            (share_field.PATH, '^', f'{path}/'),
        ])]
    ):
        await middleware.call('smb.disable_acl_if_trivial')
        await middleware.call('etc.generate', 'smb')


class SMBFSAttachmentDelegate(LockableFSAttachmentDelegate):
    name = 'smb'
    title = 'SMB Share'
    service = 'cifs'
    service_class = SharingSMBService

    async def delete(self, attachments):
        for attachment in attachments:
            await self.middleware.call('sharing.smb.delete', attachment['id'])
            await self.remove_alert(attachment)

        if attachments:
            await self.restart_reload_services(attachments)

    async def stop(self, attachments):
        for share in attachments:
            await self.middleware.call('sharing.smb.close_share', share[share_field.NAME])

    async def restart_reload_services(self, attachments):
        """
        mDNS may need to be reloaded if a time machine share is located on
        the share being attached.
        """
        await self.middleware.call('smb.disable_acl_if_trivial')
        if not await self.middleware.call("smb.is_configured"):
            self.logger.warning(
                "Skipping SMB share config sync because SMB service "
                "has not been fully initialized."
            )
            return

        await self.middleware.call('etc.generate', 'smb')
        await (await self.middleware.call('service.control', 'RELOAD', 'mdns')).wait(raise_error=True)

    async def is_child_of_path(self, resource, path, check_parent, exact_match):
        return await super().is_child_of_path(resource, path, check_parent, exact_match) if resource.get(
            self.path_field
        ) else False


async def systemdataset_setup_hook(middleware, data):
    if not data['in_progress']:
        await middleware.call('smb.setup_directories')


async def hook_post_generic(middleware, datasets):
    await (await middleware.call('service.control', 'RELOAD', 'cifs')).wait()


async def setup(middleware):
    await middleware.call(
        'interface.register_listen_delegate',
        SystemServiceListenMultipleDelegate(middleware, 'smb', 'bindip'),
    )
    await middleware.call('pool.dataset.register_attachment_delegate', SMBFSAttachmentDelegate(middleware))
    middleware.register_hook('dataset.post_lock', hook_post_generic, sync=True)
    middleware.register_hook('dataset.post_unlock', hook_post_generic, sync=True)
    middleware.register_hook('pool.post_import', pool_post_import, sync=True)
    middleware.register_hook("sysdataset.setup", systemdataset_setup_hook)
