from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from middlewared.api.current import PeriodicSnapshotTaskEntry
from middlewared.common.attachment import FSAttachmentDelegate

if TYPE_CHECKING:
    from middlewared.main import Middleware


class PeriodicSnapshotTaskFSAttachmentDelegate(FSAttachmentDelegate):
    name = 'snapshottask'
    title = 'Snapshot Task'
    resource_name = 'dataset'

    async def query(self, path: str, enabled: bool, options: dict[str, Any] | None = None) -> list[Any]:
        results: list[PeriodicSnapshotTaskEntry] = []
        for task in await self.middleware.call2(  # type: ignore[attr-defined]
            self.middleware.services.pool.snapshottask.query,
            [['enabled', '=', enabled]],
        ):
            if await self.middleware.call('filesystem.is_child', os.path.join('/mnt', task.dataset), path):
                results.append(task)

        return results

    async def delete(self, attachments: list[PeriodicSnapshotTaskEntry]) -> None:
        for attachment in attachments:
            await self.middleware.call('datastore.delete', 'storage.task', attachment.id)

        await self.middleware.call('zettarepl.update_tasks')

    async def toggle(self, attachments: list[PeriodicSnapshotTaskEntry], enabled: bool) -> None:
        for attachment in attachments:
            await self.middleware.call('datastore.update', 'storage.task', attachment.id, {'task_enabled': enabled})

        await self.middleware.call('zettarepl.update_tasks')


async def register(middleware: Middleware) -> None:
    await middleware.call(
        'pool.dataset.register_attachment_delegate',
        PeriodicSnapshotTaskFSAttachmentDelegate(middleware),
    )
