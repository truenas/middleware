import asyncio

from .base import SimpleService


class KubernetesService(SimpleService):
    name = 'kubernetes'
    etc = ['k3s']
    systemd_unit = 'k3s'

    async def _start_linux(self):
        await self.middleware.call('service.start', 'docker')
        await self._systemd_unit('cni-dhcp', 'start')
        await self._unit_action('Start')

    async def after_start(self):
        asyncio.ensure_future(self.middleware.call('kubernetes.post_start'))

    async def before_stop(self):
        await self.middleware.call('k8s.node.add_taints', [{'key': 'ix-svc-stop', 'effect': 'NoExecute'}])
        await asyncio.sleep(10)

    async def _stop_linux(self):
        await self._systemd_unit('kube-router', 'stop')
        await self._unit_action('Stop')
        await self._systemd_unit('cni-dhcp', 'stop')
        await self.middleware.call('service.stop', 'docker')
