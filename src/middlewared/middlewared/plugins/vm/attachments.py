import collections
import os.path

from middlewared.common.attachment import FSAttachmentDelegate
from middlewared.common.ports import PortDelegate
from middlewared.plugins.zfs_.utils import zvol_path_to_name
from middlewared.service import private, Service
from middlewared.utils.libvirt.utils import ACTIVE_STATES


# Device types that are backed by a storage path (as opposed to e.g. NIC/DISPLAY/PCI)
DISKLIKE_DTYPES = ('DISK', 'RAW', 'CDROM')


async def determine_recursive_search(recursive, device, child_datasets):
    # TODO: Add unit tests for this please
    if recursive:
        return True
    elif device['attributes']['dtype'] == 'DISK':
        return False

    # What we want to do here is make sure that any raw files or cdrom files are not living in the child
    # dataset and not affected by the parent snapshot as they live on a different filesystem
    path = device['attributes']['path'].removeprefix('/mnt/')
    for split_count in range(path.count('/')):
        potential_ds = path.rsplit('/', split_count)[0]
        if potential_ds in child_datasets:
            return False
    else:
        return True


class VMService(Service):

    @private
    async def periodic_snapshot_task_begin(self, task_id):
        task = await self.call2(self.s.pool.snapshottask.get_instance, task_id)
        return await self.query_snapshot_begin(task.dataset, task.recursive)

    @private
    async def query_snapshot_begin(self, dataset, recursive):
        vms = collections.defaultdict(list)
        datasets = {
            d['id']: d for d in await self.middleware.call(
                'pool.dataset.query', [['id', '^', f'{dataset}/']], {'extra': {'properties': []}}
            )
        }
        to_ignore_vms = await self.get_vms_to_ignore_for_querying_attachments(
            True, [['suspend_on_snapshot', '=', False]]
        )
        for device in await self.middleware.call(
            'vm.device.query', [
                ['attributes.dtype', 'in', DISKLIKE_DTYPES],
                ['vm', 'nin', to_ignore_vms],
            ]
        ):
            path = device['attributes'].get('path')
            if not path:
                continue
            elif path.startswith('/dev/zvol'):
                path = os.path.join('/mnt', zvol_path_to_name(path))

            dataset_path = os.path.join('/mnt', dataset)
            if await determine_recursive_search(recursive, device, datasets):
                if await self.middleware.call('filesystem.is_child', path, dataset_path):
                    vms[device['vm']].append(device)
            elif dataset_path == path:
                vms[device['vm']].append(device)

        return vms

    @private
    async def get_vms_to_ignore_for_querying_attachments(self, enabled, extra_filters=None):
        extra_filters = extra_filters or []
        return {
            vm['id']: vm for vm in await self.middleware.call(
                'vm.query', [('status.state', 'nin' if enabled else 'in', ACTIVE_STATES)] + extra_filters
            )
        }


