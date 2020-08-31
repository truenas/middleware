import os

from middlewared.common.attachment import FSAttachmentDelegate


class KubernetesFSAttachmentDelegate(FSAttachmentDelegate):
    name = 'kubernetes'
    title = 'Kubernetes'

    async def query(self, path, enabled, options=None):
        results = []

        k8s_config = await self.middleware.call('kubernetes.config')
        if not k8s_config['pool']:
            return results

        query_dataset = os.path.relpath(path, '/mnt')
        if query_dataset == k8s_config['dataset'] or query_dataset.startswith(f'{k8s_config["dataset"]}/'):
            results.append({'pool': k8s_config['dataset']})

        return results

    async def get_attachment_name(self, attachment):
        return attachment['pool']

    async def delete(self, attachments):
        await self.middleware.call('service.stop', 'kubernetes')

    async def toggle(self, attachments, enabled):
        action = 'start' if enabled else 'stop'
        try:
            await self.middleware.call(f'service.{action}', 'kubernetes')
        except Exception as e:
            self.middleware.logger.error('Unable to %r kubernetes: %s', action, e)

    async def stop(self, attachments):
        await self.middleware.call('service.stop', 'kubernetes')

    async def start(self, attachments):
        await self.middleware.call('service.start', 'kubernetes')


async def setup(middleware):
    await middleware.call('pool.dataset.register_attachment_delegate', KubernetesFSAttachmentDelegate(middleware))
