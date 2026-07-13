import os.path

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

    def storage_paths(self, container):
        # The paths whose datasets the container needs to run: its root dataset and every FILESYSTEM
        # device source.
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
        for attachment in attachments:
            try:
                container = await self.middleware.call('container.get_instance', attachment['id'])
                await self.middleware.call('container.delete_container_from_db_and_libvirt', container)
            except Exception:
                self.logger.warning('Unable to delete %r container', attachment['id'])
        else:
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
        if not paths:
            return

        containers = await self.middleware.call(
            'container.query', [('autostart', '=', True)], {'force_sql_filters': True}
        )
        to_start = []
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
                    'Unable to query %r container after unlock', container['id'], exc_info=True
                )
                continue

            if state == 'RUNNING':
                try:
                    await (
                        await self.middleware.call('container.stop', container['id'], {'force_after_timeout': True})
                    ).wait(raise_error=True)
                except Exception:
                    self.logger.warning('Unable to stop %r container', container['id'], exc_info=True)
            elif state in ACTIVE_STATES:
                # SUSPENDED: don't discard the paused state just to restart the container
                continue
            to_start.append(container)

        await self.start(to_start)


async def setup(middleware):
    await middleware.call('pool.dataset.register_attachment_delegate', LXCFSAttachmentDelegate(middleware))
    await middleware.call('pool.dataset.register_attachment_delegate', ContainerFSAttachmentDelegate(middleware))
