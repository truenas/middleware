import contextlib

from middlewared.plugins.docker.utils import applications_ds_name
from middlewared.schema import accepts, Dict, returns, Str
from middlewared.service import CallError, InstanceNotFound, job, Service

from .migrate_config_utils import migrate_chart_release_config


class K8stoDockerMigrationService(Service):

    class Config:
        namespace = 'k8s_to_docker'
        cli_namespace = 'k8s_to_docker'

    @accepts(
        Str('kubernetes_pool'),
        Dict(
            'options',
            Str('backup_name', required=True, empty=False),
        )
    )
    @returns()
    @job(lock='k8s_to_docker_migrate')
    def migrate(self, job, kubernetes_pool, options):
        """
        Migrate kubernetes backups to docker.
        """
        # The workflow for the migration would be
        # 1) Ensuring the specified backup exists
        # 2) Map apps which are supported atm and will actually reflect in the UI
        # 3) Setup filesystem appropriately for docker
        # 4) Migrate the config of apps
        # 5) Create relevant filesystem bits for apps and handle cases like ix-volumes
        # 6) Redeploy apps
        backup_config_job = self.middleware.call_sync('k8s_to_docker.list_backups', kubernetes_pool)
        backup_config_job.wait_sync()
        if backup_config_job.error:
            raise CallError(f'Failed to list backups: {backup_config_job.error}')

        backups = backup_config_job.result
        if backups['error']:
            raise CallError(f'Failed to list backups for {kubernetes_pool!r}: {backups["error"]}')

        if options['backup_name'] not in backups['backups']:
            raise CallError(f'Backup {options["backup_name"]} not found')

        backup_config = backups['backups'][options['backup_name']]
        job.set_progress(10, f'Located {options["backup_name"]} backup')

        if not backup_config['releases']:
            raise CallError(f'No old apps found in {options["backup_name"]!r} backup which can be migrated')

        # We will see if docker dataset exists on this pool and if it is there, we will error out
        docker_ds = applications_ds_name(kubernetes_pool)
        with contextlib.suppress(InstanceNotFound):
            self.middleware.call_sync('pool.dataset.get_instance_quick', docker_ds)
            raise CallError(f'Docker dataset {docker_ds!r} already exists on {kubernetes_pool!r}')

        # For good measure we stop docker service and unset docker pool if any configured
        self.middleware.call_sync('service.stop', 'docker')
        job.set_progress(15, 'Un-configuring docker service if configured')
        docker_job = self.middleware.call_sync('docker.update', {'pool': None})
        docker_job.wait_sync()
        if docker_job.error:
            raise CallError(f'Failed to un-configure docker: {docker_job.error}')

        # We will now configure docker service
        docker_job = self.middleware.call_sync('docker.update', {'pool': kubernetes_pool})
        docker_job.wait_sync()
        if docker_job.error:
            raise CallError(f'Failed to configure docker: {docker_job.error}')

        job.set_progress(25, f'Rolling back to {backup_config["snapshot_name"]!r} snapshot')
        self.middleware.call_sync(
            'zfs.snapshot.rollback', backup_config['snapshot_name'], {
                'force': True,
                'recursive': True,
                'recursive_clones': True,
                'recursive_rollback': True,
            }
        )
        job.set_progress(30, 'Starting migrating old apps to new apps')

        # FIXME: Update job progress on each chart release
        # We will now iterate over each chart release which can be migrated and try to migrate it's config
        # If we are able to migrate it's config, we will proceed with setting up relevant filesystem bits
        # for the app and finally redeploy it
        release_details = []
        for chart_release in backup_config['releases']:
            new_config = migrate_chart_release_config(chart_release)
            if isinstance(new_config, str) or not new_config:
                release_details.append({
                    'name': chart_release['name'],
                    'error': new_config,
                })
                continue
