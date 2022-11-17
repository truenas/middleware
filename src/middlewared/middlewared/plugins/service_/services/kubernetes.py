import asyncio
import contextlib
import os
import re

from middlewared.plugins.kubernetes_linux.k8s.config import remove_initialized_config
from middlewared.service import CallError
from middlewared.utils import run

from .base import SimpleService


RE_TOKEN_FORMAT = re.compile(r'^K10.+:.+:.*')


class KubernetesService(SimpleService):
    name = 'kubernetes'
    etc = ['k3s']
    systemd_unit = 'k3s'
    kubelet_mountpoint = '/var/lib/kubelet'

    async def clear_chart_releases_cache(self):
        await self.middleware.call('chart.release.clear_cached_chart_releases')
        await self.middleware.call('chart.release.clear_portal_cache')

    async def unmount_kubelet_dataset(self):
        if os.path.ismount(self.kubelet_mountpoint):
            await run('umount', '-f', '-R', self.kubelet_mountpoint, check=True)

    async def mount_kubelet_dataset(self):
        config = await self.middleware.call('kubernetes.config')
        await self.unmount_kubelet_dataset()
        os.makedirs(self.kubelet_mountpoint, exist_ok=True)
        await run(
            'mount', '-t', 'zfs',
            os.path.join(config['dataset'], 'k3s/kubelet'),
            self.kubelet_mountpoint,
            check=True
        )

    async def before_start(self):
        try:
            await self.middleware.call('kubernetes.validate_k8s_fs_setup')
        except CallError as e:
            if e.errno != CallError.EDATASETISLOCKED:
                await self.middleware.call(
                    'alert.oneshot_create',
                    'ApplicationsConfigurationFailed',
                    {'error': e.errmsg},
                )
            else:
                await self.middleware.call('alert.oneshot_delete', 'ApplicationsConfigurationFailed', None)

            raise

        await self.mount_kubelet_dataset()
        await self.clear_chart_releases_cache()

        for key, value in (
            ('vm.panic_on_oom', 0),
            ('vm.overcommit_memory', 1),
        ):
            await self.middleware.call('sysctl.set_value', key, value)
        await self.middleware.call('service.start', 'docker')
        await self._systemd_unit('cni-dhcp', 'start')

        # It is possible server/token got misconfigured somehow ( we have had reports that on unclean shutdown the file
        # is empty or malformed, in this case we should remove the token as it's generated automatically by k3s again
        # and it's not useful to us as well per se as it's used for multi-node cluster )

        await self.middleware.run_in_thread(
            self.check_server_token, (await self.middleware.call('kubernetes.config'))['dataset']
        )

    def check_server_token(self, k8s_dataset):
        token_path = os.path.join('/mnt', k8s_dataset, 'k3s/server/token')
        with contextlib.suppress(FileNotFoundError):
            with open(token_path, 'r') as f:
                token = f.read().strip()

            if not RE_TOKEN_FORMAT.findall(token):
                os.unlink(token_path)

    async def start(self):
        await super().start()
        timeout = 40
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
        await self.clear_chart_releases_cache()
        await self.middleware.call('kubernetes.remove_iptables_rules')

    async def after_stop(self):
        await self._systemd_unit('kube-router', 'stop')
        await self._systemd_unit('cni-dhcp', 'stop')
        await self.middleware.call('service.stop', 'docker')
        # This is necessary to ensure that docker umounts datasets and shuts down cleanly
        await asyncio.sleep(5)
        await self.middleware.call('k8s.cni.cleanup_cni')
        await self.unmount_kubelet_dataset()
        remove_initialized_config()
