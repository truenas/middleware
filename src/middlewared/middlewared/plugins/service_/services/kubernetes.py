import asyncio
import errno
import os

from middlewared.service import CallError

from .base import SimpleService


class KubernetesService(SimpleService):
    name = 'kubernetes'
    etc = []
    systemd_unit = 'k3s'

    async def create_update_k8s_datasets(self, k8s_ds):
        for dataset in [k8s_ds] + [os.path.join(k8s_ds, d) for d in ('docker', 'k3s', 'releases')]:
            ds_data = await self.middleware.call('pool.dataset.query', [['id', '=', dataset]])
            if not ds_data:
                await self.middleware.call('pool.dataset.create', {'name': dataset, 'type': 'FILESYSTEM'})

    async def before_start(self):
        config = await self.middleware.call('kubernetes.config')
        await self.middleware.call('kubernetes.validate_k8s_fs_setup')
        await self.create_update_k8s_datasets(config['dataset'])
        await self.middleware.call('kubernetes.setup_cri')
        await self.middleware.call('etc.generate', 'k3s')

    async def _start_linux(self):
        await self._systemd_unit('docker', 'start')
        # FIXME: Please do this in a better way
        #  For now if the images have been imported already, it will take on average 1 second to complete
        await self.middleware.call(
            'docker.images.load_images_from_file', '/usr/local/share/docker_images/docker-images.tar'
        )
        await self._systemd_unit('cni-dhcp', 'start')
        await self._unit_action('Start')

    async def after_start(self):
        asyncio.ensure_future(self.middleware.call('kubernetes.post_start'))

    async def before_stop(self):
        # TODO: Drain the node so that it starts evicting pods
        pass

    async def _stop_linux(self):
        await self._unit_action('Stop')
        await self._systemd_unit('cni-dhcp', 'stop')
        await self._systemd_unit('docker', 'stop')
