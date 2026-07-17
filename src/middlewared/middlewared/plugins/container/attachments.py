from __future__ import annotations

import os.path
from typing import TYPE_CHECKING, Any, AsyncGenerator, Iterable

from middlewared.api.current import (
    ContainerEntry,
    ContainerFilesystemDevice,
    ContainerStopOptions,
    QueryOptions,
)
from middlewared.common.attachment import FSAttachmentDelegate, UnlockedDataset
from middlewared.utils.libvirt.utils import ACTIVE_STATES

from .utils import container_dataset

if TYPE_CHECKING:
    from middlewared.main import Middleware


class LXCFSAttachmentDelegate(FSAttachmentDelegate[dict[str, str]]):

    name = 'lxc'
    title = 'LXC'

    async def query(self, path: str, enabled: bool, options: dict[str, str] | None = None) -> list[dict[str, str]]:
        # We would just like to return here that a specific pool/root dataset is being used
        # by LXC, nothing special otherwise needs to be done here
        results: list[dict[str, str]] = []
        query_ds = os.path.relpath(path, '/mnt')  # noqa: ASYNC240
        containers = await self.middleware.call2(self.s.container.query)
        assert isinstance(containers, list)
        for container in containers:
            container_pool = container.dataset.split('/')[0]
            if query_ds == container_pool or query_ds.startswith(container_dataset(container_pool)):
                results.append({'id': container_pool})
                break

        if not results and query_ds == (await self.middleware.call('lxc.config')).preferred_pool:
            results.append({'id': query_ds})

        return results

    async def get_attachment_name(self, attachment: dict[str, str]) -> str:
        return attachment['id']

    async def delete(self, attachments: list[dict[str, str]]) -> None:
        lxc_config = await self.middleware.call('lxc.config')
        if (preferred_pool := lxc_config.preferred_pool) and any(
            attachment['id'] == preferred_pool for attachment in attachments
        ):
            # We use datastore directly here as we do not want export to fail because for example some
            # bridge device or anything does not exist and validation in lxc.update fails because of that
            await self.middleware.call('datastore.update', 'container.config', lxc_config.id, {
                'preferred_pool': None,
            })

    async def toggle(self, attachments: list[dict[str, str]], enabled: bool) -> None:
        pass

    async def start_on_unlock(self, datasets: list[UnlockedDataset]) -> None:
        # `start` is a no-op for this delegate, so don't waste the base implementation's
        # `container.query` on it
        pass


