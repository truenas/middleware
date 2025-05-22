import errno

from middlewared.api import api_method
from middlewared.api.current import DockerBackupToPoolArgs, DockerBackupToPoolResult
from middlewared.service import CallError, job, Service


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
    def backup_to_pool(self, job, target_pool):
        """
        Create a backup of existing apps on `target_pool`.

        This creates a backup of existing apps on the `target_pool` specified. If this is executed multiple times,
        in the next iteration it will incrementally backup the apps that have changed since the last backup.
        """
        docker_config = self.middleware.call_sync('docker.config')
        if docker_config['pool'] is None:
            raise CallError('Docker is not configured', errno=errno.EINVAL)

        # TODO: See how locking plays a role here
        if not self.middleware.call_sync('pool.query', [['name', '=', target_pool]]):
            raise CallError(f'{target_pool!r} pool does not exist', errno=errno.ENOENT)

        job.set_progress(10, 'Initial validation has been completed')
