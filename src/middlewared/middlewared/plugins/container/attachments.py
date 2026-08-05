import os.path

from middlewared.api.current import ZFSResourceQuery
from middlewared.common.attachment import FSAttachmentDelegate
from middlewared.utils.libvirt.utils import ACTIVE_STATES

from .utils import container_dataset


class LXCFSAttachmentDelegate(FSAttachmentDelegate):

    name = 'lxc'
    title = 'LXC'

    async def query(self, path, enabled, options=None):
        # We would just like to return here that a specific pool/root dataset is being used
        # by LXC, nothing special otherwise needs to be done here
        results = []
        query_ds = os.path.relpath(path, '/mnt')  # noqa: ASYNC240
        for container in await self.middleware.call('container.query'):
            container_pool = container['dataset'].split('/')[0]
            if query_ds == container_pool or query_ds.startswith(container_dataset(container_pool)):
                results.append({'id': container_pool})
                break

        if not results and query_ds == (await self.middleware.call('lxc.config'))['preferred_pool']:
            results.append({'id': query_ds})

        return results

    async def get_attachment_name(self, attachment):
        return attachment['id']

    async def delete(self, attachments):
        lxc_config = await self.middleware.call('lxc.config')
        if (preferred_pool := lxc_config['preferred_pool']) and any(
            attachment['id'] == preferred_pool for attachment in attachments
        ):
            # We use datastore directly here as we do not want export to fail because for example some
            # bridge device or anything does not exist and validation in lxc.update fails because of that
            await self.middleware.call('datastore.update', 'container.config', lxc_config['id'], {
                'preferred_pool': None,
            })

    async def toggle(self, attachments, enabled):
        pass

    async def start_on_unlock(self, datasets):
        # `start` is a no-op for this delegate, so don't waste the base implementation's
        # `container.query` on it
        pass


class ContainerFSAttachmentDelegate(FSAttachmentDelegate):

    name = 'container'
    title = 'CONTAINER'

    async def query(self, path, enabled, options=None):
        # Select the candidate containers by state:
        # - enabled=True: looking for active attachments, skip inactive containers
        # - enabled=False: looking for inactive attachments, skip active containers
        candidates = []
        for container in await self.middleware.call('container.query'):
            state = container['status']['state']
            if (enabled and state not in ACTIVE_STATES) or (enabled is False and state in ACTIVE_STATES):
                continue
            candidates.append(container)

        return [
            {'id': container['id'], 'name': container['name']}
            async for container in self.containers_on_paths(candidates, [path])
        ]

    async def containers_on_paths(self, containers, paths):
        # Returns the subset of `containers` (as returned by `container.query`) whose root dataset,
        # or any FILESYSTEM device source, lives on or under any of `paths`.
        for container in containers:
            if await self.container_on_paths(container, paths):
                yield container

    async def containers_on_pool(self, pool):
        # Every container whose *root* dataset lives on `pool`, regardless of runtime state. This is
        # the pool-identity counterpart to `containers_on_paths`, which answers the subtree question
        # -- and includes bind-mount sources -- for the query and start paths; the two are not
        # interchangeable, see `destroy`. Matched by name rather than through `filesystem.is_child`
        # because its only caller runs once the pool is gone, leaving nothing to resolve against.
        return [
            container for container in await self.middleware.call('container.query')
            if container['dataset'].split('/')[0] == pool
        ]

    def storage_paths(self, container):
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
        paths = [os.path.join('/mnt', container['dataset'])]
        for device in container['devices']:
            if device['attributes']['dtype'] == 'FILESYSTEM' and (source := device['attributes'].get('source')):
                paths.append(source)

        return paths

    async def container_on_paths(self, container, paths):
        # `filesystem.is_child` accepts lists on both sides and matches the cartesian product, so
        # this is a single call rather than one per (storage path, unlocked path) pair.
        return await self.middleware.call('filesystem.is_child', self.storage_paths(container), list(paths))

    async def storage_locked(self, container):
        # True if any dataset the container needs to run -- its root dataset or a FILESYSTEM device
        # source -- is still locked (or has a locked parent).
        for path in self.storage_paths(container):
            if await self.middleware.call('pool.dataset.path_in_locked_datasets', path):
                return True

        return False

    async def delete(self, attachments):
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
                container = await self.middleware.call('container.get_instance', attachment['id'])
                await self.middleware.call('container.delete_container_from_libvirt', container)
            except Exception:
                self.logger.warning('%r: failed to tear down container', attachment['id'], exc_info=True)

    async def destroy(self, path):
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
                await self.middleware.call('container.delete_container_from_libvirt', container)
                await self.middleware.call('container.delete_container_from_db', container)
            except Exception:
                self.logger.error(
                    '%s: failed to remove container records after its pool was destroyed',
                    container['name'], exc_info=True,
                )
            else:
                removed = True

        if removed:
            await self.middleware.call('etc.generate', 'libvirt_guests')

    async def toggle(self, attachments, enabled):
        return await getattr(self, 'start' if enabled else 'stop')(attachments)

    async def stop(self, attachments):
        for attachment in attachments:
            try:
                await (
                    await self.middleware.call('container.stop', attachment['id'], {'force': True})
                ).wait(raise_error=True)
            except Exception:
                self.logger.warning('Unable to stop %r container', attachment['id'])

    async def start(self, attachments):
        for attachment in attachments:
            try:
                await self.middleware.call('container.start', attachment['id'])
            except Exception:
                self.logger.error('Failed to start %r container', attachment['id'], exc_info=True)

    async def start_on_unlock(self, datasets):
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

    async def start_on_import(self, path):
        # Same reasoning as `start_on_unlock`: the generic path would start every stopped container
        # on the pool, ignoring autostart entirely.
        await self.start_autostart_on_paths([path])

    async def start_autostart_on_paths(self, paths):
        # (Re)start the autostart containers whose storage lives on `paths`, now that those paths
        # have become available again.
        containers = await self.middleware.call(
            'container.query', [('autostart', '=', True)], {'force_sql_filters': True}
        )
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
                state = (await self.middleware.call('container.get_instance', container['id']))['status']['state']
            except Exception:
                self.logger.warning(
                    'Unable to query %r container after its storage became available',
                    container['id'], exc_info=True
                )
                continue

            if state == 'RUNNING':
                try:
                    await (
                        await self.middleware.call('container.stop', container['id'], {'force_after_timeout': True})
                    ).wait(raise_error=True)
                except Exception:
                    # It is still running with its stale mount; the start below can't help, so skip
                    # it rather than logging a misleading start failure.
                    self.logger.warning('Unable to stop %r container', container['id'], exc_info=True)
                    continue
            elif state in ACTIVE_STATES:
                # SUSPENDED: don't discard the paused state just to restart the container
                continue

            try:
                await self.middleware.call('container.start', container['id'])
            except Exception:
                self.logger.error(
                    'Failed to start %r container after its storage became available',
                    container['id'], exc_info=True
                )


