import aiohttp
import errno
from typing import Any, List

from middlewared.service import (
    CallError, CRUDService, ValidationErrors, filterable, job, private
)
from middlewared.utils import filter_list

from middlewared.api import api_method
from middlewared.api.current import (
    VirtInstanceEntry,
    VirtInstanceCreateArgs, VirtInstanceCreateResult,
    VirtInstanceUpdateArgs, VirtInstanceUpdateResult,
    VirtInstanceDeleteArgs, VirtInstanceDeleteResult,
    VirtInstanceStateArgs, VirtInstanceStateResult,
    VirtInstanceImageChoicesArgs, VirtInstanceImageChoicesResult,
    VirtInstanceDeviceListArgs, VirtInstanceDeviceListResult,
    VirtInstanceDeviceAddArgs, VirtInstanceDeviceAddResult,
    VirtInstanceDeviceDeleteArgs, VirtInstanceDeviceDeleteResult,
)
from .utils import incus_call, incus_call_and_wait


LC_IMAGES_SERVER = 'https://images.linuxcontainers.org'
LC_IMAGES_JSON = f'{LC_IMAGES_SERVER}/streams/v1/images.json'


class VirtInstanceService(CRUDService):

    class Config:
        namespace = 'virt.instance'
        cli_namespace = 'virt.instance'
        entry = VirtInstanceEntry
        role_prefix = 'VIRT_INSTANCE'

    @filterable
    async def query(self, filters, options):
        """
        Query all instances with `query-filters` and `query-options`.
        """
        results = (await incus_call('1.0/instances?filter=&recursion=2', 'get'))['metadata']
        entries = []
        for i in results:
            # If entry has no config or state its probably in an unknown state, skip it
            if not i.get('config') or not i.get('state'):
                continue
            entry = {
                'id': i['name'],
                'name': i['name'],
                'type': 'CONTAINER' if i['type'] == 'container' else 'VM',
                'status': i['state']['status'].upper(),
                'cpu': i['config'].get('limits.cpu'),
                'autostart': i['config'].get('boot.autostart') or False,
                'environment': {},
                'raw': i,
                'aliases': [],
            }

            if memory := i['config'].get('limits.memory'):
                # Handle all units? e.g. changes done through CLI
                if memory.endswith('MiB'):
                    memory = int(memory[:-3]) * 1024 * 1024
                else:
                    memory = None
            entry['memory'] = memory

            for k, v in i['config'].items():
                if not k.startswith('environment.'):
                    continue
                entry['environment'][k[12:]] = v
            entries.append(entry)

            for v in (i['state']['network'] or {}).values():
                for address in v['addresses']:
                    if address['scope'] != 'global':
                        continue
                    entry['aliases'].append({
                        'type': address['family'].upper(),
                        'address': address['address'],
                        'netmask': int(address['netmask']),
                    })

        return filter_list(entries, filters, options)

    @private
    async def validate(self, new, schema_name, verrors, old=None):
        if not old and await self.query([('name', '=', new['name'])]):
            verrors.add(f'{schema_name}.name', f'Name {new["name"]!r} already exists')

        # Do not validate image_choices because its an expansive operation, just fail on creation

    def __data_to_config(self, data):
        config = {}
        if data.get('environment'):
            for k, v in data['environment'].items():
                config[f'environment.{k}'] = v
        if data.get('cpu'):
            config['limits.cpu'] = data['cpu']

        if data.get('memory'):
            config['limits.memory'] = str(data['memory']) + 'MiB'

        if data.get('autostart') is not None:
            config['boot.autostart'] = str(data['autostart']).lower()
        return config

    @api_method(VirtInstanceImageChoicesArgs, VirtInstanceImageChoicesResult)
    async def image_choices(self, data):
        """
        Provice choices for instance image from a remote repository.
        """
        choices = {}
        if data['remote'] in (None, 'LINUX_CONTAINERS'):
            url = LC_IMAGES_JSON
        else:
            raise CallError('Invalid remote')
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.json()
                for v in data['products'].values():
                    alias = v['aliases'].split(',', 1)[0]
                    choices[alias] = {
                        'label': f'{v["os"]} {v["release"]} ({v["arch"]}, {v["variant"]})',
                        'os': v['os'],
                        'release': v['release'],
                        'arch': v['arch'],
                        'variant': v['variant'],
                    }
        return choices

    @api_method(VirtInstanceCreateArgs, VirtInstanceCreateResult)
    @job()
    async def do_create(self, job, data):
        """
        Create a new virtualizated instance.
        """

        verrors = ValidationErrors()
        await self.validate(data, 'virt_instance_create', verrors)

        devices = {}
        for i in (data['devices'] or []):
            await self.__validate_device(i, 'virt_instance_create', verrors)
            devices[i['name']] = await self.__device_to_incus(data['instance_type'], i)

        verrors.check()

        async def running_cb(data):
            if 'metadata' in data['metadata'] and (metadata := data['metadata']['metadata']):
                if 'download_progress' in metadata:
                    job.set_progress(None, metadata['download_progress'])
                if 'create_instance_from_image_unpack_progress' in metadata:
                    job.set_progress(None, metadata['create_instance_from_image_unpack_progress'])

        if data['remote'] in (None, 'LINUX_CONTAINERS'):
            url = LC_IMAGES_SERVER
        else:
            raise CallError('Invalid remote')

        source = {
            'type': 'image',
        }

        result = await incus_call(f'1.0/images/{data["image"]}', 'get')
        if result['status_code'] == 200:
            source['fingerprint'] = result['metadata']['fingerprint']
        else:
            source.update({
                'server': url,
                'protocol': 'simplestreams',
                'mode': 'pull',
                'alias': data['image'],
            })

        await incus_call_and_wait('1.0/instances', 'post', {'json': {
            'name': data['name'],
            'ephemeral': False,
            'config': self.__data_to_config(data),
            'devices': devices,
            'source': source,
            'type': 'container' if data['instance_type'] == 'CONTAINER' else 'virtual-machine',
            'start': True,
        }}, running_cb)

        return await self.middleware.call('virt.instance.get_instance', data['name'])

    @api_method(VirtInstanceUpdateArgs, VirtInstanceUpdateResult)
    @job()
    async def do_update(self, job, id, data):
        """
        Update instance.
        """
        instance = await self.middleware.call('virt.instance.get_instance', id)

        verrors = ValidationErrors()
        await self.validate(data, 'virt_instance_create', verrors, old=instance)
        verrors.check()

        instance['raw']['config'].update(self.__data_to_config(data))
        await incus_call_and_wait(f'1.0/instances/{id}', 'put', {'json': instance['raw']})

        return await self.middleware.call('virt.instance.get_instance', id)

    @api_method(VirtInstanceDeleteArgs, VirtInstanceDeleteResult)
    @job()
    async def do_delete(self, job, id):
        """
        Delete an instance.
        """
        instance = await self.middleware.call('virt.instance.get_instance', id)
        if instance['status'] == 'RUNNING':
            await incus_call_and_wait(f'1.0/instances/{id}/state', 'put', {'json': {
                'action': 'stop',
                'timeout': -1,
                'force': True,
            }})

        await incus_call_and_wait(f'1.0/instances/{id}', 'delete')

        return True

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
            if (device := await self.__incus_to_device(k, v)) is not None:
                devices.append(device)

        return devices

    async def __incus_to_device(self, name: str, incus: dict[str, Any]):
        device = {'name': name, 'readonly': incus.get('readonly') or False}

        def unsupported():
            self.logger.warning('Proxy device not supported by API, skipping.')
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

    async def __device_to_incus(self, instance_type: str, device: dict[str, Any]) -> dict[str, Any]:
        new = {}

        match device['dev_type']:
            case 'DISK':
                new['type'] = 'disk'
                source = device.get('source') or ''
                if not source.startswith(('/dev/zvol/', '/mnt/')):
                    raise CallError('Only pool paths are allowed.')
                new['source'] = device['source']
                if source.startswith('/mnt/'):
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

    async def __generate_device_name(self, device_names: List[str], device_type: str) -> str:
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

        data['devices'][device['name']] = await self.__device_to_incus(instance['type'], device)
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

    @api_method(VirtInstanceStateArgs, VirtInstanceStateResult, roles=['VIRT_INSTANCE_WRITE'])
    @job()
    async def state(self, job, id, action, force):
        """
        Change state of an instance.
        """
        await incus_call_and_wait(f'1.0/instances/{id}/state', 'put', {'json': {
            'action': action.lower(),
            'timeout': -1,
            'force': force,
        }})

        return True
