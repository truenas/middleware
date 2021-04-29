import asyncio

from .base import SimpleService


class KubernetesService(SimpleService):
    name = 'kubernetes'
    etc = ['k3s']
    systemd_unit = 'k3s'

    async def before_start(self):
        await self.middleware.call('kubernetes.validate_k8s_fs_setup')
        for key, value in (
            ('vm.panic_on_oom', 0),
            ('vm.overcommit_memory', 1),
            ('kernel.panic', 10),
            ('kernel.panic_on_oops', 1),
        ):
            await self.middleware.call('sysctl.set_value', key, value)
        await self.middleware.call('service.start', 'docker')
        await self._systemd_unit('cni-dhcp', 'start')

    async def _start_linux(self):
        await super()._start_linux()
        timeout = 20
        # First time when k8s is started, it takes a bit more time to initialise itself properly
        # and we need to have sleep here so that after start is called post_start is not dismissed
        while timeout > 0:
            if not await self.middleware.call('service.started', 'kubernetes'):
                await asyncio.sleep(2)
                timeout -= 2
            else:
                break

    async def after_start(self):
        asyncio.ensure_future(self.middleware.call('kubernetes.post_start'))

    async def before_stop(self):
        await self.middleware.call('k8s.node.add_taints', [{'key': 'ix-svc-stop', 'effect': 'NoExecute'}])
        await asyncio.sleep(10)

    async def after_stop(self):
        await self._systemd_unit('kube-router', 'stop')
        await self._systemd_unit('cni-dhcp', 'stop')
        await self.middleware.call('service.stop', 'docker')
        # This is necessary to ensure that docker umounts datasets and shuts down cleanly
        await asyncio.sleep(5)
        await self.middleware.call('k8s.cni.cleanup_cni')
        await self.middleware.call('kubernetes.remove_iptables_rules')
