from middlewared.schema import accepts, Dict, returns, Str
from middlewared.service import Service

from .utils import get_k8s_ds


class K8stoDockerMigrationService(Service):

    class Config:
        namespace = 'k8s_to_docker'

    @accepts(Str('kubernetes_pool'))
    @returns(Dict('backups', additional_attrs=True))
    def list_backups(self, kubernetes_pool):
        """
        List existing kubernetes backups
        """
        backup_config = {
            'error': None,
            'backups': {},
        }
        k8s_ds = get_k8s_ds(kubernetes_pool)
        if not self.middleware.call_sync('pool.dataset.query', [['id', '=', k8s_ds]]):
            return backup_config | {'error': f'Unable to locate {k8s_ds!r} dataset'}

        return backup_config
