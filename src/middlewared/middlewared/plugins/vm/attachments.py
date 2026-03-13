from __future__ import annotations

import os.path
from typing import Any, TYPE_CHECKING

from middlewared.api.current import (
    VMCDROMDevice, VMDiskDevice, VMDisplayDevice, VMRAWDevice, VMStartOptions, VMStopOptions,
)
from middlewared.common.attachment import FSAttachmentDelegate
from middlewared.common.ports import PortDelegate, PortDetail
from middlewared.plugins.zfs.zvol_utils import zvol_path_to_name

if TYPE_CHECKING:
    from middlewared.main import Middleware


class VMFSAttachmentDelegate(FSAttachmentDelegate):
    name = 'vm'
    title = 'VM'

    async def query(self, path: str, enabled: bool, options: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        vms_attached: list[dict[str, Any]] = []
        ignored_vms = await self.call2(self.s.vm.get_vms_to_ignore_for_querying_attachments, enabled)
        vm_names = {vm.id: vm.name for vm in await self.call2(self.s.vm.query)}
        for device in await self.call2(self.s.vm.device.query):
            if not isinstance(device.attributes, (VMDiskDevice, VMRAWDevice, VMCDROMDevice)):
                continue
            if device.vm in ignored_vms:
                continue

            disk = device.attributes.path
            if not disk:
                continue

            if disk.startswith('/dev/zvol'):
                disk = os.path.join('/mnt', zvol_path_to_name(disk))

            if await self.middleware.call('filesystem.is_child', disk, path):
                vm_entry = {'id': device.vm, 'name': vm_names[device.vm]}
                if vm_entry not in vms_attached:
                    vms_attached.append(vm_entry)

        return vms_attached

    async def delete(self, attachments: list[dict[str, Any]]) -> None:
        for attachment in attachments:
            try:
                job = await self.call2(self.s.vm.stop, attachment['id'], VMStopOptions())
                await job.wait()
            except Exception:
                self.middleware.logger.warning('Unable to vm.stop %r', attachment['id'])

    async def toggle(self, attachments: list[dict[str, Any]], enabled: bool) -> None:
        for attachment in attachments:
            try:
                if enabled:
                    await self.call2(self.s.vm.start, attachment['id'], VMStartOptions())
                else:
                    job = await self.call2(self.s.vm.stop, attachment['id'], VMStopOptions())
                    await job.wait()
            except Exception:
                action = 'vm.start' if enabled else 'vm.stop'
                self.middleware.logger.warning('Unable to %s %r', action, attachment['id'])

    async def stop(self, attachments: list[dict[str, Any]]) -> None:
        await self.toggle(attachments, False)

    async def start(self, attachments: list[dict[str, Any]]) -> None:
        await self.toggle(attachments, True)


class VMPortDelegate(PortDelegate):

    name = 'vm devices'
    namespace = 'vm.device'
    title = 'VM Device Service'

    async def get_ports(self) -> list[PortDetail]:
        ports: list[PortDetail] = []
        vms = {vm.id: vm.name for vm in await self.call2(self.s.vm.query)}
        for device in await self.call2(
            self.s.vm.device.query, [['attributes.dtype', '=', 'DISPLAY']]
        ):
            if not isinstance(device.attributes, VMDisplayDevice):
                continue
            device_ports: list[tuple[str, int]] = []
            if device.attributes.port is not None:
                device_ports.append((device.attributes.bind, device.attributes.port))
            if device.attributes.web_port is not None:
                device_ports.append((device.attributes.bind, device.attributes.web_port))
            if device_ports:
                ports.append({
                    'description': f'{vms[device.vm]!r} VM',
                    'ports': device_ports,
                })

        return ports


async def setup(middleware: Middleware) -> None:
    middleware.create_task(
        middleware.call('pool.dataset.register_attachment_delegate', VMFSAttachmentDelegate(middleware))
    )
    await middleware.call('port.register_attachment_delegate', VMPortDelegate(middleware))
