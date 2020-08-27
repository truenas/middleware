import asyncio

from .base import SimpleService


class KubernetesService(SimpleService):
    name = 'kubernetes'
    etc = ['k3s']
    systemd_unit = 'k3s'

    async def before_start(self):
        config = await self.middleware.call('kubernetes.config')
        await self.middleware.call('kubernetes.status_change', config, config)
        await self.middleware.call('kubernetes.validate_k8s_fs_setup')

    async def _start_linux(self):
        await self.middleware.call('service.start', 'docker')
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
        await self.middleware.call('service.stop', 'docker')
