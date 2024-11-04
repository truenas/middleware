import enum
import struct

from base64 import b64decode
from middlewared.api import api_method
from middlewared.api.current import (
    DirectoryServicesEntry,
    DirectoryServicesUpdateArgs, DirectoryServicesUpdateResult,
    DirectoryServicesStatusArgs, DirectoryServicesStatusResult,
    DirectoryServicesGetStateArgs, DirectoryServicesGetStateResult,
)
from middlewared.schema import accepts, List, OROperator, returns, Str
from middlewared.service import ConfigService, private, job
from middlewared.service_exception import CallError, MatchNotFound
from middlewared.utils.directoryservices.constants import (
    DomainJoinResponse, DSStatus, DSType, NSS_Info
)
from middlewared.utils.directoryservices.krb5_constants import krb5ccache
from middlewared.utils.directoryservices.health import DSHealthObj

DEPENDENT_SHARING_SERVICES = frozenset(['smb', 'nfs', 'ftp'])
DEPENDENT_SERVICES = frozenset(['ssh']) | DEPENDENT_SHARING_SERVICES


class SSL(enum.Enum):
    NOSSL = 'OFF'
    USESSL = 'ON'
    USESTARTTLS = 'START_TLS'


class SASL_Wrapping(enum.Enum):
    PLAIN = 'PLAIN'
    SIGN = 'SIGN'
    SEAL = 'SEAL'


class DirectoryServices(ConfigService):
    class Config:
        service = 'directoryservices'
        datastore = 'directoryservice_configuration'
        datastore_extend = 'directoryservices.extend'
        cli_namespace = 'directory_service'
        entry = DirectoryServicesEntry
        role_prefix = 'DIRECTORY_SERVICE'

    @api_method(
        DirectoryServicesUpdateArgs, DirectoryServicesUpdateResult,
    )
    @job(lock='directoryservices.update')
    async def update(self, job, data):
        old = await self.config()
        new = await self.middleware.call('directoryservices.validate_and_clean', old, data)
        ds = DSType(new['dstype'])

        if ds is DSType.STANDALONE:
            # Nothing to change if we're standalone.
            return await self.config()

        if not old['enable'] and new['enable']:
            # START directory services
            resp = await self.middleware.call('directoryservices.connection.is_joined')
            if resp == DomainJoinResponse.NOT_JOINED:
                # We're not joined to the directory service and so we need to perform join

                # Only IPA and AD will respond with NOT_JOINED
                assert ds in (DSType.AD, DSType.IPA), 'Unexpected DSType'

                await self.middleware.call('directoryservices.health.set_state', ds, DSStatus.JOINING)
                join = await self.middleware.call(
                    'directoryservices.connection.join', ds, new['configuration']['domainname'],
                )

                try:
                    resp = await job.wrap(join)
                except Exception:
                    self.logger.warning('Failed to join domain. Disabling service.', exc_info=True)
                    await self.middleware.call('datastore.update', 'directoryservices.configuraiton', new['id'], {
                        'common_enable': False
                    })
                    raise

            # By this point we should be joined to domain and just need to activate connection fully.
            cache_job_id = await self.middleware.call('directoryservices.connection.activate')
            try:
                # Cache fill should be non-fatal, but we want to update watcher on progress
                await job.wrap(cache_job_id)
            except Exception:
                self.logger.warning('Failed to fill directory services cache', exc_info=True)

            if resp == DomainJoinResponse.PERFORMED_JOIN:
                try:
                    await self.middleware.call(
                        'directoryservices.connection.grant_privileges',
                        ds, new['configuration']['domainname'],
                    )
                except Exception:
                    # This should be non-fatal error
                    self.logger.warning(
                        'Failed to grant privileges to domain admin group. '
                        'Further administrative action may be required in order '
                        'to use TrueNAS RBAC with directory services groups.',
                        exc_info=True
                    )

            # Change state to HEALTHY before performing final health check
            await self.middleware.call('directoryservices.health.set_state', ds, DSStatus.HEALTHY)

            # Force health check so that user gets immediate feedback if something
            # went sideways while enabling
            await self.middleware.call('directoryservices.health.check')
            await self.middleware.call('directoryservices.restart_dependent_services')

        elif not new['enable'] and old['enable']:
            # STOP directory services
            await self.middleware.call('directoryservices.health.set_state', ds, DSStatus.DISABLED)
            to_start = []

            # stop sharing services that depend on DS
            for service in DEPENDENT_SHARING_SERVICES:
                if await self.middleware.call('service.started', service):
                    await self.middleware.call('service.stop', service)
                    to_start.append(service)

            ds = DSType(new['dstype'])
            await self.middleware.call('service.stop', ds.middleware_service)

            for etc_file in ds.etc_files:
                await self.middleware.call('etc.generate', etc_file)

            # clear any kerberos tickets
            if await self.middleware.call('kerberos.check_ticket', {'ccache': krb5ccache.SYSTEM.name}, False):
                await self.middleware.call('kerberos.kdestroy')

            await self.middleware.call('directoryservices.cache.abort_refresh')

            # toggle ssh if required
            if await self.middleware.call('service.started', 'ssh'):
                await self.middleware.call('service.restart', 'ssh')

            # start any services we stopped
            for service in to_start:
                await self.middleware.call('service.start', service)

        elif new['enable'] and old['enable']:
            # RESTART directory services
            await self.middleware.call('service.restart', ds.middleware_service)

        return await self.config()

    @api_method(
        DirectoryServicesStatusArgs,
        DirectoryServicesStatusResult,
        authorization_required=False
    )
    def status(self):
        """
        Provide the type and status of the currently-enabled directory service
        """
        if not DSHealthObj.initialized:
            try:
                self.middleware.call_sync('directoryservices.health.check')
            except Exception:
                pass

        return DSHealthObj.dump()

    @api_method(
        DirectoryServicesGetStateArgs,
        DirectoryServicesGetStateResult,
        authorization_required=False
    )
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

        # Recover is called here because it short-circuits if health check
        # shows we're healthy. If we can't recover due to things being irreparably
        # broken then this will raise an exception.
        self.middleware.call_sync('directoryservices.health.recover')
        if DSHealthObj.dstype is None:
            return

        # nsswitch.conf needs to be updated
        self.middleware.call_sync('etc.generate', 'nss')
        job.set_progress(10, 'Refreshing cache'),
        cache_refresh = self.middleware.call_sync('directoryservices.cache.refresh_impl')
        cache_refresh.wait_sync()

        job.set_progress(75, 'Restarting dependent services')
        self.restart_dependent_services()
        job.set_progress(100, 'Setup complete')


async def __init_directory_services(middleware, event_type, args):
    await middleware.call('directoryservices.setup')


async def setup(middleware):
    middleware.event_subscribe('system.ready', __init_directory_services)
    middleware.event_register('directoryservices.status', 'Sent on directory service state changes.')