class VMFSAttachmentDelegate(FSAttachmentDelegate):
    name = 'vm'
    title = 'VM'

    async def query(self, path, enabled, options=None):
        vms_attached = []
        ignored_vms = await self.middleware.call('vm.get_vms_to_ignore_for_querying_attachments', enabled)
        for device in await self.middleware.call('datastore.query', 'vm.device'):
            if device['vm']['id'] in ignored_vms:
                continue

            if await self.device_on_paths(device, [path]):
                vm = {
                    'id': device['vm'].get('id'),
                    'name': device['vm'].get('name'),
                }
                if vm not in vms_attached:
                    vms_attached.append(vm)

        return vms_attached

    def device_disk_path(self, device):
        # Normalized `/mnt`-relative path a disk-like device is backed by, or `None` if the device
        # is not disk-backed or has no path.
        if device['attributes']['dtype'] not in DISKLIKE_DTYPES:
            return None

        disk = device['attributes'].get('path')
        if not disk:
            return None

        if disk.startswith('/dev/zvol/'):
            disk = os.path.join('/mnt', zvol_path_to_name(disk))

        return disk

    def disk_paths(self, vm):
        # Normalized paths of the VM's DISK/RAW devices -- the storage it can't run without.
        return [
            disk for device in vm['devices']
            if device['attributes']['dtype'] in ('DISK', 'RAW')
            if (disk := self.device_disk_path(device))
        ]

    async def device_on_paths(self, device, paths):
        disk = self.device_disk_path(device)
        return disk is not None and await self.middleware.call('filesystem.is_child', disk, list(paths))

    async def storage_locked(self, vm):
        # True if any DISK/RAW disk the VM needs is on a dataset that is still locked (or has a
        # locked parent).
        for disk in self.disk_paths(vm):
            if await self.middleware.call('pool.dataset.path_in_locked_datasets', disk):
                return True

        return False

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

    async def start_on_unlock(self, datasets):
        # The generic start path cannot help here: query(enabled=True) only reports already-active
        # VMs, so an autostart VM that is stopped because its disk's dataset was locked would never
        # be restarted. Match autostart VMs to the unlocked datasets ourselves and (re)start them.
        paths = set()
        for dataset, mountpoint in datasets:
            if mountpoint:
                paths.add(mountpoint)
            # Child zvols live under the dataset's name-based path no matter where (or whether)
            # the dataset's filesystem is mounted
            paths.add(os.path.join('/mnt', dataset['name']))

        vms = await self.middleware.call('vm.query', [('autostart', '=', True)], {'force_sql_filters': True})
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
                state = (await self.middleware.call('vm.status', vm['id']))['state']
            except Exception:
                self.middleware.logger.warning('Unable to query %r VM after unlock', vm['name'], exc_info=True)
                continue

            if state == 'RUNNING':
                try:
                    stop_job = await self.middleware.call('vm.stop', vm['id'], {'force_after_timeout': True})
                    await stop_job.wait()
                    if stop_job.error:
                        self.middleware.logger.warning('Unable to stop %r VM: %s', vm['name'], stop_job.error)
                except Exception:
                    self.middleware.logger.warning('Unable to stop %r VM', vm['name'], exc_info=True)
            elif state in ACTIVE_STATES:
                # SUSPENDED: don't discard the paused state just to restart the VM
                continue

            try:
                await self.middleware.call('vm.start', vm['id'])
            except Exception:
                self.middleware.logger.error('Failed to start %r VM after unlock', vm['name'], exc_info=True)

    async def vm_on_paths(self, vm, paths):
        # A VM is tied to the unlocked datasets if a DISK/RAW disk lives there: it cannot run without
        # it, so a VM stopped when its dataset was locked is restarted on unlock. CDROMs are removable
        # media and don't trigger a restart. `filesystem.is_child` matches the cartesian product of
        # both lists, so this is a single call.
        disks = self.disk_paths(vm)
        return bool(disks) and await self.middleware.call('filesystem.is_child', disks, list(paths))


class VMPortDelegate(PortDelegate):

    name = 'vm devices'
    namespace = 'vm.device'
    title = 'VM Device Service'

    async def get_ports(self):
        ports = []
        vms = {vm['id']: vm['name'] for vm in await self.middleware.call('vm.query')}
        for device in await self.middleware.call('vm.device.query', [['attributes.dtype', '=', 'DISPLAY']]):
            ports.append({
                'description': f'{vms[device["vm"]]!r} VM',
                'ports': [
                    (device['attributes']['bind'], device['attributes']['port']),
                    (device['attributes']['bind'], device['attributes']['web_port']),
                ]
            })

        return ports


async def setup(middleware):
    middleware.create_task(
        middleware.call('pool.dataset.register_attachment_delegate', VMFSAttachmentDelegate(middleware))
    )
    await middleware.call('port.register_attachment_delegate', VMPortDelegate(middleware))
