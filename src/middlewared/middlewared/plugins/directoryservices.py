import struct

from base64 import b64decode
from middlewared.api import api_method, Event
from middlewared.api.current import (
    DirectoryServicesStatusArgs, DirectoryServicesStatusResult,
    DirectoryServicesCacheRefreshArgs, DirectoryServicesCacheRefreshResult,
    DirectoryServicesStatusChangedEvent,
)
from middlewared.plugins.directoryservices_.util_cache import check_cache_version
from middlewared.service import Service, private, job
from middlewared.service_exception import MatchNotFound
from middlewared.utils.directoryservices.health import DSHealthObj

PREREQUISITE_SERVICES = ('auth-rpcgss-module',)
DEPENDENT_SERVICES = ('smb', 'nfs', 'ssh', 'ftp')


class DirectoryServices(Service):
    class Config:
        service = "directoryservices"
        cli_namespace = "directory_service"
        datastore = "directoryservices"
        datastore_extend = "directoryservices.extend"
        role_prefix = "DIRECTORY_SERVICE"
        events = [
            Event(
                name='directoryservices.status',
                description='Sent on directory service state changes.',
                roles=['DIRECTORY_SERVICE_READ'],
                models={
                    'CHANGED': DirectoryServicesStatusChangedEvent,
                }
            )
        ]

    @api_method(
        DirectoryServicesStatusArgs, DirectoryServicesStatusResult,
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

    @private
    def get_state(self):
        """ LEGACY method to get directory services state. To be removed when UI
        stops using this. """
        output = {'activedirectory': 'DISABLED', 'ldap': 'DISABLED'}
        status = self.status()

        match status['type']:
            case 'ACTIVEDIRECTORY':
                output['activedirectory'] = status['status']
            case 'LDAP' | 'IPA':
                output['ldap'] = status['status']

        return output

    @api_method(
        DirectoryServicesCacheRefreshArgs, DirectoryServicesCacheRefreshResult,
        roles=['DIRECTORY_SERVICE_WRITE']
    )
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
        await job.wrap(await self.middleware.call('directoryservices.cache.refresh_impl', True))
        return

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
        server_secrets = db_secrets.get(f"{smb_config['netbiosname'].upper()}$")
        if server_secrets is None:
            return {"dbconfig": None, "secrets": passwd_ts}

        try:
            stored_ts_bytes = server_secrets[f'SECRETS/MACHINE_LAST_CHANGE_TIME/{domain.upper()}']
            stored_ts = struct.unpack("<L", b64decode(stored_ts_bytes))[0]
        except KeyError:
            stored_ts = None

        return {"dbconfig": stored_ts, "secrets": passwd_ts}

    @private
    def restart_dependent_services(self):
        # System services that should be started
        for svc in PREREQUISITE_SERVICES:
            self.middleware.call_sync('service.control', 'START', svc).wait_sync(raise_error=True)

        # Dependent protocols
        for svc in self.middleware.call_sync('service.query', [['OR', [
            ['enable', '=', True],
            ['state', '=', 'RUNNING']
        ]], ['service', 'in', DEPENDENT_SERVICES]]):
            self.middleware.call_sync('service.control', 'RESTART', svc['service']).wait_sync(raise_error=True)

    @private
    @job(lock='ds_init', lock_queue_size=1)
    def setup(self, job):
        """
        Set up directory services and NSS for the server. This handles NFS and SMB startup as well
        on the active storage controller
        """
        # ensure that samba is properly configured. This will block until networking is up
        config_job = self.middleware.call_sync('smb.configure')
        config_job.wait_sync(raise_error=True)

        # Recover is called here because it short-circuits if health check
        # shows we're healthy. If we can't recover due to things being irreparably
        # broken then this will raise an exception.
        self.middleware.call_sync('directoryservices.health.recover')

        # nsswitch.conf needs to be updated
        self.middleware.call_sync('etc.generate', 'nss')

        # The UI / API user cache isn't required for standby controller. This means we can avoid unnecessary
        # load on remote servers.
        if self.middleware.call_sync('failover.is_single_master_node'):
            job.set_progress(10, 'Refreshing cache')
            # NOTE: we're deliberately not specifying `force` here because we want to avoid
            # unnecessary cache rebuilds during HA failover events.

            if DSHealthObj.dstype is not None:
                cache_refresh = self.middleware.call_sync('directoryservices.cache.refresh_impl')
                cache_refresh.wait_sync()

            job.set_progress(75, 'Restarting dependent services')
            self.restart_dependent_services()

        job.set_progress(100, 'Setup complete')


async def __init_directory_services(middleware, event_type, args):
    await middleware.call('directoryservices.setup')


async def setup(middleware):
    middleware.event_subscribe('system.ready', __init_directory_services)

    truenas_version = await middleware.call('system.version_short')
    try:
        await middleware.run_in_thread(check_cache_version, truenas_version)
    except Exception:
        middleware.logger.warning('Failed to check directory services cache', exc_info=True)
