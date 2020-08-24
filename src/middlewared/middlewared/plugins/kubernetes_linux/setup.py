import errno
import os

from middlewared.service import CallError, private, Service


class KubernetesService(Service):

    @private
    async def create_update_k8s_datasets(self, k8s_ds):
        for dataset in [k8s_ds] + [os.path.join(k8s_ds, d) for d in ('docker', 'k3s', 'releases')]:
            ds_data = await self.middleware.call('pool.dataset.query', [['id', '=', dataset]])
            if not ds_data:
                await self.middleware.call('pool.dataset.create', {'name': dataset, 'type': 'FILESYSTEM'})

    @private
    def setup(self):
        """
        # TODO: Please account for locked datasets
        We will be going along the following steps to setup k3s cluster:
        1) Ensure specified pool is configured
        2) Create / update ix-applications dataset
        3) Setup CRI
        4)
        """
        config = self.middleware.call_sync('kubernetes.config')
        if not await self.middleware.call_sync('pool.query', [['name', '=', config['pool']]]):
            raise CallError(f'"{config["pool"]}" pool not found.', errno=errno.ENOENT)

        self.middleware.call_sync('kubernetes.create_update_k8s_datasets')

        self.middleware.call_sync('etc.generate', 'docker')
