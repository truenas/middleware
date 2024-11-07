import aiohttp
import platform

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
    VirtInstanceStartArgs, VirtInstanceStartResult,
    VirtInstanceStopArgs, VirtInstanceStopResult,
    VirtInstanceRestartArgs, VirtInstanceRestartResult,
    VirtInstanceImageChoicesArgs, VirtInstanceImageChoicesResult,
)
from .utils import Status, incus_call, incus_call_and_wait


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
        if not options['extra'].get('skip_state'):
            config = await self.middleware.call('virt.global.config')
            if config['state'] != Status.INITIALIZED.value:
                return []
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
                'autostart': True if i['config'].get('boot.autostart') == 'true' else False,
                'environment': {},
                'aliases': [],
                'image': {
                    'architecture': i['config'].get('image.architecture'),
                    'description': i['config'].get('image.description'),
                    'os': i['config'].get('image.os'),
                    'release': i['config'].get('image.release'),
                    'serial': i['config'].get('image.serial'),
                    'type': i['config'].get('image.type'),
                    'variant': i['config'].get('image.variant'),
                }
            }

            if options['extra'].get('raw'):
                entry['raw'] = i

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

        if memory := new.get('memory'):
            # Lets require at least 32MiB of reserved memory
            # This value is somewhat arbitrary but hard to think lower value would have to be used
            # (would most likely be a typo).
            # Running container with very low memory will probably cause it to be killed by the cgroup OOM
            if memory < 33554432:
                verrors.add(f'{schema_name}.memory', 'At least 32MiB of memory is required for a container')

        # Do not validate image_choices because its an expansive operation, just fail on creation

    def __data_to_config(self, data):
        config = {}
        if data.get('environment'):
            for k, v in data['environment'].items():
                config[f'environment.{k}'] = v
        if data.get('cpu'):
            config['limits.cpu'] = data['cpu']

        if data.get('memory'):
            config['limits.memory'] = str(int(data['memory'] / 1024 / 1024)) + 'MiB'

        if data.get('autostart') is not None:
            config['boot.autostart'] = str(data['autostart']).lower()
        return config

    @api_method(VirtInstanceImageChoicesArgs, VirtInstanceImageChoicesResult, roles=['VIRT_INSTANCE_READ'])
    async def image_choices(self, data):
        """
        Provice choices for instance image from a remote repository.
        """
        choices = {}
        if data['remote'] == 'LINUX_CONTAINERS':
            url = LC_IMAGES_JSON

        current_arch = platform.machine()
        if current_arch == 'x86_64':
            current_arch = 'amd64'

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                for v in (await resp.json())['products'].values():
                    # For containers we only want images matching current platform
                    if data['instance_type'] == 'CONTAINER' and v['arch'] != current_arch:
                        continue
                    alias = v['aliases'].split(',', 1)[0]
                    if alias not in choices:
                        choices[alias] = {
                            'label': f'{v["os"]} {v["release"]} ({v["arch"]}, {v["variant"]})',
                            'os': v['os'],
                            'release': v['release'],
                            'archs': [v['arch']],
                            'variant': v['variant'],
                        }
                    else:
                        choices[alias]['archs'].append(v['arch'])
        return choices

    @api_method(VirtInstanceCreateArgs, VirtInstanceCreateResult)
    @job()
    async def do_create(self, job, data):
        """
        Create a new virtualizated instance.
        """

        await self.middleware.call('virt.global.check_initialized')
        verrors = ValidationErrors()
        await self.validate(data, 'virt_instance_create', verrors)

        devices = {}
        for i in (data['devices'] or []):
            await self.middleware.call('virt.instance.validate', i, 'virt_instance_create', verrors)
            devices[i['name']] = await self.middleware.call('virt.instance.device_to_incus', data['instance_type'], i)

        verrors.check()

        async def running_cb(data):
            if 'metadata' in data['metadata'] and (metadata := data['metadata']['metadata']):
                if 'download_progress' in metadata:
                    job.set_progress(None, metadata['download_progress'])
                if 'create_instance_from_image_unpack_progress' in metadata:
                    job.set_progress(None, metadata['create_instance_from_image_unpack_progress'])

        if data['remote'] == 'LINUX_CONTAINERS':
            url = LC_IMAGES_SERVER

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
            'start': data['autostart'],
        }}, running_cb)

        return await self.middleware.call('virt.instance.get_instance', data['name'])

    @api_method(VirtInstanceUpdateArgs, VirtInstanceUpdateResult)
    @job()
    async def do_update(self, job, id, data):
        """
        Update instance.
        """
        await self.middleware.call('virt.global.check_initialized')
        instance = await self.middleware.call('virt.instance.get_instance', id, {'extra': {'raw': True}})

        verrors = ValidationErrors()
        await self.validate(data, 'virt_instance_update', verrors, old=instance)
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
        await self.middleware.call('virt.global.check_initialized')
        instance = await self.middleware.call('virt.instance.get_instance', id)
        if instance['status'] == 'RUNNING':
            await incus_call_and_wait(f'1.0/instances/{id}/state', 'put', {'json': {
                'action': 'stop',
                'timeout': -1,
                'force': True,
            }})

        await incus_call_and_wait(f'1.0/instances/{id}', 'delete')

        return True

    @api_method(VirtInstanceStartArgs, VirtInstanceStartResult, roles=['VIRT_INSTANCE_WRITE'])
    @job(logs=True)
    async def start(self, job, id):
        """
        Start an instance.
        """
        await self.middleware.call('virt.global.check_initialized')
        instance = await self.middleware.call('virt.instance.get_instance', id)

        try:
            await incus_call_and_wait(f'1.0/instances/{id}/state', 'put', {'json': {
                'action': 'start',
            }})
        except CallError:
            log = 'lxc.log' if instance['type'] == 'CONTAINER' else 'qemu.log'
            content = await incus_call(f'1.0/instances/{id}/logs/{log}', 'get', json=False)
            output = []
            while line := await content.readline():
                output.append(line)
                output = output[-10:]
            await job.logs_fd_write(b''.join(output).strip())
            raise CallError('Failed to start instance. Please check job logs.')

        return True

    @api_method(VirtInstanceStopArgs, VirtInstanceStopResult, roles=['VIRT_INSTANCE_WRITE'])
    @job()
    async def stop(self, job, id, data):
        """
        Stop an instance.

        Timeout is how long it should wait for the instance to shutdown cleanly.
        """
        # Only check started because its used when tearing the service down
        await self.middleware.call('virt.global.check_started')
        await incus_call_and_wait(f'1.0/instances/{id}/state', 'put', {'json': {
            'action': 'stop',
            'timeout': data['timeout'],
            'force': data['force'],
        }})

        return True

    @api_method(VirtInstanceRestartArgs, VirtInstanceRestartResult, roles=['VIRT_INSTANCE_WRITE'])
    @job()
    async def restart(self, job, id, data):
        """
        Restart an instance.

        Timeout is how long it should wait for the instance to shutdown cleanly.
        """
        await self.middleware.call('virt.global.check_initialized')
        instance = await self.middleware.call('virt.instance.get_instance', id)
        if instance['status'] == 'RUNNING':
            await incus_call_and_wait(f'1.0/instances/{id}/state', 'put', {'json': {
                'action': 'stop',
                'timeout': data['timeout'],
                'force': data['force'],
            }})

        await incus_call_and_wait(f'1.0/instances/{id}/state', 'put', {'json': {
            'action': 'start',
        }})

        return True
