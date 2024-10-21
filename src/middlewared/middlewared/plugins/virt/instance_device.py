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
        instance = await self.middleware.call('virt.instance.get_instance', id)

        # Grab devices from default profile (e.g. nic and disk)
        profile = await self.middleware.call('virt.global.get_default_profile')

        # Flag devices from the profile as readonly, cannot be modified only overridden
        raw_devices = profile['devices']
        for v in raw_devices.values():
            v['readonly'] = True

        raw_devices.update(instance['raw']['devices'])

        devices = []
        for k, v in raw_devices.items():
            if (device := await self.incus_to_device(k, v)) is not None:
                devices.append(device)

        return devices

    @private
    async def incus_to_device(self, name: str, incus: dict[str, Any]):
        device = {'name': name, 'readonly': incus.get('readonly') or False}

        def unsupported():
            self.logger.trace('Proxy device not supported by API, skipping.')
            return None

        match incus['type']:
            case 'disk':
                device['dev_type'] = 'DISK'
                device['source'] = incus.get('source')
                device['destination'] = incus.get('path')
            case 'nic':
                device['dev_type'] = 'NIC'
                device['network'] = incus.get('network')
            case 'proxy':
                device['dev_type'] = 'PROXY'
                # For now follow docker lead for simplification
                # only allowing to bind on host (host -> container)
                if incus.get('bind') == 'instance':
                    return unsupported()

                proto, addr, ports = incus['listen'].split(':')
                if proto == 'unix' or '-' in ports or ',' in ports:
                    return unsupported()

                device['source_proto'] = proto.upper()
                device['source_port'] = int(ports)

                proto, addr, ports = incus['connect'].split(':')
                if proto == 'unix' or '-' in ports or ',' in ports:
                    return unsupported()

                device['dest_proto'] = proto.upper()
                device['dest_port'] = int(ports)
            case 'tpm':
                device['dev_type'] = 'TPM'
                device['path'] = incus.get('path')
                device['pathrm'] = incus.get('pathrm')
            case 'usb':
                device['dev_type'] = 'USB'
                if incus.get('busnum') is not None:
                    device['bus'] = int(incus['busnum'])
                if incus.get('devnum') is not None:
                    device['dev'] = int(incus['devnum'])
                if incus.get('productid') is not None:
                    device['product_id'] = incus['productid']
                if incus.get('vendorid') is not None:
                    device['vendir_id'] = incus['vendorid']
            case 'gpu':
                device['dev_type'] = 'USB'
                device['id'] = incus['id']
                device['gpu_type'] = incus['gputype'].upper()
                match incus['gputype']:
                    case 'physical':
                        pass
                    case 'mdev':
                        pass
                    case 'mig':
                        device['mig_uuid'] = incus['mig.uuid']
                    case 'sriov':
                        pass
            case _:
                return unsupported()

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

    async def __generate_device_name(self, device_names: list[str], device_type: str) -> str:
        name = device_type.lower()
        i = 0
        while True:
            new_name = f'{name}{i}'
            if new_name not in device_names:
                name = new_name
                break
            i += 1
        return name

    async def __validate_device(self, device, schema, verrors: ValidationErrors):
        match device['dev_type']:
            case 'PROXY':
                verror = await self.middleware.call('port.validate_port', schema, device['source_port'])
                verrors.extend(verror)
            case 'DISK':
                if device['source'] and device['source'].startswith('/dev/zvol/'):
                    if device['source'] not in await self.middleware.call('virt.device.disk_choices'):
                        verrors.add(schema, 'Invalid ZVOL choice.')

    @api_method(VirtInstanceDeviceAddArgs, VirtInstanceDeviceAddResult, roles=['VIRT_INSTANCE_WRITE'])
    async def device_add(self, id, device):
        """
        Add a device to an instance.
        """
        instance = await self.middleware.call('virt.instance.get_instance', id)
        data = instance['raw']
        if device['name'] is None:
            device['name'] = await self.__generate_device_name(data['devices'].keys(), device['dev_type'])

        verrors = ValidationErrors()
        await self.__validate_device(device, 'virt_device_add', verrors)
        verrors.check()

        data['devices'][device['name']] = await self.device_to_incus(instance['type'], device)
        await incus_call_and_wait(f'1.0/instances/{id}', 'put', {'json': data})
        return True

    @api_method(VirtInstanceDeviceDeleteArgs, VirtInstanceDeviceDeleteResult, roles=['VIRT_INSTANCE_DELETE'])
    async def device_delete(self, id, device):
        """
        Delete a device from an instance.
        """
        instance = await self.middleware.call('virt.instance.get_instance', id)
        data = instance['raw']
        if device not in data['devices']:
            raise CallError('Device not found.', errno.ENOENT)
        data['devices'].pop(device)
        await incus_call_and_wait(f'1.0/instances/{id}', 'put', {'json': data})
        return True
