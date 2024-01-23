import enum
import os
import struct
import errno

from base64 import b64decode
from middlewared.schema import accepts, Dict, List, OROperator, Ref, returns, Str
from middlewared.service import no_authz_required, Service, private, job
from middlewared.plugins.smb import SMBCmd, SMBPath
from middlewared.service_exception import CallError, MatchNotFound

DEFAULT_AD_CONF = {
    "id": 1,
    "bindname": "",
    "verbose_logging": False,
    "kerberos_principal": "",
    "kerberos_realm": None,
    "createcomputer": "",
    "disable_freenas_cache": False,
    "restrict_pam": False
}

DEPENDENT_SERVICES = ['smb', 'nfs', 'ssh']


class DSStatus(enum.Enum):
    DISABLED = enum.auto()
    FAULTED = 1028  # MSG_WINBIND_OFFLINE
    LEAVING = enum.auto()
    JOINING = enum.auto()
    HEALTHY = 1027  # MSG_WINBIND_ONLINE


class DSType(enum.Enum):
    AD = 'activedirectory'
    LDAP = 'ldap'


class SSL(enum.Enum):
    NOSSL = 'OFF'
    USESSL = 'ON'
    USESTARTTLS = 'START_TLS'


class SASL_Wrapping(enum.Enum):
    PLAIN = 'PLAIN'
    SIGN = 'SIGN'
    SEAL = 'SEAL'


class NSS_Info(enum.Enum):
    SFU = ('SFU', [DSType.AD])
    SFU20 = ('SFU20', [DSType.AD])
    RFC2307 = ('RFC2307', [DSType.AD, DSType.LDAP])
    RFC2307BIS = ('RFC2307BIS', [DSType.LDAP])
    TEMPLATE = ('TEMPLATE', [DSType.AD])


