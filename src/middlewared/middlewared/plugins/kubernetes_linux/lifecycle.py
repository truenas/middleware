import asyncio
import errno
import json
import os

from middlewared.service import CallError, lock, private, Service


class KubernetesService(Service):

    @private
    async def post_start(self):
        # TODO: Add support for migrations
        await asyncio.sleep(10)
        # 10 secs should be enough for the node to come up online and kube-api servers to start accepting calls.
        try:
            await self.post_start_internal()
        except Exception:
            await self.middleware.call('alert.oneshot_create', 'ApplicationsStartFailed', None)
            raise
        else:
            await self.middleware.call('alert.oneshot_delete', 'ApplicationsStartFailed', None)

    @private
    async def post_start_internal(self):
        await self.middleware.call('k8s.node.add_taints', [{'key': 'ix-svc-start', 'effect': 'NoExecute'}])
        node_config = await self.middleware.call('k8s.node.config')
        if not node_config['node_configured']:
            raise CallError(f'Unable to configure node: {node_config["error"]}')
        await self.middleware.call('k8s.cni.setup_cni')
        await self.middleware.call(
            'k8s.node.remove_taints', [
                k['key'] for k in (node_config['spec']['taints'] or []) if k['key'] in ('ix-svc-start', 'ix-svc-stop')
            ]
        )

    @private
    async def validate_k8s_fs_setup(self):
        config = await self.middleware.call('kubernetes.config')
        if not await self.middleware.call('pool.query', [['name', '=', config['pool']]]):
            raise CallError(f'"{config["pool"]}" pool not found.', errno=errno.ENOENT)

        k8s_datasets = set(await self.kubernetes_datasets(config['dataset']))
        diff = {
            d['id'] for d in await self.middleware.call('pool.dataset.query', [['id', 'in', list(k8s_datasets)]])
        } ^ k8s_datasets
        if diff:
            raise CallError(f'Missing "{", ".join(diff)}" dataset(s) required for starting kubernetes.')

        locked_datasets = [
            d['id'] for d in await self.middleware.call('zfs.dataset.locked_datasets')
            if d['mountpoint'].startswith(f'{config["dataset"]}/') or d['mountpoint'] == config['dataset']
        ]
        if locked_datasets:
            raise CallError(
                f'Please unlock following dataset(s) before starting kubernetes: {", ".join(locked_datasets)}'
            )

    @private
    @lock('kubernetes_status_change')
    def status_change(self):
        config = self.middleware.call_sync('kubernetes.config')
        if self.middleware.call_sync('service.started', 'kubernetes'):
            self.middleware.call_sync('service.stop', 'kubernetes')

        if not config['pool']:
            return

        config_path = os.path.join('/mnt', config['dataset'], 'config.json')
        clean_start = True
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                on_disk_config = json.loads(f.read())
            clean_start = not all(
                config[k] == on_disk_config.get(k) for k in ('cluster_cidr', 'service_cidr', 'cluster_dns_ip')
            )

        if clean_start and self.middleware.call_sync('pool.dataset.query', [['id', '=', config['dataset']]]):
            self.middleware.call_sync('zfs.dataset.delete', config['dataset'], {'force': True, 'recursive': True})

        self.middleware.call_sync('kubernetes.setup_pool')
        try:
            self.middleware.call_sync('kubernetes.status_change_internal')
        except Exception:
            self.middleware.call_sync('alert.oneshot_create', 'ApplicationsConfigurationFailed', None)
            raise
        else:
            with open(config_path, 'w') as f:
                f.write(json.dumps(config))

            self.middleware.call_sync('alert.oneshot_delete', 'ApplicationsConfigurationFailed', None)

    @private
    async def status_change_internal(self):
        await self.validate_k8s_fs_setup()
        await self.middleware.call('service.start', 'docker')
        # This is necessary because docker daemon requires a couple of seconds after starting to initialise itself
        # properly, if we try to load images without the delay that will fail and will only correct after a restart
        await asyncio.sleep(5)
        await self.middleware.call('docker.images.load_default_images')
        asyncio.ensure_future(self.middleware.call('service.start', 'kubernetes'))

    @private
    async def setup_pool(self):
        config = await self.middleware.call('kubernetes.config')
        await self.create_update_k8s_datasets(config['dataset'])

    @private
    async def create_update_k8s_datasets(self, k8s_ds):
        for dataset in await self.kubernetes_datasets(k8s_ds):
            if not await self.middleware.call('pool.dataset.query', [['id', '=', dataset]]):
                await self.middleware.call('pool.dataset.create', {'name': dataset, 'type': 'FILESYSTEM'})

    @private
    async def kubernetes_datasets(self, k8s_ds):
        return [k8s_ds] + [os.path.join(k8s_ds, d) for d in ('docker', 'k3s', 'releases')]


async def _event_system(middleware, event_type, args):

    if args['id'] == 'ready' and (await middleware.call('kubernetes.config'))['pool']:
        asyncio.ensure_future(middleware.call('service.start', 'kubernetes'))
    elif args['id'] == 'shutdown' and await middleware.call('service.started', 'kubernetes'):
        asyncio.ensure_future(middleware.call('service.stop', 'kubernetes'))


async def setup(middleware):
    middleware.event_subscribe('system', _event_system)
