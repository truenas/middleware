import errno
import os
from typing import Any

from middlewared.service import (
    CallError, Service, ValidationErrors, private
)

from middlewared.api import api_method
from middlewared.api.current import (
    VirtInstanceDeviceListArgs, VirtInstanceDeviceListResult,
    VirtInstanceDeviceAddArgs, VirtInstanceDeviceAddResult,
    VirtInstanceDeviceDeleteArgs, VirtInstanceDeviceDeleteResult,
    VirtInstanceDeviceUpdateArgs, VirtInstanceDeviceUpdateResult,
)
from middlewared.async_validators import check_path_resides_within_volume
from .utils import incus_call_and_wait, storage_pool_to_incus_pool, incus_pool_to_storage_pool


class VirtInstanceDeviceService(Service):

    class Config:
        namespace = 'virt.instance'
        cli_namespace = 'virt.instance'

    @api_method(VirtInstanceDeviceListArgs, VirtInstanceDeviceListResult, roles=['VIRT_INSTANCE_READ'])
    async def device_list(self, id):
        """
        List all devices associated to an instance.
        """
        instance = await self.middleware.call('virt.instance.get_instance', id, {'extra': {'raw': True}})
        instance_profiles = instance['raw']['profiles']
        raw_devices = {}

        # An incus instance may have more than one profile applied to it.
        for profile in instance_profiles:
            profile_devs = (await self.middleware.call('virt.global.get_profile', profile))['devices']
            # Flag devices from the profile as readonly, cannot be modified only overridden
            for v in profile_devs.values():
                v['readonly'] = True

            raw_devices |= profile_devs

        raw_devices.update(instance['raw']['devices'])

        devices = []
        context = {}
        for k, v in raw_devices.items():
            if (device := await self.incus_to_device(k, v, context)) is not None:
                devices.append(device)

        return devices

    @private
    def unsupported(self):
        self.logger.trace('Proxy device not supported by API, skipping.')
        return None

    @private
    async def incus_to_device(self, name: str, incus: dict[str, Any], context: dict):
        device = {
            'name': name,
            'description': None,
            'readonly': incus.get('readonly') or False,
        }

        match incus['type']:
            case 'disk':
                device.update({
                    'dev_type': 'DISK',
                    'source': incus.get('source'),
                    'storage_pool': incus_pool_to_storage_pool(incus.get('pool')),
                    'destination': incus.get('path'),
                    'description': f'{incus.get("source")} -> {incus.get("path")}',
                    'boot_priority': int(incus['boot.priority']) if incus.get('boot.priority') else None,
                    'io_bus': incus['io.bus'].upper() if incus.get('io.bus') else None,
                })
            case 'nic':
                device['dev_type'] = 'NIC'
                device['network'] = incus.get('network')
                if device['network']:
                    device['parent'] = None
                    device['nic_type'] = None
                elif incus.get('nictype'):
                    device['nic_type'] = incus.get('nictype').upper()
                    device['parent'] = incus.get('parent')
                device['description'] = device['network']
            case 'proxy':
                device['dev_type'] = 'PROXY'
                # For now follow docker lead for simplification
                # only allowing to bind on host (host -> container)
                if incus.get('bind') == 'instance':
                    return self.unsupported()

                proto, addr, ports = incus['listen'].split(':')
                if proto == 'unix' or '-' in ports or ',' in ports:
                    return self.unsupported()

                device['source_proto'] = proto.upper()
                device['source_port'] = int(ports)

                proto, addr, ports = incus['connect'].split(':')
                if proto == 'unix' or '-' in ports or ',' in ports:
                    return self.unsupported()

                device['dest_proto'] = proto.upper()
                device['dest_port'] = int(ports)

                device['description'] = f'{device["source_proto"]}/{device["source_port"]} -> {device["dest_proto"]}/{device["dest_port"]}'
            case 'tpm':
                device['dev_type'] = 'TPM'
                device['path'] = incus.get('path')
                device['pathrm'] = incus.get('pathrm')
                device['description'] = 'TPM'
            case 'usb':
                device['dev_type'] = 'USB'
                if incus.get('busnum') is not None:
                    device['bus'] = int(incus['busnum'])
                if incus.get('devnum') is not None:
                    device['dev'] = int(incus['devnum'])
                if incus.get('productid') is not None:
                    device['product_id'] = incus['productid']
                if incus.get('vendorid') is not None:
                    device['vendor_id'] = incus['vendorid']

                if 'usb_choices' not in context:
                    context['usb_choices'] = await self.middleware.call('virt.device.usb_choices')

                for choice in context['usb_choices'].values():
                    if device.get('bus') and choice['bus'] != device['bus']:
                        continue
                    if device.get('dev') and choice['dev'] != device['dev']:
                        continue
                    if device.get('product_id') and choice['product_id'] != device['product_id']:
                        continue
                    if device.get('vendor_id') and choice['vendor_id'] != device['product_id']:
                        continue
                    device['description'] = f'{choice["product"]} ({choice["vendor_id"]}:{choice["product_id"]})'
                    break
                else:
                    device['description'] = 'Unknown'
            case 'gpu':
                device['dev_type'] = 'GPU'
                device['gpu_type'] = incus['gputype'].upper()
                match incus['gputype']:
                    case 'physical':
                        device['pci'] = incus['pci']
                        if 'gpu_choices' not in context:
                            context['gpu_choices'] = await self.middleware.call('virt.device.gpu_choices', 'PHYSICAL')
                        for key, choice in context['gpu_choices'].items():
                            if key == incus['pci']:
                                device['description'] = choice['description']
                                break
                        else:
                            device['description'] = 'Unknown'
                    case 'mdev' | 'mig' | 'srviov':
                        return self.unsupported()
            case 'pci':
                if 'pci_choices' not in context:
                    context['pci_choices'] = await self.middleware.call('virt.device.pci_choices')

                device.update({
                    'dev_type': 'PCI',
                    'address': incus['address'],
                    'description': context['pci_choices'].get(incus['address'], {}).get('description', 'Unknown')
                })
            case _:
                return self.unsupported()

        return device

    @private
    async def device_to_incus(self, instance_type: str, device: dict[str, Any]) -> dict[str, Any]:
        new = {}

        match device['dev_type']:
            case 'DISK':
                new.update({
                    'type': 'disk',
                    'source': device['source'],
                    'path': device['destination'],
                })
                if device['boot_priority'] is not None:
                    new['boot.priority'] = str(device['boot_priority'])
                if '/' not in new['source']:
                    if zpool := device.get('storage_pool'):
                        new['pool'] = storage_pool_to_incus_pool(device.get('storage_pool'))
                    else:
                        new['pool'] = None
                if device.get('io_bus'):
                    new['io.bus'] = device['io_bus'].lower()

            case 'NIC':
                new['type'] = 'nic'
                new['network'] = device['network']
                new['nictype'] = device['nic_type'].lower()
                new['parent'] = device['parent']
            case 'PROXY':
                new['type'] = 'proxy'
                # For now follow docker lead for simplification
                # only allowing to bind on host (host -> container)
                new['bind'] = 'host'
                new['listen'] = f'{device["source_proto"].lower()}:0.0.0.0:{device["source_port"]}'
                new['connect'] = f'{device["dest_proto"].lower()}:0.0.0.0:{device["dest_port"]}'
            case 'USB':
                new['type'] = 'usb'
                if device.get('bus') is not None:
                    new['busnum'] = str(device['bus'])
                if device.get('dev') is not None:
                    new['devnum'] = str(device['dev'])
                if device.get('product_id') is not None:
                    new['productid'] = device['product_id']
                if device.get('vendor_id') is not None:
                    new['vendorid'] = device['vendor_id']
            case 'TPM':
                new['type'] = 'tpm'
                if device.get('path'):
                    if instance_type == 'VM':
                        raise CallError('Path is not valid for VM')
                    new['path'] = device['path']
                elif instance_type == 'CONTAINER':
                    new['path'] = '/dev/tpm0'

                if device.get('pathrm'):
                    if instance_type == 'VM':
                        raise CallError('Pathrm is not valid for VM')
                    new['pathrm'] = device['pathrm']
                elif instance_type == 'CONTAINER':
                    new['pathrm'] = '/dev/tpmrm0'
            case 'GPU':
                new['type'] = 'gpu'
                # new['id'] = device['id']
                match device['gpu_type']:
                    case 'PHYSICAL':
                        new['gputype'] = 'physical'
                        new['pci'] = device['pci']
                    case 'MDEV':
                        new['gputype'] = 'mdev'
                    case 'MIG':
                        new['gputype'] = 'mig'
                        if not device.get('mig_uuid'):
                            raise CallError('UUID is required for MIG')
                        new['mig.uuid'] = device['mig_uuid']
                    case 'SRIOV':
                        new['gputype'] = 'sriov'
            case 'PCI':
                new.update({
                    'type': 'pci',
                    'address': device['address'],
                })
            case _:
                raise Exception('Invalid device type')
        return new

    @private
    async def generate_device_name(self, device_names: list[str], device_type: str) -> str:
        name = device_type.lower()
        if name == 'nic':
            name = 'eth'
        i = 0
        while True:
            new_name = f'{name}{i}'
            if new_name not in device_names:
                name = new_name
                break
            i += 1
        return name

    @private
    async def validate_devices(self, devices, schema, verrors: ValidationErrors):
        unique_src_proxies = []
        unique_dst_proxies = []

        for device in devices:
            match device['dev_type']:
                case 'PROXY':
                    source = (device['source_proto'], device['source_port'])
                    if source in unique_src_proxies:
                        verrors.add(f'{schema}.source_port', 'Source proto/port already in use.')
                    else:
                        unique_src_proxies.append(source)
                    dst = (device['dest_proto'], device['dest_port'])
                    if dst in unique_dst_proxies:
                        verrors.add(f'{schema}.dest_port', 'Destination proto/port already in use.')
                    else:
                        unique_dst_proxies.append(dst)

    @private
    async def validate_device(
        self, device, schema, verrors: ValidationErrors, instance_type: str, old: dict = None,
        instance_config: dict = None,
    ):
        match device['dev_type']:
            case 'PROXY':
                # Skip validation if we are updating and port has not changed
                if old and old['source_port'] == device['source_port']:
                    return
                # We want to make sure there are no other instances using that port
                ports = await self.middleware.call('port.ports_mapping')
                for attachment in ports.get(device['source_port'], {}).values():
                    # Only add error if the port is not in use by current instance
                    if instance_config is None or attachment['namespace'] != 'virt' or any(
                        True for i in attachment['port_details'] if i['instance'] != instance_config['name']
                    ):
                        verror = await self.middleware.call(
                            'port.validate_port', schema, device['source_port'],
                        )
                        verrors.extend(verror)
                        break
            case 'DISK':
                source = device['source'] or ''
                if source == '':
                    verrors.add(schema, 'Source is required.')
                elif source.startswith('/'):
                    if source.startswith('/dev/zvol/') and source not in await self.middleware.call(
                        'virt.device.disk_choices_internal', True
                    ):
                        verrors.add(schema, 'Invalid ZVOL choice.')

                    if instance_type == 'CONTAINER':
                        if device['boot_priority'] is not None:
                            verrors.add(schema, 'Boot priority is not valid for filesystem paths.')
                        if source.startswith('/dev/zvol/'):
                            verrors.add(schema, 'ZVOL are not allowed for containers')

                        if await self.middleware.run_in_thread(os.path.exists, source) is False:
                            verrors.add(schema, 'Source path does not exist.')
                        if not device.get('destination'):
                            verrors.add(schema, 'Destination is required for filesystem paths.')
                        else:
                            if device['destination'].startswith('/') is False:
                                verrors.add(schema, 'Destination must be an absolute path.')

                            if not source.startswith('/dev/zvol'):
                                # Verify that path resolves to an expected data pool
                                await check_path_resides_within_volume(
                                    verrors, self.middleware, schema, source, True
                                )

                                # Limit paths to mountpoints because they're much harder for arbitrary
                                # processes to maliciously replace
                                st = await self.middleware.call('filesystem.stat', source)
                                if not st['is_mountpoint']:
                                    verrors.add(schema, 'Source must be a dataset mountpoint.')

                    else:
                        if source.startswith('/dev/zvol/') is False:
                            verrors.add(
                                schema, 'Source must be a path starting with /dev/zvol/ for VM or a virt volume name.'
                            )
                else:
                    if instance_type == 'CONTAINER':
                        verrors.add(schema, 'Source must be a filesystem path for CONTAINER')
                    else:
                        available_volumes = {v['id']: v for v in await self.middleware.call('virt.volume.query')}
                        if source not in available_volumes:
                            verrors.add(schema, f'No {source!r} incus volume found which can be used for source')
                        elif available_volumes[source]['content_type'] == 'ISO' and device['boot_priority'] is None:
                            verrors.add(schema, 'Boot priority is required for ISO volumes.')
                        else:
                            # We need to specify the storage pool for device adding to VM
                            # copy in what is known for the virt volume
                            device['storage_pool'] = available_volumes[source]['storage_pool']

                destination = device.get('destination')
                if destination == '/':
                    verrors.add(schema, 'Destination cannot be /')
                if destination and instance_type == 'VM':
                    verrors.add(schema, 'Destination is not valid for VM')
                if device.get('io_bus'):
                    if instance_type != 'VM':
                        verrors.add(f'{schema}.io_bus', 'IO bus is only available for VMs')
                    elif instance_config and instance_config['status'] != 'STOPPED':
                        verrors.add(f'{schema}.io_bus', 'VM should be stopped before updating IO bus')

            case 'NIC':
                if await self.middleware.call('interface.has_pending_changes'):
                    raise CallError('There are pending network changes, please resolve before proceeding.')
                if device['nic_type'] == 'BRIDGED':
                    if await self.middleware.call('failover.licensed'):
                        verrors.add(schema, 'Bridge interface not allowed for HA')
                    choices = await self.middleware.call('virt.device.nic_choices', device['nic_type'])
                    if device['parent'] not in choices:
                        verrors.add(schema, 'Invalid parent interface')
            case 'GPU':
                if instance_config and instance_type == 'VM' and instance_config['status'] == 'RUNNING':
                    verrors.add('virt.device.gpu_choices', 'VM must be stopped before adding a GPU device')
            case 'PCI':
                if device['address'] not in await self.middleware.call('virt.device.pci_choices'):
                    verrors.add(f'{schema}.address', f'Invalid PCI {device["address"]!r} address.')
                if instance_type != 'VM':
                    verrors.add(schema, 'PCI passthrough is only supported for vms')

    @api_method(VirtInstanceDeviceAddArgs, VirtInstanceDeviceAddResult, roles=['VIRT_INSTANCE_WRITE'])
    async def device_add(self, id, device):
        """
        Add a device to an instance.
        """
        instance = await self.middleware.call('virt.instance.get_instance', id, {'extra': {'raw': True}})
        data = instance['raw']
        if device['name'] is None:
            device['name'] = await self.generate_device_name(data['devices'].keys(), device['dev_type'])

        verrors = ValidationErrors()
        await self.validate_device(device, 'virt_device_add', verrors, instance['type'], instance_config=instance)
        verrors.check()

        data['devices'][device['name']] = await self.device_to_incus(instance['type'], device)
        await incus_call_and_wait(f'1.0/instances/{id}', 'put', {'json': data})
        return True

    @api_method(VirtInstanceDeviceUpdateArgs, VirtInstanceDeviceUpdateResult, roles=['VIRT_INSTANCE_WRITE'])
    async def device_update(self, id, device):
        """
        Update a device in an instance.
        """
        instance = await self.middleware.call('virt.instance.get_instance', id, {'extra': {'raw': True}})
        data = instance['raw']

        for old in await self.device_list(id):
            if old['name'] == device['name']:
                break
        else:
            raise CallError('Device does not exist.', errno.ENOENT)

        verrors = ValidationErrors()
        await self.validate_device(device, 'virt_device_update', verrors, instance['type'], old, instance)
        verrors.check()

        data['devices'][device['name']] = await self.device_to_incus(instance['type'], device)
        await incus_call_and_wait(f'1.0/instances/{id}', 'put', {'json': data})
        return True

    @api_method(VirtInstanceDeviceDeleteArgs, VirtInstanceDeviceDeleteResult, roles=['VIRT_INSTANCE_DELETE'])
    async def device_delete(self, id, device):
        """
        Delete a device from an instance.
        """
        instance = await self.middleware.call('virt.instance.get_instance', id, {'extra': {'raw': True}})
        data = instance['raw']
        if device not in data['devices']:
            raise CallError('Device not found.', errno.ENOENT)
        data['devices'].pop(device)
        await incus_call_and_wait(f'1.0/instances/{id}', 'put', {'json': data})
        return True
