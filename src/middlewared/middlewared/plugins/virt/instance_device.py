import errno
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
from .utils import incus_call_and_wait


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

        # Grab devices from default profile (e.g. nic and disk)
        profile = await self.middleware.call('virt.global.get_default_profile')

        # Flag devices from the profile as readonly, cannot be modified only overridden
        raw_devices = profile['devices']
        for v in raw_devices.values():
            v['readonly'] = True

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
                device['dev_type'] = 'DISK'
                device['source'] = incus.get('source')
                device['destination'] = incus.get('path')
                device['description'] = f'{device["source"]} -> {device["destination"]}'
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
                device['dev_type'] = 'USB'
                device['gpu_type'] = incus['gputype'].upper()
                match incus['gputype']:
                    case 'physical':
                        device['pci'] = incus['pci']
                        if 'gpu_choices' not in context:
                            context['gpu_choices'] = await self.middleware.call(
                                'virt.device.gpu_choices', 'CONTAINER', 'PHYSICAL',
                            )
                        for key, choice in context['gpu_choices'].items():
                            if key == incus['pci']:
                                device['description'] = choice['description']
                                break
                        else:
                            device['description'] = 'Unknown'
                    case 'mdev' | 'mig' | 'srviov':
                        return self.unsupported()
            case _:
                return self.unsupported()

        return device

    @private
    async def device_to_incus(self, instance_type: str, device: dict[str, Any]) -> dict[str, Any]:
        new = {}

        match device['dev_type']:
            case 'DISK':
                new['type'] = 'disk'
                source = device.get('source') or ''
                if not source.startswith(('/dev/zvol/', '/mnt/')):
                    raise CallError('Only pool paths are allowed.')
                new['source'] = device['source']
                if source.startswith('/mnt/'):
                    if source.startswith('/mnt/.ix-apps'):
                        raise CallError('Invalid source')
                    if not device.get('destination'):
                        raise CallError('Destination is required for filesystem paths.')
                    if instance_type == 'VM':
                        raise CallError('Destination is not valid for VM')
                new['path'] = device['destination']
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
    async def validate_device(self, device, schema, verrors: ValidationErrors, old: dict = None, instance: str = None):
        match device['dev_type']:
            case 'PROXY':
                # Skip validation if we are updating and port has not changed
                if old and old['source_port'] == device['source_port']:
                    return
                # We want to make sure there are no other instances using that port
                ports = await self.middleware.call('port.ports_mapping')
                for attachment in ports.get(device['source_port'], {}).values():
                    # Only add error if the port is not in use by current instance
                    if instance is None or attachment['namespace'] != 'virt.device' or any(True for i in attachment['port_details'] if i['instance'] != instance):
                        verror = await self.middleware.call(
                            'port.validate_port', schema, device['source_port'],
                        )
                        verrors.extend(verror)
                        break
            case 'DISK':
                if device['source'] and device['source'].startswith('/dev/zvol/'):
                    if device['source'] not in await self.middleware.call('virt.device.disk_choices'):
                        verrors.add(schema, 'Invalid ZVOL choice.')
            case 'NIC':
                if await self.middleware.call('interface.has_pending_changes'):
                    raise CallError('There are pending network changes, please resolve before proceeding.')
                if device['nic_type'] == 'BRIDGED':
                    if await self.middleware.call('failover.licensed'):
                        verrors.add(schema, 'Bridge interface not allowed for HA')
                    choices = await self.middleware.call('virt.device.nic_choices', device['nic_type'])
                    if device['parent'] not in choices:
                        verrors.add(schema, 'Invalid parent interface')

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
        await self.validate_device(device, 'virt_device_add', verrors)
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
        await self.validate_device(device, 'virt_device_update', verrors, old, instance['name'])
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