async def pool_post_import(middleware, pool=None, **kwargs):
    """Re-point containers at their storage after their pool was imported under a new name.

    A container's dataset is always `<pool>/.truenas_containers/containers/<name>`, so the location
    under the newly imported pool is derived rather than guessed. The remap is only committed when
    the old pool is genuinely gone, the derived dataset actually exists, and no other container
    already claims it -- otherwise the record is left alone for the user to sort out, which is the
    safer failure.
    """
    if pool is None:
        # Fired with no pool on boot
        return

    containers = await middleware.call('container.query')
    known_pools = {p['name'] for p in await middleware.call('pool.query')}
    claimed = {container['dataset'] for container in containers}

    for container in containers:
        old_pool = container['dataset'].split('/')[0]
        if old_pool == pool['name'] or old_pool in known_pools:
            continue

        dataset = f'{container_dataset(pool["name"])}/containers/{container["name"]}'
        if dataset in claimed:
            middleware.logger.warning(
                '%s: not re-pointing container at %r after pool rename, another container already uses it',
                container['name'], dataset,
            )
            continue

        if not await middleware.call2(
            middleware.services.zfs.resource.query_impl,
            ZFSResourceQuery(paths=[dataset], properties=None),
        ):
            continue

        # Written through the datastore rather than `container.update` / `container.device.update`
        # so that validation of an unrelated part of the container (a missing bridge device, say)
        # cannot fail the pool import. One container failing must not abort the import or stop the
        # rest from being re-pointed, so each is applied behind its own boundary.
        try:
            for device in container['devices']:
                if device['attributes']['dtype'] != 'FILESYSTEM':
                    continue
                if not (source := device['attributes'].get('source')):
                    continue

                if source == f'/mnt/{old_pool}' or source.startswith(f'/mnt/{old_pool}/'):
                    attributes = dict(device['attributes'])
                    attributes['source'] = f'/mnt/{pool["name"]}' + source[len(f'/mnt/{old_pool}'):]
                    await middleware.call(
                        'datastore.update', 'container.device', device['id'], {'attributes': attributes}
                    )

            await middleware.call('datastore.update', 'container.container', container['id'], {'dataset': dataset})
        except Exception:
            middleware.logger.error(
                '%s: failed to re-point container at %r after pool rename', container['name'], dataset,
                exc_info=True,
            )
            continue

        claimed.add(dataset)
        middleware.logger.info(
            '%s: re-pointed container at %r after its pool was renamed from %r',
            container['name'], dataset, old_pool,
        )


async def setup(middleware):
    await middleware.call('pool.dataset.register_attachment_delegate', LXCFSAttachmentDelegate(middleware))
    await middleware.call('pool.dataset.register_attachment_delegate', ContainerFSAttachmentDelegate(middleware))
    middleware.register_hook('pool.post_import', pool_post_import, sync=True)
