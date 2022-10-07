import os

from middlewared.common.attachment import FSAttachmentDelegate
from middlewared.common.ports import ServicePortDelegate


class KubernetesFSAttachmentDelegate(FSAttachmentDelegate):
    name = 'kubernetes'
    title = 'Kubernetes'
    service = 'kubernetes'

    async def query(self, path, enabled, options=None):
        results = []

        k8s_config = await self.middleware.call('kubernetes.config')
        if not k8s_config['pool']:
            return results

        query_dataset = os.path.relpath(path, '/mnt')
        if query_dataset in (k8s_config['dataset'], k8s_config['pool']) or query_dataset.startswith(
            f'{k8s_config["dataset"]}/'
        ):
            results.append({'id': k8s_config['pool']})

        return results

    async def get_attachment_name(self, attachment):
        return attachment['id']

    async def delete(self, attachments):
        if attachments:
            await (await self.middleware.call('kubernetes.update', {'pool': None})).wait(raise_error=True)

    async def toggle(self, attachments, enabled):
        await getattr(self, 'start' if enabled else 'stop')(attachments)

    async def stop(self, attachments):
        if not attachments:
            return
        try:
            await self.middleware.call('service.stop', 'kubernetes')
        except Exception as e:
            self.middleware.logger.error('Failed to stop kubernetes: %s', e)

    async def start(self, attachments):
        if not attachments:
            return
        try:
            await self.middleware.call('service.start', 'kubernetes')
        except Exception:
            self.middleware.logger.error('Failed to start kubernetes')


class KubernetesServicePortDelegate(ServicePortDelegate):

    name = 'apps'
    namespace = 'kubernetes'
    title = 'Kubernetes Service'

    async def get_ports_internal(self):
        return [6443]


async def setup(middleware):
    await middleware.call('pool.dataset.register_attachment_delegate', KubernetesFSAttachmentDelegate(middleware))
    await middleware.call('port.register_attachment_delegate', KubernetesServicePortDelegate(middleware))
