import os.path

from middlewared.common.attachment import FSAttachmentDelegate
from middlewared.plugins.zfs_.utils import zvol_path_to_name
from middlewared.utils.libvirt.utils import ACTIVE_STATES

from .utils import container_dataset


class LXCFSAttachmentDelegate(FSAttachmentDelegate):

    name = 'lxc'
    title = 'LXC'

    async def query(self, path, enabled, options=None):
        # We would just like to return here that a specific pool/root dataset is being used
        # by LXC, nothing special otherwise needs to be done here
        results = []
        query_ds = os.path.relpath(path, '/mnt')
        for container in await self.middleware.call('container.query'):
            container_pool = container['dataset'].split('/')[0]
            if query_ds == container_pool or query_ds.startswith(container_dataset(container_pool)):
                results.append({'id': container_pool})
                break
        return results

    async def get_attachment_name(self, attachment):
        return attachment['id']

    async def delete(self, attachments):
        pass

    async def toggle(self, attachments, enabled):
        pass


class ContainerFSAttachmentDelegate(FSAttachmentDelegate):

    name = 'container'
    title = 'CONTAINER'

    async def query(self, path, enabled, options=None):
        containers_attached = []
        # Track containers to skip during attachment queries:
        # - enabled=True: looking for active attachments, skip inactive containers
        # - enabled=False: looking for inactive attachments, skip active containers
        # Also tracks containers already found via root dataset check to avoid duplicates when checking devices
        ignored_or_seen_containers = set()
        for container in await self.middleware.call('container.query'):
            state = container['status']['state']
            if (enabled and state not in ACTIVE_STATES) or (enabled is False and state in ACTIVE_STATES):
                ignored_or_seen_containers.add(container['id'])
                continue

            if await self.middleware.call('filesystem.is_child', os.path.join('/mnt', container['dataset']), path):
                containers_attached.append({'id': container['id'], 'name': container['name']})
                ignored_or_seen_containers.add(container['id'])

        for device in await self.middleware.call('datastore.query', 'container.device'):
            if (
                device['attributes']['dtype'] not in ('DISK', 'RAW', 'FILESYSTEM')
                or device['container']['id'] in ignored_or_seen_containers
            ):
                continue

            disk = device['attributes'].get('path') or device['attributes'].get('source')
            if not disk:
                continue

            if disk.startswith('/dev/zvol'):
                disk = os.path.join('/mnt', zvol_path_to_name(disk))

            if await self.middleware.call('filesystem.is_child', disk, path):
                containers_attached.append({
                    'id': device['container']['id'],
                    'name': device['container']['name'],
                })
                ignored_or_seen_containers.add(device['container']['id'])

        return containers_attached

    async def delete(self, attachments):
        await self.toggle(attachments, False)

    async def toggle(self, attachments, enabled):
        if enabled:
            action = 'container.start'
            action_args = []
        else:
            action = 'container.stop'
            action_args = [{'force': True}]

        for attachment in attachments:
            try:
                await self.middleware.call(action, attachment['id'], *action_args)
            except Exception:
                self.middleware.logger.warning('Unable to %s %r', action, attachment['id'])

    async def stop(self, attachments):
        await self.toggle(attachments, False)

    async def start(self, attachments):
        await self.toggle(attachments, True)


async def setup(middleware):
    await middleware.call('pool.dataset.register_attachment_delegate', LXCFSAttachmentDelegate(middleware))
    await middleware.call('pool.dataset.register_attachment_delegate', ContainerFSAttachmentDelegate(middleware))
