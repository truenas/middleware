import asyncio
import re

from middlewared.common.attachment import FSAttachmentDelegate
from middlewared.utils.path import is_child


class VMFSAttachmentDelegate(FSAttachmentDelegate):
    name = 'vm'
    title = 'VM'

    async def query(self, path, enabled, options=None):
        vms_attached = []
        ignored_vms = {
            vm['id']: vm for vm in await self.middleware.call(
                'vm.query', [('status.state', '!=' if enabled else '=', 'RUNNING')]
            )
        }
        for device in await self.middleware.call('datastore.query', 'vm.device'):
            if (device['dtype'] not in ('DISK', 'RAW', 'CDROM')) or device['vm']['id'] in ignored_vms:
                continue

            disk = device['attributes'].get('path')
            if not disk:
                continue

            disk = re.sub(r'^/dev/zvol', '/mnt', disk)

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
