import asyncio
from itertools import groupby

from middlewared.api import api_method
from middlewared.api.current import PoolDatasetAttachmentsArgs, PoolDatasetAttachmentsResult
from middlewared.service import private, Service

from .utils import dataset_mountpoint


class PoolDatasetService(Service):

    attachment_delegates = []

    class Config:
        namespace = 'pool.dataset'

    @api_method(PoolDatasetAttachmentsArgs, PoolDatasetAttachmentsResult, roles=['DATASET_READ'])
    async def attachments(self, oid):
        """
        Return a list of services dependent of this dataset.

        Responsible for telling the user whether there is a related
        share, asking for confirmation.

        Example return value:
        [
          {
            "type": "NFS Share",
            "service": "nfs",
            "attachments": ["/mnt/tank/work"]
          }
        ]
        """
        dataset = await self.middleware.call('pool.dataset.get_instance_quick', oid)
        if mountpoint := dataset_mountpoint(dataset):
            return await self.attachments_with_path(mountpoint)
        return []

    @private
    async def attachments_with_path(self, path, check_parent=False, exact_match=False):
        result = []
        if isinstance(path, str) and not path.startswith('/mnt/'):
            self.logger.warning('%s: unexpected path not located within pool mountpoint', path)

        if path:
            options = {'check_parent': check_parent, 'exact_match': exact_match}
            for delegate in self.attachment_delegates:
                attachments = {'type': delegate.title, 'service': delegate.service, 'attachments': []}
                for attachment in await delegate.query(path, True, options):
                    attachments['attachments'].append(await delegate.get_attachment_name(attachment))
                if attachments['attachments']:
                    result.append(attachments)
        return result

    @private
    def register_attachment_delegate(self, delegate):
        self.attachment_delegates.append(delegate)

    @private
    async def query_attachment_delegate(self, name, path, enabled):
        for delegate in self.attachment_delegates:
            if delegate.name == name:
                return await delegate.query(path, enabled)

        raise RuntimeError(f'Unknown attachment delegate {name!r}')

    @private
    async def get_attachment_delegates(self):
        return self.attachment_delegates

    @private
    async def get_attachment_delegates_for_start(self):
        """
        Returns delegates sorted for start operations.
        Higher priority delegates (infrastructure) run first.
        """
        return sorted(self.attachment_delegates, key=lambda d: d.priority, reverse=True)

    @private
    async def get_attachment_delegates_for_stop(self):
        """
        Returns delegates sorted for stop operations.
        Lower priority delegates (dependent services) run first.
        """
        return sorted(self.attachment_delegates, key=lambda d: d.priority)

    @private
    async def stop_attachment_delegates(self, path):
        """
        Stop attachment delegates in priority order.
        Delegates with the same priority run in parallel, but different priority
        groups run sequentially (lower priority first).
        """
        if not path:
            return

        delegates = await self.get_attachment_delegates_for_stop()
        for _, group in groupby(delegates, key=lambda d: d.priority):
            group_list = list(group)

            async def stop_delegate(delegate):
                if attachments := await delegate.query(path, True):
                    await delegate.stop(attachments)

            await asyncio.gather(*[stop_delegate(dg) for dg in group_list])
