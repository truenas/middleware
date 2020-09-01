import asyncio

from .base import SimpleService


class KubernetesService(SimpleService):
    name = 'kubernetes'
    etc = ['k3s']
    systemd_unit = 'k3s'

    async def before_start(self):
        await self.middleware.call('kubernetes.validate_k8s_fs_setup')
        await self.middleware.call('service.start', 'docker')
        await self._systemd_unit('cni-dhcp', 'start')

    async def after_start(self):
        asyncio.ensure_future(self.middleware.call('kubernetes.post_start'))

    async def before_stop(self):
        await self.middleware.call('k8s.node.add_taints', [{'key': 'ix-svc-stop', 'effect': 'NoExecute'}])
        await asyncio.sleep(10)

    async def after_stop(self):
        await self._systemd_unit('kube-router', 'stop')
        await self._systemd_unit('cni-dhcp', 'stop')
        await self.middleware.call('service.stop', 'docker')
