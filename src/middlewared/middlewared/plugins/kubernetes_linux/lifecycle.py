import asyncio
import errno

from middlewared.service import CallError, private, Service


class KubernetesService(Service):

    @private
    async def post_start(self):
        # TODO: Add support for migrations
        await self.middleware.call(
            'k8s.node.add_taints', [{'key': 'ix-taint', 'effect': e} for e in ('NoSchedule', 'NoExecute')]
        )
        await self.middleware.call('k8s.cni.setup_cni')
        await self.middleware.call('k8s.node.remove_taints', ['ix-taint'])

    @private
    async def setup_cri(self):
        await self.middleware.call('etc.generate', 'docker')

    @private
    async def validate_k8s_fs_setup(self):
        # TODO: Please account for locked datasets
        config = await self.middleware.call('kubernetes.config')
        if not await self.middleware.call('pool.query', [['name', '=', config['pool']]]):
            raise CallError(f'"{config["pool"]}" pool not found.', errno=errno.ENOENT)


async def _event_system(middleware, event_type, args):

    if args['id'] == 'ready' and (
        await middleware.call('service.query', [['service', '=', 'kubernetes']], {'get': True})
    )['enable']:
        asyncio.ensure_future(middleware.call('service.start', 'kubernetes'))
    elif args['id'] == 'shutdown' and await middleware.call('service.started', 'kubernetes'):
        asyncio.ensure_future(middleware.call('service.stop', 'kubernetes'))


async def setup(middleware):
    middleware.event_subscribe('system', _event_system)
