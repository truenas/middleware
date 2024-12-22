from middlewared.api import api_method
from middlewared.api.current import DockerUpdateArgs, DockerBackupResult
from middlewared.service import CallError, private, Service


class DockerService(Service):

    class Config:
        cli_namespace = 'app.docker'

    @api_method(DockerUpdateArgs, DockerBackupResult, roles=['DOCKER_WRITE'])
    def backup(self, backup_name):
        """
        Create a backup of existing apps.
        """
        self.middleware.call_sync('docker.state.validate')
