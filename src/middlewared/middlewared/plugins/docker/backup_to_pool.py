from middlewared.api import api_method
from middlewared.api.current import DockerBackupToPoolArgs, DockerBackupToPoolResult
from middlewared.service import job, private, Service, ValidationErrors

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
        elif target_root_ds[0]['encrypted']:
            # This is not allowed because destination root if encrypted means that docker datasets would be
            # not encrypted and by design we don't allow this to happen to keep it simple / straight forward.
            # https://github.com/truenas/zettarepl/blob/52d3b7a00fa4630c3428ae4e70bc33cf41a6d768/zettarepl/
            # replication/run.py#L319
            verrors.add('target_pool', f'Backup to an encrypted pool {target_pool!r} is not allowed')

        verrors.check()

        job.set_progress(10, 'Initial validation has been completed, stopping docker service')
        await self.middleware.call('service.stop', 'docker')
        job.set_progress(30, 'Snapshotting apps dataset')
        schema = f'ix-apps-{docker_config["pool"]}-to-{target_pool}-backup-%Y-%m-%d_%H-%M-%S'
        await self.middleware.call(
            'zfs.snapshot.create', {
                'dataset': applications_ds_name(docker_config["pool"]),
                'naming_schema': schema,
                'recursive': True,
            }
        )
        await self.middleware.call('service.start', 'docker')
        job.set_progress(45, 'Incrementally replicating apps dataset')

        try:
            await self.incrementally_replicate_apps_dataset(docker_config['pool'], target_pool, schema)
        except Exception:
            job.set_progress(90, 'Failed to incrementally replicate apps dataset')
            raise
        else:
            job.set_progress(100, 'Successfully incrementally replicated apps dataset')

    @private
    async def incrementally_replicate_apps_dataset(self, source_pool, target_pool, schema):
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
                'mount': False,
            }
        )
        await replication_job.wait(raise_error=True)
