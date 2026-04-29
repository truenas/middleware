from __future__ import annotations

import os.path
from typing import TYPE_CHECKING, Any

from middlewared.api.current import ContainerStopOptions
from middlewared.common.attachment import FSAttachmentDelegate
from middlewared.utils.libvirt.utils import ACTIVE_STATES

from .utils import container_dataset

if TYPE_CHECKING:
    from middlewared.main import Middleware


class LXCFSAttachmentDelegate(FSAttachmentDelegate):

    name = "lxc"
    title = "LXC"

    async def query(self, path: str, enabled: bool, options: dict[str, str] | None = None) -> list[dict[str, str]]:
        # We would just like to return here that a specific pool/root dataset is being used
        # by LXC, nothing special otherwise needs to be done here
        results: list[dict[str, str]] = []
        query_ds = os.path.relpath(path, "/mnt")
        containers = await self.middleware.call2(self.s.container.query)
        assert isinstance(containers, list)
        for container in containers:
            container_pool = container.dataset.split("/")[0]
            if query_ds == container_pool or query_ds.startswith(container_dataset(container_pool)):
                results.append({"id": container_pool})
                break

        if not results and query_ds == (await self.middleware.call("lxc.config")).preferred_pool:
            results.append({"id": query_ds})

        return results

    async def get_attachment_name(self, attachment: dict[str, str]) -> str:
        return attachment["id"]

    async def delete(self, attachments: list[dict[str, str]]) -> None:
        lxc_config = await self.middleware.call("lxc.config")
        if (preferred_pool := lxc_config.preferred_pool) and any(
            attachment["id"] == preferred_pool for attachment in attachments
        ):
            # We use datastore directly here as we do not want export to fail because for example some
            # bridge device or anything does not exist and validation in lxc.update fails because of that
            await self.middleware.call("datastore.update", "container.config", lxc_config.id, {
                "preferred_pool": None,
            })

    async def toggle(self, attachments: list[dict[str, str]], enabled: bool) -> None:
        pass


class ContainerFSAttachmentDelegate(FSAttachmentDelegate):

    name = "container"
    title = "CONTAINER"

    async def query(self, path: str, enabled: bool, options: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        containers_attached: list[dict[str, Any]] = []
        # Track containers to skip during attachment queries:
        # - enabled=True: looking for active attachments, skip inactive containers
        # - enabled=False: looking for inactive attachments, skip active containers
        # Also tracks containers already found via root dataset check to avoid duplicates when checking devices
        ignored_or_seen_containers: set[int] = set()
        containers = await self.middleware.call2(self.s.container.query)
        assert isinstance(containers, list)
        for container in containers:
            state = container.status.state
            if (enabled and state not in ACTIVE_STATES) or (enabled is False and state in ACTIVE_STATES):
                ignored_or_seen_containers.add(container.id)
                continue

            if await self.middleware.call("filesystem.is_child", os.path.join("/mnt", container.dataset), path):
                containers_attached.append({"id": container.id, "name": container.name})
                ignored_or_seen_containers.add(container.id)

        for device in await self.middleware.call("datastore.query", "container.device"):
            if (
                device["attributes"]["dtype"] != "FILESYSTEM"
                or device["container"]["id"] in ignored_or_seen_containers
            ):
                continue

            source = device["attributes"].get("source")
            if not source:
                continue

            if await self.middleware.call("filesystem.is_child", source, path):
                containers_attached.append({
                    "id": device["container"]["id"],
                    "name": device["container"]["name"],
                })
                ignored_or_seen_containers.add(device["container"]["id"])

        return containers_attached

    async def delete(self, attachments: list[dict[str, Any]]) -> None:
        for attachment in attachments:
            try:
                await self.middleware.call2(
                    self.s.container.delete_container_from_db_and_libvirt,
                    await self.middleware.call2(self.s.container.get_instance, attachment["id"]),
                )
            except Exception:
                self.middleware.logger.warning("Unable to delete %r container", attachment["id"])

    async def toggle(self, attachments: list[dict[str, Any]], enabled: bool) -> None:
        await getattr(self, "start" if enabled else "stop")(attachments)

    async def stop(self, attachments: list[dict[str, Any]]) -> None:
        for attachment in attachments:
            try:
                job = await self.middleware.call2(
                    self.s.container.stop, attachment["id"], ContainerStopOptions(force=True)
                )
                await job.wait(raise_error=True)
            except Exception:
                self.middleware.logger.warning("Unable to stop %r container", attachment["id"])

    async def start(self, attachments: list[dict[str, Any]]) -> None:
        for attachment in attachments:
            try:
                await self.middleware.call2(self.s.container.start, attachment["id"])
            except Exception:
                self.middleware.logger.warning("Unable to start %r container", attachment["id"])


async def setup(middleware: Middleware) -> None:
    await middleware.call("pool.dataset.register_attachment_delegate", LXCFSAttachmentDelegate(middleware))
    await middleware.call("pool.dataset.register_attachment_delegate", ContainerFSAttachmentDelegate(middleware))
