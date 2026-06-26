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


class ContainerFSAttachmentDelegate(FSAttachmentDelegate):

    name = 'container'
    title = 'CONTAINER'

    async def query(self, path, enabled, options=None):
        # Select the candidate containers by state:
        # - enabled=True: looking for active attachments, skip inactive containers
        # - enabled=False: looking for inactive attachments, skip active containers
        candidates = {}
        for container in await self.middleware.call('container.query'):
            state = container['status']['state']
            if (enabled and state not in ACTIVE_STATES) or (enabled is False and state in ACTIVE_STATES):
                continue
            candidates[container['id']] = container

        matched = await self.containers_on_path(candidates, path)
        return [{'id': container['id'], 'name': container['name']} for container in matched.values()]

    async def containers_on_path(self, containers, path):
        # `containers` maps container id -> container dict (as returned by `container.query`). Returns the
        # ordered id -> container subset whose root dataset, or any FILESYSTEM device source, lives on or
        # under `path` (root-dataset matches first, then device-source matches).
        matched = {}
        for container_id, container in containers.items():
            if await self.middleware.call('filesystem.is_child', os.path.join('/mnt', container['dataset']), path):
                matched[container_id] = container

        for device in await self.middleware.call('datastore.query', 'container.device'):
            container_id = device['container']['id']
            if container_id in matched or container_id not in containers:
                continue
            if device['attributes']['dtype'] != 'FILESYSTEM':
                continue
            source = device['attributes'].get('source')
            if source and await self.middleware.call('filesystem.is_child', source, path):
                matched[container_id] = containers[container_id]

        return matched

    async def delete(self, attachments):
        for attachment in attachments:
            try:
                container = await self.middleware.call('container.get_instance', attachment['id'])
                await self.middleware.call('container.delete_container_from_db_and_libvirt', container)
            except Exception:
                self.middleware.logger.warning('Unable to delete %r container', attachment['id'])
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
                self.middleware.logger.warning('Unable to stop %r container', attachment['id'])

    async def start(self, attachments):
        for attachment in attachments:
            try:
                await self.middleware.call('container.start', attachment['id'])
            except Exception:
                self.middleware.logger.warning('Unable to start %r container', attachment['id'])

    async def start_on_unlock(self, dataset, mountpoint):
        # The generic start path cannot help here: it would call query(enabled=True), which only
        # reports already-active containers, so an autostart container that is stopped because its
        # pool was locked would never be restarted. Match autostart containers to the unlocked
        # dataset ourselves and (re)start them.
        if dataset['type'] != 'FILESYSTEM' or not mountpoint:
            return

        containers = await self.autostart_containers_on_path(mountpoint)
        await self.stop([c for c in containers if c['status']['state'] in ACTIVE_STATES])
        await self.start(containers)

    async def autostart_containers_on_path(self, path):
        autostart_containers = {
            container['id']: container
            for container in await self.middleware.call('container.query', [('autostart', '=', True)])
        }
        if not autostart_containers:
            return []

        return list((await self.containers_on_path(autostart_containers, path)).values())


async def setup(middleware):
    await middleware.call('pool.dataset.register_attachment_delegate', LXCFSAttachmentDelegate(middleware))
    await middleware.call('pool.dataset.register_attachment_delegate', ContainerFSAttachmentDelegate(middleware))
