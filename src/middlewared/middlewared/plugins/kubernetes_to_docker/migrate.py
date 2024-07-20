from middlewared.schema import accepts, Dict, returns, Str
from middlewared.service import Service


class K8stoDockerMigrationService(Service):

    class Config:
        namespace = 'k8s_to_docker'
        cli_namespace = 'k8s_to_docker'

    @accepts(
        Str('kubernetes_pool'),
        Dict(
            'options',
            Str('backup_name'),
        )
    )
    @returns()
    def migrate(self, kubernetes_pool, options):
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
        pass
