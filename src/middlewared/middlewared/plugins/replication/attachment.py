from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from middlewared.api.current import ReplicationEntry
from middlewared.common.attachment import FSAttachmentDelegate
from middlewared.plugins.zettarepl_.state import REPLICATION_TASK_STATE

if TYPE_CHECKING:
    from middlewared.main import Middleware


class ReplicationFSAttachmentDelegate(FSAttachmentDelegate[ReplicationEntry]):
    name = "replication"
    title = "Replication"

    async def query(self, path: str, enabled: bool, options: dict[str, Any] | None = None) -> list[ReplicationEntry]:
        results: list[ReplicationEntry] = []
        for replication in await self.middleware.call2(
            self.middleware.services.replication.query, [["enabled", "=", enabled]]
        ):
            if replication.transport == "LOCAL" or replication.direction == "PUSH":
                if await self.middleware.call(
                    "filesystem.is_child",
                    [os.path.join("/mnt", source_dataset) for source_dataset in replication.source_datasets],
                    path,
                ):
                    results.append(replication)

            if replication.transport == "LOCAL" or replication.direction == "PULL":
                if await self.middleware.call(
                    "filesystem.is_child", os.path.join("/mnt", replication.target_dataset), path
                ):
                    results.append(replication)

        return results

    async def delete(self, attachments: list[ReplicationEntry]) -> None:
        for attachment in attachments:
            await self.middleware.call("datastore.delete", "storage.replication", attachment.id)

        await self.middleware.call("zettarepl.update_tasks")

    async def toggle(self, attachments: list[ReplicationEntry], enabled: bool) -> None:
        for attachment in attachments:
            await self.middleware.call(
                "datastore.update", "storage.replication", attachment.id, {"repl_enabled": enabled}
            )

        await self.middleware.call("zettarepl.update_tasks")


async def on_zettarepl_state_changed(middleware: Middleware, id_: str, fields: dict[str, Any]) -> None:
    if (task_id := REPLICATION_TASK_STATE.task_id_number(id_)) is not None:
        middleware.send_event("replication.query", "CHANGED", id=task_id, fields={"state": fields})


async def setup(middleware: Middleware) -> None:
    await middleware.call2(
        middleware.services.zfs.resource.register_attachment_delegate, ReplicationFSAttachmentDelegate(middleware)
    )
    await middleware.call("network.general.register_activity", "replication", "Replication")

    middleware.register_hook("zettarepl.state_change", on_zettarepl_state_changed)
