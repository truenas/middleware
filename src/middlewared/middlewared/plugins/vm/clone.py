import errno
import itertools
import re
import uuid

from middlewared.api import api_method
from middlewared.api.current import (
    VMCloneArgs, VMCloneResult, ZFSResourceSnapshotCloneQuery, ZFSResourceQuery, ZFSResourceSnapshotDestroyQuery,
    ZFSResourceSnapshotCreateQuery, ZFSResourceSnapshotQuery,
)
from middlewared.plugins.zfs_.utils import zvol_name_to_path, zvol_path_to_name
from middlewared.service import CallError, Service, private
from middlewared.service_exception import ValidationErrors


ZVOL_CLONE_SUFFIX = '_clone'
ZVOL_CLONE_RE = re.compile(rf'^(.*){ZVOL_CLONE_SUFFIX}\d+$')


class VMService(Service):

    async def __next_clone_name(self, name):
        vm_names = [
            i['name']
            for i in await self.middleware.call('vm.query', [
                ('name', '~', rf'{name}{ZVOL_CLONE_SUFFIX}\d+')
            ])
        ]
        clone_index = 0
        while True:
            clone_name = f'{name}{ZVOL_CLONE_SUFFIX}{clone_index}'
            if clone_name not in vm_names:
                break
            clone_index += 1
        return clone_name

    async def __clone_zvol(self, name, zvol, created_snaps, created_clones):
        zz = await self.call2(
            self.s.zfs.resource.query_impl,
            ZFSResourceQuery(paths=[zvol], properties=None)
        )
        if not zz:
            raise CallError(f'zvol {zvol} does not exist.', errno.ENOENT)

        # Get existing snapshots for this zvol (properties: None for efficiency)
        existing_snaps = await self.call2(self.s.zfs.resource.snapshot.query, ZFSResourceSnapshotQuery(
            paths=[zvol], properties=None,
        ))
        existing_snap_names = {s['name'] for s in existing_snaps}

        snapshot_name = name
        i = 0
        while True:
            zvol_snapshot = f'{zvol}@{snapshot_name}'
            if zvol_snapshot in existing_snap_names:
                if ZVOL_CLONE_RE.search(snapshot_name):
                    snapshot_name = ZVOL_CLONE_RE.sub(rf'\1{ZVOL_CLONE_SUFFIX}{i}', snapshot_name)
                else:
                    snapshot_name = f'{name}{ZVOL_CLONE_SUFFIX}{i}'
                i += 1
                continue
            break

        await self.call2(self.s.zfs.resource.snapshot.create_impl, ZFSResourceSnapshotCreateQuery(
            dataset=zvol,
            name=snapshot_name,
        ))
        created_snaps.append(zvol_snapshot)

        clone_suffix = name
        i = 0
        while True:
            clone_dst = f'{zvol}_{clone_suffix}'
            if await self.call2(
                self.s.zfs.resource.query_impl, ZFSResourceQuery(paths=[clone_dst], properties=None)
            ):
                if ZVOL_CLONE_RE.search(clone_suffix):
                    clone_suffix = ZVOL_CLONE_RE.sub(rf'\1{ZVOL_CLONE_SUFFIX}{i}', clone_suffix)
                else:
                    clone_suffix = f'{name}{ZVOL_CLONE_SUFFIX}{i}'
                i += 1
                continue
            break

        await self.call2(self.s.zfs.resource.snapshot.clone, ZFSResourceSnapshotCloneQuery(
            snapshot=zvol_snapshot,
            dataset=clone_dst,
        ))

        created_clones.append(clone_dst)

        return clone_dst

    @api_method(
        VMCloneArgs, VMCloneResult, roles=['VM_WRITE'], audit='VM clone', audit_callback=True
    )
    async def clone(self, audit_callback, id_, name):
        """
        Clone the VM `id`.

        `name` is an optional parameter for the cloned VM.
        If not provided it will append the next number available to the VM name.
        """
        vm = await self.middleware.call('vm.get_instance', id_)
        await self.validate(vm)

        origin_name = vm['name']
        for key in ('id', 'status', 'display_available'):
            vm.pop(key, None)

        devices = vm.pop('devices')
        vm['name'] = await self.__next_clone_name(vm['name'])
        vm['uuid'] = str(uuid.uuid4())  # We want to use a newer uuid here as it is supposed to be unique per VM

        if name is not None:
            vm['name'] = name

        audit_callback(f'{origin_name} to {vm["name"]}')
        # In case we need to rollback
        created_snaps = []
        created_clones = []
        try:
            new_vm = await self.middleware.call('vm.do_create', vm)

            for item in devices:
                item.pop('id', None)
                item['vm'] = new_vm['id']
                item_dtype = item['attributes']['dtype']
                if item_dtype == 'NIC':
                    if 'mac' in item['attributes']:
                        del item['attributes']['mac']
                if item_dtype == 'DISPLAY':
                    if 'port' in item['attributes']:
                        dev_dict = await self.middleware.call('vm.port_wizard')
                        item['attributes']['port'] = dev_dict['port']
                        item['attributes']['web_port'] = dev_dict['web']
                if item_dtype == 'DISK':
                    zvol = zvol_path_to_name(item['attributes']['path'])
                    item['attributes']['path'] = zvol_name_to_path(
                        await self.__clone_zvol(vm['name'], zvol, created_snaps, created_clones)
                    )
                if item_dtype == 'RAW':
                    self.logger.warning('RAW disks must be copied manually. Skipping...')
                    continue

                await self.middleware.call('vm.device.create', item)
        except Exception as e:
            for clone, snap in itertools.zip_longest(reversed(created_clones), reversed(created_snaps)):
                # order is important here. the clone is dependent on snap so destroy
                # the clone first before destroying the snap
                if clone is not None:
                    try:
                        self.call_sync2(self.s.zfs.resource.destroy_impl, clone)
                    except Exception:
                        self.logger.exception('Failed to destroy cloned zvol %r', clone)
                        # failing to destroy the clone means destroying the snap will
                        # also fail since we're not recursively destroying anything
                        continue
                    else:
                        if snap is not None:
                            try:
                                await self.call2(
                                    self.s.zfs.resource.snapshot.destroy_impl,
                                    ZFSResourceSnapshotDestroyQuery(path=snap),
                                )
                            except Exception:
                                self.logger.exception('Failed to destroy snapshot %r for zvol %r', snap, clone)
            raise e

        self.logger.info('VM cloned from %r to %r', origin_name, vm['name'])
        return True

    @private
    async def validate(self, vm):
        verrors = ValidationErrors()
        for index, device in enumerate(vm['devices']):
            if device['attributes']['dtype'] == 'DISPLAY' and not device['attributes'].get('password'):
                verrors.add(
                    f'vm.devices.{index}.attributes.password',
                    'Password must be configured for display device in order to clone the VM.'
                )

        verrors.check()
