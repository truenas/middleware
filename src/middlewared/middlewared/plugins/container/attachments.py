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

    async def containers_on_pool(self, pool: str) -> list[ContainerEntry]:
        # Every container whose *root* dataset lives on `pool`, regardless of runtime state. This is
        # the pool-identity counterpart to `containers_on_paths`, which answers the subtree question
        # -- and includes bind-mount sources -- for the query and start paths; the two are not
        # interchangeable, see `destroy`. Matched by name rather than through `filesystem.is_child`
        # because its only caller runs once the pool is gone, leaving nothing to resolve against.
        containers = await self.middleware.call2(self.s.container.query)
        assert isinstance(containers, list)
        return [c for c in containers if c.dataset.split('/')[0] == pool]

    def storage_paths(self, container: ContainerEntry) -> list[str]:
        # The paths whose datasets the container needs to run: its root dataset and every FILESYSTEM
        # device source.
        #
        # The root entry is deliberately derived from the dataset *name*, not from where the
        # dataset is actually mounted (`container_instance_dataset_mountpoint`, which yields
        # `/mnt/.truenas_containers/<pool>/containers/<name>`). Both consumers of this list need
        # the name-derived form:
        # - `filesystem.is_child` is asked whether the container lives under `/mnt/<pool>`, which
        #   the real mountpoint is not a child of.
        # - `pool.dataset.path_in_locked_datasets` strips `/mnt/` and re-parses the remainder as a
        #   dataset name.
        # Switching this to the real mountpoint would silently stop matching containers on pool
        # export and pool lock.
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
        # Tear the domain down through the libvirt delete rather than `stop`: our callers destroy the
        # storage as soon as this returns, and `stop` comes back while the container's runtime mounts
        # -- the idmapped root under /run/truenas_containers/ and every FILESYSTEM bind mount -- are
        # still being unwound by the domain's stop event, so the destroy then fails on a busy dataset.
        # Deleting the domain destroys it and gives that teardown time to finish before undefining it.
        #
        # Never remove the container's records here. The database row is the only copy of a
        # container's definition (init, environment, devices, capabilities), and its rootfs dataset
        # outlives this delegate: a pool may simply have been exported, in which case the storage is
        # still there and is orphaned the moment the row goes. Freeing the container's idmap slice
        # makes that unrecoverable, because a later container can claim the UID range the surviving
        # rootfs is still owned by.
        #
        # Records are removed only where nothing recoverable is left -- when the pool was both
        # cascaded and destroyed -- which `destroy` below handles, because that runs once the data
        # is confirmed gone.
        for attachment in attachments:
            try:
                container = await self.middleware.call2(self.s.container.get_instance, attachment['id'])
                await self.middleware.call2(self.s.container.delete_container_from_libvirt, container)
            except Exception:
                self.logger.warning('%r: failed to tear down container', attachment['id'], exc_info=True)

    async def destroy(self, path: str) -> None:
        # The pool's data is gone, so the rootfs a container's record describes is gone with it. This
        # is the one place where dropping the record loses nothing that still exists -- the
        # definition can no longer be reunited with a rootfs, and its idmap slice is finally safe to
        # hand out again -- which is why `delete` never does it.
        #
        # Deliberately not driven by the attachments `delete` was given:
        # - it must ignore runtime state, or a pool holding only stopped containers keeps every
        #   record while a pool of running ones is cleaned out;
        # - it must match the *root* dataset only, or a container rooted on another pool that merely
        #   bind-mounts this one loses its whole definition while its rootfs is still there.
        #
        # For the first of those reasons it also cannot assume `delete` already tore these domains
        # down, hence the libvirt delete here as well -- it is idempotent.
        removed = False
        for container in await self.containers_on_pool(path.removeprefix('/mnt/')):
            try:
                await self.middleware.call2(self.s.container.delete_container_from_libvirt, container)
                await self.middleware.call2(self.s.container.delete_container_from_db, container)
            except Exception:
                self.logger.error(
                    '%s: failed to remove container records after its pool was destroyed',
                    container.name, exc_info=True,
                )
            else:
                removed = True

        if removed:
            await self.middleware.call('etc.generate', 'libvirt_guests')

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
        if paths:
            await self.start_autostart_on_paths(paths)

    async def start_on_import(self, path: str) -> None:
        # Same reasoning as `start_on_unlock`: the generic path would start every stopped container
        # on the pool, ignoring autostart entirely.
        await self.start_autostart_on_paths([path])

    async def start_autostart_on_paths(self, paths: list[str]) -> None:
        # (Re)start the autostart containers whose storage lives on `paths`, now that those paths
        # have become available again.
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
                    'Unable to query %r container after its storage became available',
                    container.id, exc_info=True
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
                self.logger.error(
                    'Failed to start %r container after its storage became available',
                    container.id, exc_info=True
                )


async def setup(middleware: Middleware) -> None:
    await middleware.call('pool.dataset.register_attachment_delegate', LXCFSAttachmentDelegate(middleware))
    await middleware.call('pool.dataset.register_attachment_delegate', ContainerFSAttachmentDelegate(middleware))
