import middlewared.sqlalchemy as sa

from middlewared.service import private, Service
from middlewared.service_exception import MatchNotFound

from .utils import get_sorted_backups


class KubernetesModel(sa.Model):
    __tablename__ = 'services_kubernetes'

    id = sa.Column(sa.Integer(), primary_key=True)
    pool = sa.Column(sa.String(255), default=None, nullable=True)


class K8stoDockerMigrationService(Service):

    class Config:
        namespace = 'k8s_to_docker'
        cli_namespace = 'k8s_to_docker'

    @private
    async def trigger_migration(self):
        try:
            k8s_pool = (await self.middleware.call('datastore.config', 'services.kubernetes'))['pool']
        except MatchNotFound:
            return
        if not k8s_pool:
            return

        # We would like to wait for interfaces like bridge to come up before we proceed with migration
        # because they are notorious and can take some time to actually come up and if they are the default
        # interface, then migration is bound to fail as catalog won't sync because of no network
        # connectivity and us not able to see if an app is available in newer catalog. If the default interface
        # is not up, then we will fail the migration here and early
        await self.middleware.call('docker.state.validate_interfaces')

        list_backup_job = await self.middleware.call('k8s_to_docker.list_backups', k8s_pool)
        await list_backup_job.wait()
        if list_backup_job.error or list_backup_job.result['error']:
            self.logger.error(
                'Failed to list backups for %r pool: %s', k8s_pool,
                list_backup_job.error or list_backup_job.result['error']
            )
            return

        if not list_backup_job.result['backups']:
            self.logger.debug('No backups found for %r pool', k8s_pool)
            await self.unset_kubernetes_pool()
            return

        # We will get latest backup now and execute it
        backups = get_sorted_backups(list_backup_job.result)
        if not backups:
            self.logger.debug('No backups found with releases which can be migrated for %r pool', k8s_pool)
            await self.unset_kubernetes_pool()
            return

        latest_backup = backups[-1]
        migrate_job = await self.middleware.call(
            'k8s_to_docker.migrate', k8s_pool, {'backup_name': latest_backup['name']}
        )
        await migrate_job.wait()
        if migrate_job.error:
            self.logger.error(
                'Failed to migrate %r backup for %r pool: %s', latest_backup['name'], k8s_pool, migrate_job.error
            )
            return

        await self.unset_kubernetes_pool()
        self.logger.debug('Successfully migrated %r backup for %r pool', latest_backup['name'], k8s_pool)

    @private
    async def unset_kubernetes_pool(self):
        config = await self.middleware.call('datastore.config', 'services.kubernetes')
        self.logger.debug('Unsetting kubernetes pool for %r', config['pool'])
        await self.middleware.call('datastore.update', 'services.kubernetes', config['id'], {'pool': None})


async def _event_system_ready(middleware, event_type, args):
    # we ignore the 'ready' event on an HA system since the failover event plugin
    # is responsible for starting this service
    if await middleware.call('failover.licensed'):
        return

    middleware.create_task(middleware.call('k8s_to_docker.trigger_migration'))


async def setup(middleware):
    middleware.event_subscribe('system.ready', _event_system_ready)
