import asyncio
import collections
import os.path

from middlewared.common.attachment import FSAttachmentDelegate
from middlewared.plugins.zfs_.utils import zvol_path_to_name
from middlewared.service import private, Service
from middlewared.utils.path import is_child

from .utils import ACTIVE_STATES


class VMService(Service):

    @private
    async def query_snapshot_begin(self, dataset, recursive):
        vms = collections.defaultdict(list)
        to_ignore_vms = await self.get_vms_to_ignore_for_querying_attachments(True)
        for device in await self.middleware.call(
            'vm.device.query', [
                ['dtype', 'in', ('DISK', 'RAW', 'CDROM')],
                ['vm', 'nin', to_ignore_vms],
            ]
        ):
            path = device['attributes'].get('path')
            if not path:
                continue
            elif path.startswith('/dev/zvol'):
                path = os.path.join('/mnt', zvol_path_to_name(path))

            dataset_path = os.path.join('/mnt', dataset)
            recursive_search = recursive or device['dtype'] != 'DISK'
            if recursive_search:
                if is_child(path, dataset_path):
                    vms[device['vm']].append(device)
            elif dataset_path == path:
                vms[device['vm']].append(device)

        return vms

    @private
    async def get_vms_to_ignore_for_querying_attachments(self, enabled):
        return {
            vm['id']: vm for vm in await self.middleware.call(
                'vm.query', [('status.state', 'nin' if enabled else 'in', ACTIVE_STATES)]
            )
        }


class VMFSAttachmentDelegate(FSAttachmentDelegate):
    name = 'vm'
    title = 'VM'

    async def query(self, path, enabled, options=None):
        vms_attached = []
        ignored_vms = await self.middleware.call('vm.get_vms_to_ignore_for_querying_attachments', enabled)
        for device in await self.middleware.call('datastore.query', 'vm.device'):
            if (device['dtype'] not in ('DISK', 'RAW', 'CDROM')) or device['vm']['id'] in ignored_vms:
                continue

            disk = device['attributes'].get('path')
            if not disk:
                continue

            if disk.startswith('/dev/zvol'):
                disk = os.path.join('/mnt', zvol_path_to_name(disk))

            if is_child(disk, path):
                vm = {
                    'id': device['vm'].get('id'),
                    'name': device['vm'].get('name'),
                }
                if vm not in vms_attached:
                    vms_attached.append(vm)

        return vms_attached

    async def delete(self, attachments):
        for attachment in attachments:
            try:
                await self.middleware.call('vm.stop', attachment['id'])
            except Exception:
                self.middleware.logger.warning('Unable to vm.stop %r', attachment['id'])

    async def toggle(self, attachments, enabled):
        for attachment in attachments:
            action = 'vm.start' if enabled else 'vm.stop'
            try:
                await self.middleware.call(action, attachment['id'])
            except Exception:
                self.middleware.logger.warning('Unable to %s %r', action, attachment['id'])

    async def stop(self, attachments):
        await self.toggle(attachments, False)

    async def start(self, attachments):
        await self.toggle(attachments, True)


async def setup(middleware):
    asyncio.ensure_future(
        middleware.call('pool.dataset.register_attachment_delegate', VMFSAttachmentDelegate(middleware))
    )