class ContainerFSAttachmentDelegate(FSAttachmentDelegate[dict[str, Any]]):

    name = 'container'
    title = 'CONTAINER'

    async def query(self, path: str, enabled: bool, options: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        containers = await self.middleware.call2(self.s.container.query)
        assert isinstance(containers, list)
        # Select the candidate containers by state:
        # - enabled=True: looking for active attachments, skip inactive containers
        # - enabled=False: looking for inactive attachments, skip active containers
        candidates = []
        for container in containers:
            state = container.status.state
            if (enabled and state not in ACTIVE_STATES) or (enabled is False and state in ACTIVE_STATES):
                continue
            candidates.append(container)

        return [
            {'id': container.id, 'name': container.name}
            async for container in self.containers_on_paths(candidates, [path])
        ]

    async def containers_on_paths(
        self, containers: list[ContainerEntry], paths: Iterable[str]
    ) -> AsyncGenerator[ContainerEntry]:
        # Returns the subset of `containers` (as returned by `container.query`) whose root dataset,
        # or any FILESYSTEM device source, lives on or under any of `paths`.
        for container in containers:
            if await self.container_on_paths(container, paths):
                yield container

    def storage_paths(self, container: ContainerEntry) -> list[str]:
        # The paths whose datasets the container needs to run: its root dataset and every FILESYSTEM
        # device source.
        paths = [os.path.join('/mnt', container.dataset)]
        for device in container.devices:
            if isinstance(device.attributes, ContainerFilesystemDevice):
                paths.append(device.attributes.source)

        return paths

    async def container_on_paths(self, container: ContainerEntry, paths: Iterable[str]) -> bool:
        # `filesystem.is_child` accepts lists on both sides and matches the cartesian product, so
        # this is a single call rather than one per (storage path, unlocked path) pair.
        return await self.middleware.call(  # type: ignore[no-any-return]
            'filesystem.is_child', self.storage_paths(container), list(paths)
        )

    async def storage_locked(self, container: ContainerEntry) -> bool:
        # True if any dataset the container needs to run -- its root dataset or a FILESYSTEM device
        # source -- is still locked (or has a locked parent).
        for path in self.storage_paths(container):
            if await self.middleware.call('pool.dataset.path_in_locked_datasets', path):
                return True

        return False

    async def delete(self, attachments: list[dict[str, Any]]) -> None:
        for attachment in attachments:
            try:
                await self.middleware.call2(
                    self.s.container.delete_container_from_db_and_libvirt,
                    await self.middleware.call2(self.s.container.get_instance, attachment['id']),
                )
            except Exception:
                self.logger.warning('Unable to delete %r container', attachment['id'])

    async def toggle(self, attachments: list[dict[str, Any]], enabled: bool) -> None:
        await getattr(self, 'start' if enabled else 'stop')(attachments)

    async def stop(self, attachments: list[dict[str, Any]]) -> None:
        for attachment in attachments:
            try:
                job = await self.middleware.call2(
                    self.s.container.stop, attachment['id'], ContainerStopOptions(force=True)
                )
                await job.wait(raise_error=True)
            except Exception:
                self.logger.warning('Unable to stop %r container', attachment['id'])

    async def start(self, attachments: list[dict[str, Any]]) -> None:
        for attachment in attachments:
            try:
                await self.middleware.call2(self.s.container.start, attachment['id'])
            except Exception:
                self.logger.error('Failed to start %r container', attachment['id'], exc_info=True)

    async def start_on_unlock(self, datasets: list[UnlockedDataset]) -> None:
        # The generic start path cannot help here: it would call query(enabled=True), which only
        # reports already-active containers, so an autostart container that is stopped because its
        # pool was locked would never be restarted. Match autostart containers to the unlocked
        # datasets ourselves and (re)start them.
        paths = [
            mountpoint for dataset, mountpoint in datasets
            if dataset['type'] == 'FILESYSTEM' and mountpoint
        ]
        if not paths:
            return

        containers = await self.middleware.call2(
            self.s.container.query, [('autostart', '=', True)], QueryOptions(force_sql_filters=True)
        )
        assert isinstance(containers, list)
        async for container in self.containers_on_paths(containers, paths):
            if await self.storage_locked(container):
                # Don't start a container while any dataset it needs (its root or a FILESYSTEM
                # bind-mount source) is still locked -- it would come up with missing/empty
                # filesystems. It gets started when the unlock of its last remaining dependency
                # triggers this delegate again.
                continue
            try:
                # Use a fresh state for the restart decision: the query snapshot may have gone stale
                # while earlier containers in this loop were being restarted (or a container may have
                # been deleted since)
                state = (await self.middleware.call2(self.s.container.get_instance, container.id)).status.state
            except Exception:
                self.logger.warning(
                    'Unable to query %r container after unlock', container.id, exc_info=True
                )
                continue

            if state == 'RUNNING':
                try:
                    job = await self.middleware.call2(
                        self.s.container.stop, container.id, ContainerStopOptions(force_after_timeout=True)
                    )
                    await job.wait(raise_error=True)
                except Exception:
                    # It is still running with its stale mount; the start below can't help, so skip
                    # it rather than logging a misleading start failure.
                    self.logger.warning('Unable to stop %r container', container.id, exc_info=True)
                    continue
            elif state in ACTIVE_STATES:
                # SUSPENDED: don't discard the paused state just to restart the container
                continue

            try:
                await self.middleware.call2(self.s.container.start, container.id)
            except Exception:
                self.logger.error('Failed to start %r container after unlock', container.id, exc_info=True)


async def setup(middleware: Middleware) -> None:
    await middleware.call('pool.dataset.register_attachment_delegate', LXCFSAttachmentDelegate(middleware))
    await middleware.call('pool.dataset.register_attachment_delegate', ContainerFSAttachmentDelegate(middleware))
