import errno
import re
import uuid

from middlewared.api import api_method
from middlewared.api.current import VMCloneArgs, VMCloneResult
from middlewared.plugins.zfs_.utils import zvol_name_to_path, zvol_path_to_name
from middlewared.service import CallError, item_method, Service, private
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
        if not await self.middleware.call('zfs.dataset.query', [('id', '=', zvol)]):
            raise CallError(f'zvol {zvol} does not exist.', errno.ENOENT)

        snapshot_name = name
        i = 0
        while True:
            zvol_snapshot = f'{zvol}@{snapshot_name}'
            if await self.middleware.call('zfs.snapshot.query', [('id', '=', zvol_snapshot)]):
                if ZVOL_CLONE_RE.search(snapshot_name):
                    snapshot_name = ZVOL_CLONE_RE.sub(rf'\1{ZVOL_CLONE_SUFFIX}{i}', snapshot_name)
                else:
                    snapshot_name = f'{name}{ZVOL_CLONE_SUFFIX}{i}'
                i += 1
                continue
            break

        await self.middleware.call('zfs.snapshot.create', {'dataset': zvol, 'name': snapshot_name})
        created_snaps.append(zvol_snapshot)

        clone_suffix = name
        i = 0
        while True:
            clone_dst = f'{zvol}_{clone_suffix}'
            if await self.middleware.call('zfs.dataset.query', [('id', '=', clone_dst)]):
                if ZVOL_CLONE_RE.search(clone_suffix):
                    clone_suffix = ZVOL_CLONE_RE.sub(rf'\1{ZVOL_CLONE_SUFFIX}{i}', clone_suffix)
                else:
                    clone_suffix = f'{name}{ZVOL_CLONE_SUFFIX}{i}'
                i += 1
                continue
            break

        await self.middleware.call('zfs.snapshot.clone', {'snapshot': zvol_snapshot, 'dataset_dst': clone_dst})

        created_clones.append(clone_dst)

        return clone_dst

    @item_method
    @api_method(VMCloneArgs, VMCloneResult, roles=['VM_WRITE'])
    async def clone(self, id_, name):
        """
        Clone the VM `id`.

        `name` is an optional parameter for the cloned VM.
        If not provided it will append the next number available to the VM name.
        """
        raise CallError('Cloning legacy VMs is not supported on this system')
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
            for i in reversed(created_clones):
                try:
                    await self.middleware.call('zfs.dataset.delete', i)
                except Exception:
                    self.logger.warning('Rollback of VM clone left dangling zvol: %s', i)
            for i in reversed(created_snaps):
                try:
                    dataset, snap = i.split('@')
                    await self.middleware.call('zfs.snapshot.remove', {
                        'dataset': dataset,
                        'name': snap,
                        'defer_delete': True,
                    })
                except Exception:
                    self.logger.warn('Rollback of VM clone left dangling snapshot: %s', i)
            raise e
        self.logger.info('VM cloned from {0} to {1}'.format(origin_name, vm['name']))

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
