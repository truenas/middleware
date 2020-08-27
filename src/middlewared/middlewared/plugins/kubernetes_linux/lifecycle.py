import asyncio
import errno
import os

from middlewared.service import CallError, lock, private, Service


class KubernetesService(Service):

    @private
    async def post_start(self):
        # TODO: Add support for migrations
        await asyncio.sleep(5)
        await self.middleware.call('k8s.node.add_taints', [{'key': 'ix-svc-start', 'effect': 'NoExecute'}])
        node_config = await self.middleware.call('k8s.node.config')
        if not node_config['node_configured']:
            # TODO: Raise an alert
            raise CallError('Unable to configure node.')
        await self.middleware.call('k8s.cni.setup_cni')
        await self.middleware.call('service.start', 'kuberouter')
        await self.middleware.call(
            'k8s.node.remove_taints', [
                k['key'] for k in (node_config['spec']['taints'] or []) if k['key'] in ('ix-svc-start', 'ix-svc-stop')
            ]
        )

    @private
    async def validate_k8s_fs_setup(self):
        # TODO: Please account for locked datasets
        config = await self.middleware.call('kubernetes.config')
        if not await self.middleware.call('pool.query', [['name', '=', config['pool']]]):
            raise CallError(f'"{config["pool"]}" pool not found.', errno=errno.ENOENT)

        k8s_datasets = set(await self.kubernetes_datasets(config['dataset']))
        diff = {
            d['id'] for d in await self.middleware.call('pool.dataset.query', [['id', 'in', list(k8s_datasets)]])
        } ^ k8s_datasets
        if diff:
            raise CallError(f'Missing "{", ".join(diff)}" dataset(s) required for starting kubernetes.')

    @private
    @lock('kubernetes_status_change')
    async def status_change(self, config, old_config):
        k3s_running = await self.middleware.call('service.started', 'kubernetes')
        if config['pool'] and config['pool'] != old_config['pool']:
            await self.setup_pool()
            if not k3s_running:
                await self.middleware.call('service.start', 'docker')
                await asyncio.sleep(5)
                await self.middleware.call('docker.images.load_default_images')
                await self.middleware.call('service.stop', 'docker')
            else:
                asyncio.ensure_future(self.middleware.call('service.restart', 'kubernetes'))
        if not config['pool'] and k3s_running:
            asyncio.ensure_future(self.middleware.call('service.stop', 'kubernetes'))

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

    if args['id'] == 'ready' and (
        await middleware.call('service.query', [['service', '=', 'kubernetes']], {'get': True})
    )['enable']:
        asyncio.ensure_future(middleware.call('service.start', 'kubernetes'))
    elif args['id'] == 'shutdown' and await middleware.call('service.started', 'kubernetes'):
        asyncio.ensure_future(middleware.call('service.stop', 'kubernetes'))


async def setup(middleware):
    middleware.event_subscribe('system', _event_system)
