import enum
import struct

from base64 import b64decode
from middlewared.schema import accepts, Dict, List, OROperator, returns, Str
from middlewared.service import no_authz_required, Service, private, job
from middlewared.service_exception import CallError, MatchNotFound
from middlewared.utils.directoryservices.constants import (
    DSStatus, DSType, NSS_Info
)
from middlewared.utils.directoryservices.health import DSHealthObj

DEPENDENT_SERVICES = ['smb', 'nfs', 'ssh']


class SSL(enum.Enum):
    NOSSL = 'OFF'
    USESSL = 'ON'
    USESTARTTLS = 'START_TLS'


class SASL_Wrapping(enum.Enum):
    PLAIN = 'PLAIN'
    SIGN = 'SIGN'
    SEAL = 'SEAL'


class DirectoryServices(Service):
    class Config:
        service = "directoryservices"
        cli_namespace = "directory_service"

    @no_authz_required
    @accepts()
    @returns(Dict(
        'directoryservices_status',
        Str('type', enum=[x.value for x in DSType], null=True),
        Str('status', enum=[status.name for status in DSStatus], null=True)
    ))
    def status(self):
        """
        Provide the type and status of the currently-enabled directory service
        """
        if not DSHealthObj.initialized:
            try:
                self.middleware.call_sync('directoryservices.health.check')
            except Exception:
                pass

        status = DSHealthObj.dump()
        status.pop('status_msg')
        return status

    @no_authz_required
    @accepts()
    @returns(Dict(
        'directory_services_states',
        Str(DSType.AD.value.lower(), enum=[status.name for status in DSStatus]),
        Str(DSType.LDAP.value.lower(), enum=[status.name for status in DSStatus]),
    ))
    def get_state(self):
        """
        `DISABLED` Directory Service is disabled.

        `FAULTED` Directory Service is enabled, but not HEALTHY. Review logs and generated alert
        messages to debug the issue causing the service to be in a FAULTED state.

        `LEAVING` Directory Service is in process of stopping.

        `JOINING` Directory Service is in process of starting.

        `HEALTHY` Directory Service is enabled, and last status check has passed.
        """
        output = {'activedirectory': DSStatus.DISABLED.name, 'ldap': DSStatus.DISABLED.name}
        status = self.status()

        match status['type']:
            case DSType.AD.value:
                output[DSType.AD.value.lower()] = status['status']
            case DSType.LDAP.value | DSType.IPA.value:
                output[DSType.LDAP.value.lower()] = status['status']

        return output

    @accepts()
    @job(lock="directoryservices_refresh_cache", lock_queue_size=1)
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
        return await job.wrap(await self.middleware.call('directoryservices.cache.refresh_impl'))

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
        ds = DSType(dstype)
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
    @job()
    async def initialize(self, job, data=None):
        # retrieve status to force initialization of status
        if (await self.middleware.call('directoryservices.status'))['type'] is None:
            return

        try:
            await self.middleware.call('idmap.gencache.flush')
        except Exception:
            self.logger.warning('Cache flush failed', exc_info=True)

        await self.middleware.call('directoryservices.health.check')

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

        self.middleware.call_sync('service.restart', 'idmap')

        self.middleware.call_sync('directoryservices.health.check')
        if DSHealthObj.dstype is None:
            return

        job.set_progress(10, 'Refreshing cache'),
        cache_refresh = self.middleware.call_sync('directoryservices.cache.refresh')
        cache_refresh.wait_sync()

        job.set_progress(75, 'Restarting dependent services')
        self.restart_dependent_services()
        job.set_progress(100, 'Setup complete')


async def __init_directory_services(middleware, event_type, args):
    await middleware.call('directoryservices.setup')


async def setup(middleware):
    middleware.event_subscribe('system.ready', __init_directory_services)
    middleware.event_register('directoryservices.status', 'Sent on directory service state changes.')
