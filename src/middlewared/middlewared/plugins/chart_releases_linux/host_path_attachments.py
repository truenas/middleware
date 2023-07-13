import os

from middlewared.common.attachment import FSAttachmentDelegate
from middlewared.service import private, Service


class ChartReleaseService(Service):

    class Config:
        namespace = 'chart.release'

    @private
    async def validate_host_source_path(self, path):
        # We just validate now that the path is not in a locked dataset
        paths = {
            'path': path,
        }
        real_path = await self.middleware.run_in_thread(os.path.realpath, path)
        if real_path != path:
            paths[f'path (real path of {path})'] = real_path

        for path_type, path_to_test in paths.items():
            if path_to_test.startswith('/mnt/'):
                if await self.middleware.call('pool.dataset.path_in_locked_datasets', path_to_test):
                    return f'Path {path_to_test!r} {path_type} is locked'


class ChartReleaseFSAttachmentDelegate(FSAttachmentDelegate):
    name = 'chart releases'
    title = 'Chart Releases'

    async def query(self, path, enabled, options=None):
        chart_releases_attached = []
        for release in await self.middleware.call('chart.release.query', [], {'extra': {'retrieve_resources': True}}):
            if not release['resources']['host_path_volumes'] or (
                release['status'] == 'STOPPED' if enabled else release['status'] != 'STOPPED'
            ):
                continue

            if await self.middleware.call('filesystem.is_child', release['resources']['host_path_volumes'], path):
                chart_releases_attached.append({
                    'id': release['name'],
                    'name': release['name'],
                })
        return chart_releases_attached

    async def delete(self, attachments):
        for attachment in attachments:
            try:
                job = await self.middleware.call('chart.release.scale', attachment['id'], {'replica_count': 0})
                await job.wait(raise_error=True)
            except Exception:
                self.middleware.logger.error('Unable to scale down %r chart release', attachment['id'], exc_info=True)

    async def toggle(self, attachments, enabled):
        # if enabled is true - we are going to ignore that as we don't want to scale up releases
        # automatically when a path becomes available
        for attachment in ([] if enabled else attachments):
            replica_count = 1 if enabled else 0
            await self.middleware.call('chart.release.scale', attachment['id'], {'replica_count': replica_count})
            try:
                job = await self.middleware.call(
                    'chart.release.scale', attachment['id'], {'replica_count': replica_count}
                )
                await job.wait(raise_error=True)
            except Exception:
                self.middleware.logger.error(
                    'Unable to set replica count of %r to %d', attachment['id'], replica_count, exc_info=True
                )

    async def stop(self, attachments):
        await self.toggle(attachments, False)

    async def start(self, attachments):
        await self.toggle(attachments, True)


async def setup(middleware):
    middleware.create_task(
        middleware.call('pool.dataset.register_attachment_delegate', ChartReleaseFSAttachmentDelegate(middleware))
    )
