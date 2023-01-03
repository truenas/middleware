import os

from middlewared.common.attachment import FSAttachmentDelegate
from middlewared.service import private, Service

from .utils import is_ix_volume_path, safe_to_ignore_path


class ChartReleaseService(Service):

    class Config:
        namespace = 'chart.release'

    @private
    async def ix_mount_validation(self, path, path_type):
        path_list = [p for p in path.split('/') if p.strip()]
        if safe_to_ignore_path(path):
            if path_list and len(path_list) < 3 and path_list[0] == 'mnt':
                return f'Invalid path {path}. Mounting root dataset or path outside a pool is not allowed'
        else:
            return f'{path!r} {path_type!r} not allowed to be mounted'

    @private
    async def attached_path_validation(self, path, path_type):
        allowed_service_types = {
            'Chart Releases',
            'Rsync Task',
            'Snapshot Task',
            'Rsync Module',
            'CloudSync Task',
            'Replication',
        }
        in_use_attachments = []
        for attachment_entry in filter(
            lambda attachment: attachment['type'] not in allowed_service_types,
            await self.middleware.call('pool.dataset.attachments_with_path', path)
        ):
            if attachment_entry['service'] == 'Kubernetes' and is_ix_volume_path(
                path, (await self.middleware.call('kubernetes.config'))['dataset']
            ):
                continue

            in_use_attachments.append(attachment_entry)

        if in_use_attachments:
            return f'Invalid mount {path!r} {path_type}. Following service(s) use this ' \
                   f'path: {", ".join(attachment["type"] for attachment in in_use_attachments)}'

    @private
    async def validate_host_source_path(self, path):
        paths = {
            'path': path,
        }
        real_path = await self.middleware.run_in_thread(os.path.realpath, path)
        if real_path != path:
            paths[f'path (real path of {path})'] = real_path

        for path_type, path_to_test in paths.items():
            if err := await self.ix_mount_validation(path_to_test, path_type):
                return err

            if path_to_test.startswith('/mnt/'):
                if await self.middleware.call('pool.dataset.path_in_locked_datasets', path_to_test):
                    return f'Path {path_to_test!r} {path_type} is locked'
                if err := await self.attached_path_validation(path_to_test, path_type):
                    return err


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