class DirectoryServices(Service):
    class Config:
        service = "directoryservices"
        cli_namespace = "directory_service"

    @no_authz_required
    @accepts()
    @returns(Dict(
        'directory_services_states',
        Ref('directoryservice_state', 'activedirectory'),
        Ref('directoryservice_state', 'ldap')
    ))
    async def get_state(self):
        """
        `DISABLED` Directory Service is disabled.

        `FAULTED` Directory Service is enabled, but not HEALTHY. Review logs and generated alert
        messages to debug the issue causing the service to be in a FAULTED state.

        `LEAVING` Directory Service is in process of stopping.

        `JOINING` Directory Service is in process of starting.

        `HEALTHY` Directory Service is enabled, and last status check has passed.
        """
        try:
            return await self.middleware.call('cache.get', 'DS_STATE')
        except KeyError:
            ds_state = {}
            for srv in DSType:
                try:
                    res = await self.middleware.call(f'{srv.value}.started')
                    ds_state[srv.value] = DSStatus.HEALTHY.name if res else DSStatus.DISABLED.name

                except CallError as e:
                    if e.errno == errno.EINVAL:
                        self.logger.warning('%s: setting service to DISABLED due to invalid config',
                                            srv.value.upper(), exc_info=True)
                        ds_state[srv.value] = DSStatus.DISABLED.name
                    else:
                        ds_state[srv.value] = DSStatus.FAULTED.name

                except Exception:
                    ds_state[srv.value] = DSStatus.FAULTED.name

            await self.middleware.call('cache.put', 'DS_STATE', ds_state, 60)
            return ds_state

    @private
    async def set_state(self, new):
        ds_state = {
            'activedirectory': DSStatus.DISABLED.name,
            'ldap': DSStatus.DISABLED.name,
        }

        try:
            old_state = await self.middleware.call('cache.get', 'DS_STATE')
            ds_state.update(old_state)
        except KeyError:
            self.logger.trace("No previous DS_STATE exists. Lazy initializing for %s", new)

        ds_state.update(new)
        self.middleware.send_event('directoryservices.status', 'CHANGED', fields=ds_state)
        return await self.middleware.call('cache.put', 'DS_STATE', ds_state)

    @accepts()
    @job()
    async def cache_refresh(self, job):
        """
        This method refreshes the directory services cache for users and groups that is
        used as a backing for `user.query` and `group.query` methods. The first cache fill in
        an Active Directory domain may take a significant amount of time to complete and
        so it is performed as within a job. The most likely situation in which a user may
        desire to refresh the directory services cache is after new users or groups  to a remote
        directory server with the intention to have said users or groups appear in the
        results of the aforementioned account-related methods.

        A cache refresh is not required in order to use newly-added users and groups for in
        permissions and ACL related methods. Likewise, a cache refresh will not resolve issues
        with users being unable to authenticate to shares.
        """
        return await job.wrap(await self.middleware.call('dscache.refresh'))

    @private
    @returns(List(
        'ldap_ssl_choices', items=[
            Str('ldap_ssl_choice', enum=[x.value for x in list(SSL)], default=SSL.USESSL.value, register=True)
        ]
    ))
    async def ssl_choices(self, dstype):
        return [x.value for x in list(SSL)]

    @private
    @returns(List(
        'sasl_wrapping_choices', items=[
            Str('sasl_wrapping_choice', enum=[x.value for x in list(SASL_Wrapping)], register=True)
        ]
    ))
    async def sasl_wrapping_choices(self, dstype):
        return [x.value for x in list(SASL_Wrapping)]

    @private
    @returns(OROperator(
        List('ad_nss_choices', items=[Str(
            'nss_info_ad',
            enum=[x.value[0] for x in NSS_Info if DSType.AD in x.value[1]],
            default=NSS_Info.SFU.value[0],
            register=True
        )]),
        List('ldap_nss_choices', items=[Str(
            'nss_info_ldap',
            enum=[x.value[0] for x in NSS_Info if DSType.LDAP in x.value[1]],
            default=NSS_Info.RFC2307.value[0],
            register=True)
        ]),
        name='nss_info_choices'
    ))
    async def nss_info_choices(self, dstype):
        ds = DSType(dstype.lower())
        ret = []

        for x in list(NSS_Info):
            if ds in x.value[1]:
                ret.append(x.value[0])

        return ret

    @private
    async def get_last_password_change(self, domain=None):
        """
        Returns unix timestamp of last password change according to
        the secrets.tdb (our current running configuration), and what
        we have in our database.
        """
        ha_mode = await self.middleware.call('smb.get_smb_ha_mode')
        smb_config = await self.middleware.call('smb.config')
        if domain is None:
            domain = smb_config['workgroup']

        try:
            passwd_ts = await self.middleware.call(
                'directoryservices.secrets.last_password_change', domain
            )
        except MatchNotFound:
            passwd_ts = None

        db_secrets = await self.middleware.call('directoryservices.secrets.get_db_secrets')
        server_secrets = db_secrets.get(f"{smb_config['netbiosname_local'].upper()}$")
        if server_secrets is None:
            return {"dbconfig": None, "secrets": passwd_ts}

        try:
            stored_ts_bytes = server_secrets[f'SECRETS/MACHINE_LAST_CHANGE_TIME/{domain.upper()}']
            stored_ts = struct.unpack("<L", b64decode(stored_ts_bytes))[0]
        except KeyError:
            stored_ts = None

        return {"dbconfig": stored_ts, "secrets": passwd_ts}

    @private
    async def initialize(self, data=None):
        """
        Ensure that secrets.tdb at a minimum exists. If it doesn't exist, try to restore
        from a backup stored in our config file. If this fails, try to use what
        auth info we have to recover the information. If we are in an LDAP
        environment with a samba schema in use, we just need to write the password into
        secrets.tdb.
        """
        if data is None:
            ldap_conf = await self.middleware.call("ldap.config")
            ldap_enabled = ldap_conf['enable']
            ad_enabled = (await self.middleware.call("activedirectory.config"))['enable']
        else:
            ldap_enabled = data['ldap']
            ad_enabled = data['activedirectory']
            if ldap_enabled:
                ldap_conf = await self.middleware.call("ldap.config")

        workgroup = (await self.middleware.call("smb.config"))["workgroup"]
        is_kerberized = ad_enabled

        if not ldap_enabled and not ad_enabled:
            return

        health_check = 'activedirectory.started' if ad_enabled else 'ldap.started'

        has_secrets = await self.middleware.call('directoryservices.secrets.has_domain', workgroup)
        if ad_enabled and not has_secrets:
            self.logger.warning("Domain secrets database does not exist. "
                                "Attempting to restore.")

            if not await self.middleware.call("directoryservices.secrets.restore"):
                self.logger.warning("Failed to restore domain secrets database. "
                                    "Re-joining AD domain may be required.")

        elif ldap_enabled and not has_secrets and ldap_conf["has_samba_schema"]:
            self.logger.warning("LDAP SMB secrets database does not exist. "
                                "attempting to restore secrets from configuration file.")
            await self.middleware.call("smb.store_ldap_admin_password")

        if ldap_enabled and ldap_conf['kerberos_realm']:
            is_kerberized = True

        try:
            await self.middleware.call('idmap.gencache.flush')
        except Exception:
            self.logger.warning('Cache flush failed', exc_info=True)

        if is_kerberized:
            try:
                await self.middleware.call('kerberos.start')
            except CallError:
                self.logger.warning("Failed to start kerberos after directory service "
                                    "initialization. Services dependent on kerberos may"
                                    "not work correctly.", exc_info=True)

        await self.middleware.call(health_check)

    @private
    def restart_dependent_services(self):
        for svc in self.middleware.call_sync('service.query', [['OR', [
            ['enable', '=', True],
            ['state', '=', 'RUNNING']
        ]], ['service', 'in', DEPENDENT_SERVICES]]):
            self.middleware.call_sync('service.restart', svc['service'])

    @private
    @job(lock='ds_init', lock_queue_size=1)
    def setup(self, job):
        config_in_progress = self.middleware.call_sync("core.get_jobs", [
            ["method", "=", "smb.configure"],
            ["state", "=", "RUNNING"]
        ])
        if config_in_progress:
            job.set_progress(0, "waiting for smb.configure to complete")
            wait_id = self.middleware.call_sync('core.job_wait', config_in_progress[0]['id'])
            wait_id.wait_sync()

        if not self.middleware.call_sync('smb.is_configured'):
            raise CallError('Skipping directory service setup due to SMB service being unconfigured')


        failover_status = self.middleware.call_sync('failover.status')
        if failover_status not in ('SINGLE', 'MASTER'):
            self.logger.debug('%s: skipping directory service setup due to failover status', failover_status)
            job.set_progress(100, f'{failover_status}: skipping directory service setup due to failover status')
            return

        ldap_enabled = self.middleware.call_sync('ldap.config')['enable']
        ad_enabled = self.middleware.call_sync('activedirectory.config')['enable']
        if not ldap_enabled and not ad_enabled:
            job.set_progress(100, "No directory services enabled.")
            return

        # Started methods will transition us from JOINING to HEALTHY
        # which allows the cache refresh to proceed
        if ad_enabled:
            self.middleware.call_sync('activedirectory.started')
        else:
            self.middleware.call_sync('ldap.started')

        job.set_progress(10, 'Refreshing cache'),
        cache_refresh = self.middleware.call_sync('dscache.refresh')
        cache_refresh.wait_sync()

        job.set_progress(75, 'Restarting dependent services')
        self.restart_dependent_services()
        job.set_progress(100, 'Setup complete')


async def __init_directory_services(middleware, event_type, args):
    await middleware.call('directoryservices.setup')


async def setup(middleware):
    middleware.event_subscribe('system.ready', __init_directory_services)
    middleware.event_register('directoryservices.status', 'Sent on directory service state changes.')
