import errno

from middlewared.api import api_method
from middlewared.api.current import DockerBackupToPoolArgs, DockerBackupToPoolResult
from middlewared.service import CallError, job, private, Service, ValidationErrors

from .utils import applications_ds_name


class DockerService(Service):

    class Config:
        cli_namespace = 'app.docker'

    @api_method(
        DockerBackupToPoolArgs, DockerBackupToPoolResult,
        audit='Docker: Backup to pool',
        audit_extended=lambda target_pool: target_pool,
        roles=['DOCKER_WRITE']
    )
    @job(lock='docker_backup_to_pool')
    async def backup_to_pool(self, job, target_pool):
        """
        Create a backup of existing apps on `target_pool`.

        This creates a backup of existing apps on the `target_pool` specified. If this is executed multiple times,
        in the next iteration it will incrementally backup the apps that have changed since the last backup.
        """
        verrors = ValidationErrors()
        docker_config = await self.middleware.call('docker.config')
        if docker_config['pool'] is None:
            verrors.add('pool', 'Docker is not configured to use a pool')

        if target_pool == docker_config['pool']:
            verrors.add('target_pool', 'Target pool cannot be the same as the current Docker pool')

        target_root_ds = await self.middleware.call('pool.dataset.query', [['id', '=', target_pool]], {
            'extra': {
                'retrieve_children': False,
                'properties': ['encryption', 'keystatus', 'mountpoint', 'keyformat', 'encryptionroot'],
            }
        })
        if not target_root_ds:
            verrors.add('target_pool', 'Target pool does not exist')

        # FIXME: See if we want to allow replicating to encrypted pool

        verrors.check()
        # TODO: See how locking plays a role here
        if not await self.middleware.call('pool.query', [['name', '=', target_pool]]):
            raise CallError(f'{target_pool!r} pool does not exist', errno=errno.ENOENT)

        job.set_progress(10, 'Initial validation has been completed')
        await self.middleware.call('service.stop', 'docker')
        job.set_progress(20, 'Docker service has been stopped')

        try:
            await self.incrementally_replicate_apps_dataset(docker_config['pool'], target_pool)
        finally:
            self.middleware.call_sync('service.start', 'docker')

    @private
    async def incrementally_replicate_apps_dataset(self, source_pool, target_pool):
        schema = f'ix-apps-{source_pool}-backup-%Y-%m-%d_%H-%M'
        await self.middleware.call(
            'zfs.snapshot.create', {
                'dataset': applications_ds_name(source_pool),
                'naming_schema': schema,
                'recursive': True,
            }
        )
        old_ds = applications_ds_name(source_pool)
        new_ds = applications_ds_name(target_pool)
        replication_job = await self.middleware.call(
            'replication.run_onetime', {
                'direction': 'PUSH',
                'transport': 'LOCAL',
                'source_datasets': [old_ds],
                'target_dataset': new_ds,
                'recursive': True,
                'also_include_naming_schema': [schema],
                'retention_policy': 'SOURCE',
                'replicate': True,
                'readonly': 'IGNORE',
                'exclude_mountpoint_property': False,
            }
        )
        await replication_job.wait()
        if replication_job.error:
            raise CallError(f'Failed to replicate {old_ds} to {new_ds}: {replication_job.error}')
