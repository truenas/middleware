from __future__ import annotations

import os.path
from typing import TYPE_CHECKING, Any, Iterable

from middlewared.api.current import (
    QueryOptions,
    VMCDROMDevice,
    VMDeviceEntry,
    VMDiskDevice,
    VMDisplayDevice,
    VMEntry,
    VMRAWDevice,
    VMStartOptions,
    VMStopOptions,
)
from middlewared.common.attachment import FSAttachmentDelegate, UnlockedDataset
from middlewared.common.ports import PortDelegate, PortDetail
from middlewared.plugins.zfs.zvol_utils import zvol_path_to_name
from middlewared.utils.libvirt.utils import ACTIVE_STATES

if TYPE_CHECKING:
    from middlewared.main import Middleware


class VMFSAttachmentDelegate(FSAttachmentDelegate[dict[str, Any]]):
    name = 'vm'
    title = 'VM'

    async def query(self, path: str, enabled: bool, options: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        vms_attached: list[dict[str, Any]] = []
        ignored_vms = await self.call2(self.s.vm.get_vms_to_ignore_for_querying_attachments, enabled)
        vm_names = {vm.id: vm.name for vm in await self.call2(self.s.vm.query)}
        for device in await self.call2(self.s.vm.device.query):
            if device.vm in ignored_vms:
                continue

            if await self.device_on_paths(device, [path]):
                vm_entry = {'id': device.vm, 'name': vm_names[device.vm]}
                if vm_entry not in vms_attached:
                    vms_attached.append(vm_entry)

        return vms_attached

    def device_disk_path(self, device: VMDeviceEntry) -> str | None:
        # Normalized `/mnt`-relative path a disk-like device is backed by, or `None` if the device
        # is not disk-backed or has no path.
        if not isinstance(device.attributes, (VMDiskDevice, VMRAWDevice, VMCDROMDevice)):
            return None

        disk = device.attributes.path
        if not disk:
            return None

        if disk.startswith('/dev/zvol/'):
            disk = os.path.join('/mnt', zvol_path_to_name(disk))

        return disk

    def disk_paths(self, vm: VMEntry) -> list[str]:
        # Normalized paths of the VM's DISK/RAW devices -- the storage it can't run without.
        return [
            disk for device in vm.devices
            if isinstance(device.attributes, (VMDiskDevice, VMRAWDevice))
            if (disk := self.device_disk_path(device))
        ]

    async def device_on_paths(self, device: VMDeviceEntry, paths: Iterable[str]) -> bool:
        disk = self.device_disk_path(device)
        return disk is not None and await self.middleware.call('filesystem.is_child', disk, list(paths))

    async def storage_locked(self, vm: VMEntry) -> bool:
        # True if any DISK/RAW disk the VM needs is on a dataset that is still locked (or has a
        # locked parent).
        for disk in self.disk_paths(vm):
            if await self.middleware.call('pool.dataset.path_in_locked_datasets', disk):
                return True

        return False

    async def delete(self, attachments: list[dict[str, Any]]) -> None:
        for attachment in attachments:
            try:
                job = await self.call2(self.s.vm.stop, attachment['id'], VMStopOptions())
                await job.wait()
            except Exception:
                self.logger.warning('Unable to vm.stop %r', attachment['id'])

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
                self.logger.warning('Unable to %s %r', action, attachment['id'])

    async def stop(self, attachments: list[dict[str, Any]]) -> None:
        await self.toggle(attachments, False)

    async def start(self, attachments: list[dict[str, Any]]) -> None:
        await self.toggle(attachments, True)

    async def start_on_unlock(self, datasets: list[UnlockedDataset]) -> None:
        # The generic start path cannot help here: query(enabled=True) only reports already-active
        # VMs, so an autostart VM that is stopped because its disk's dataset was locked would never
        # be restarted. Match autostart VMs to the unlocked datasets ourselves and (re)start them.
        paths: set[str] = set()
        for dataset, mountpoint in datasets:
            if mountpoint:
                paths.add(mountpoint)
            # Child zvols live under the dataset's name-based path no matter where (or whether)
            # the dataset's filesystem is mounted
            paths.add(os.path.join('/mnt', dataset['name']))

        vms = await self.call2(self.s.vm.query, [('autostart', '=', True)], QueryOptions(force_sql_filters=True))
        for vm in vms:
            if not await self.vm_on_paths(vm, paths):
                continue
            if await self.storage_locked(vm):
                # Don't start a VM while any dataset a DISK/RAW disk lives on is still locked -- it
                # would boot with missing storage. It gets started when the unlock of its last
                # remaining dependency triggers this delegate again.
                continue

            try:
                # Use a fresh state for the restart decision: the query snapshot may have gone stale
                # while earlier VMs in this loop were being restarted (or a VM may have been deleted since)
                state = (await self.call2(self.s.vm.status, vm.id)).state
            except Exception:
                self.logger.warning('Unable to query %r VM after unlock', vm.name, exc_info=True)
                continue

            if state == 'RUNNING':
                # If the bounce-stop fails, the VM is still running with its stale mount; the start
                # below can't help, so skip it rather than logging a misleading start failure.
                try:
                    stop_job = await self.call2(
                        self.s.vm.stop, vm.id, VMStopOptions(force_after_timeout=True)
                    )
                    await stop_job.wait()
                    if stop_job.error:
                        self.logger.warning('Unable to stop %r VM: %s', vm.name, stop_job.error)
                        continue
                except Exception:
                    self.logger.warning('Unable to stop %r VM', vm.name, exc_info=True)
                    continue
            elif state in ACTIVE_STATES:
                # SUSPENDED: don't discard the paused state just to restart the VM
                continue

            try:
                await self.call2(self.s.vm.start, vm.id, VMStartOptions())
            except Exception:
                self.logger.error('Failed to start %r VM after unlock', vm.name, exc_info=True)

    async def vm_on_paths(self, vm: VMEntry, paths: Iterable[str]) -> bool:
        # A VM is tied to the unlocked datasets if a DISK/RAW disk lives there: it cannot run without
        # it, so a VM stopped when its dataset was locked is restarted on unlock. CDROMs are removable
        # media and deliberately don't trigger a restart -- note this is asymmetric with the lock side
        # (`query` treats CDROMs as disk-like), so a VM whose only tie to a locked dataset is a CDROM
        # is stopped when it locks but not auto-restarted on unlock; it must be started manually.
        # `filesystem.is_child` matches the cartesian product of both lists, so this is a single call.
        disks = self.disk_paths(vm)
        return bool(disks) and await self.middleware.call('filesystem.is_child', disks, list(paths))


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
