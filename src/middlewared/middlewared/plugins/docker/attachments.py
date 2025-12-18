import os

from middlewared.common.attachment import FSAttachmentDelegate


class DockerFSAttachmentDelegate(FSAttachmentDelegate):
    name = 'docker'
    title = 'Docker'
    service = 'docker'
    # Docker must start before apps, and stop after apps
    priority = 10

    async def query(self, path, enabled, options=None):
        results = []

        k8s_config = await self.middleware.call('docker.config')
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
            await (await self.middleware.call('docker.update', {'pool': None})).wait(raise_error=True)

    async def toggle(self, attachments, enabled):
        await getattr(self, 'start' if enabled else 'stop')(attachments)

    async def stop(self, attachments):
        if not attachments:
            return
        try:
            await (await self.middleware.call('service.control', 'STOP', self.service)).wait(raise_error=True)
        except Exception as e:
            self.middleware.logger.error('Failed to stop docker: %s', e)

    async def start(self, attachments):
        if not attachments:
            return
        try:
            await self.middleware.call('docker.state.start_service', True)
        except Exception:
            self.middleware.logger.error('Failed to start docker')


async def setup(middleware):
    await middleware.call('pool.dataset.register_attachment_delegate', DockerFSAttachmentDelegate(middleware))
