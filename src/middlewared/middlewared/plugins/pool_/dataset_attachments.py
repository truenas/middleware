import asyncio
from itertools import groupby
from typing import TYPE_CHECKING

from middlewared.api import api_method
from middlewared.api.current import PoolAttachment, PoolDatasetAttachmentsArgs, PoolDatasetAttachmentsResult
from middlewared.service import private, Service
if TYPE_CHECKING:
    from middlewared.common.attachment import FSAttachmentDelegate

from .utils import dataset_mountpoint


class PoolDatasetService(Service):

    attachment_delegates: list['FSAttachmentDelegate'] = []

    class Config:
        namespace = 'pool.dataset'
        cli_namespace = 'storage.dataset'

    @api_method(
        PoolDatasetAttachmentsArgs,
        PoolDatasetAttachmentsResult,
        roles=['DATASET_READ'],
        check_annotations=True,
    )
    async def attachments(self, oid: str) -> list[PoolAttachment]:
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
    async def attachments_with_path(
        self, path: str, check_parent: bool = False, exact_match: bool = False
    ) -> list[PoolAttachment]:
        """
        Query all registered attachment delegates to find services, shares, and tasks that depend on a given path.

        This method is the core of the attachment system, discovering what will be affected if a dataset at
        the specified path becomes unavailable (due to deletion, export, locking, etc.).

        Called by:
        - `pool.dataset.attachments()` - Public API method for querying dataset dependencies
        - `pool.info()` - When displaying pool-level attachment information
        - Internal pool operations - Before destructive operations to warn users or prevent conflicts

        Args:
            path (str): Filesystem path to check for attachments, typically a dataset mountpoint
                       (e.g., "/mnt/tank/work"). Method warns if path is not within /mnt/.
            check_parent (bool): If True, also match when path is a child of configured attachment paths.
                                This allows finding shares that consume the given path as a subdirectory.
                                Default: False (only match path as child of attachment paths).
            exact_match (bool): If True, only match when path exactly equals the attachment path.
                               Disables parent/child hierarchy matching.
                               Default: False (allow hierarchy matching).

        Returns:
            list[dict]: List of attachment groups, one per delegate type that has matches.
                       Each dict contains:
                       - type (str): Human-readable delegate title (e.g., "NFS Share", "SMB Share")
                       - service (str): Associated service name (e.g., "nfs", "cifs") or None
                       - attachments (list[str]): Human-readable names of matched attachments

        Example return value:
            [
                {
                    "type": "NFS Share",
                    "service": "nfs",
                    "attachments": ["/mnt/tank/work"]
                },
                {
                    "type": "Rsync Task",
                    "service": "rsync",
                    "attachments": ["Daily backup to /mnt/tank/work"]
                }
            ]
        """
        if isinstance(path, str) and not path.startswith('/mnt/'):
            self.logger.warning('%s: unexpected path not located within pool mountpoint', path)

        if not path:
            return []

        result = []
        options = {'check_parent': check_parent, 'exact_match': exact_match}
        for delegate in self.attachment_delegates:
            attachments = [
                await delegate.get_attachment_name(attachment)
                for attachment in await delegate.query(path, True, options)
            ]
            if attachments:
                result.append(
                    PoolAttachment(
                        type=delegate.title,
                        service=delegate.service,
                        attachments=attachments
                    )
                )

        return result

    @private
    def register_attachment_delegate(self, delegate: 'FSAttachmentDelegate') -> None:
        self.attachment_delegates.append(delegate)

    @private
    async def query_attachment_delegate(self, name: str, path: str, enabled: bool) -> list[dict]:
        for delegate in self.attachment_delegates:
            if delegate.name == name:
                return await delegate.query(path, enabled)

        raise RuntimeError(f'Unknown attachment delegate {name!r}')

    @private
    async def get_attachment_delegates(self) -> list['FSAttachmentDelegate']:
        return self.attachment_delegates

    @private
    async def get_attachment_delegates_for_start(self) -> list['FSAttachmentDelegate']:
        """
        Returns delegates sorted for start operations.
        Higher priority delegates (infrastructure) run first.
        """
        return sorted(self.attachment_delegates, key=lambda d: d.priority, reverse=True)

    @private
    async def get_attachment_delegates_for_stop(self) -> list['FSAttachmentDelegate']:
        """
        Returns delegates sorted for stop operations.
        Lower priority delegates (dependent services) run first.
        """
        return sorted(self.attachment_delegates, key=lambda d: d.priority)

    @private
    async def stop_attachment_delegates(self, path: str) -> None:
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

            async def stop_delegate(delegate: 'FSAttachmentDelegate'):
                if attachments := await delegate.query(path, True):
                    await delegate.stop(attachments)

            await asyncio.gather(*[stop_delegate(dg) for dg in group_list])
