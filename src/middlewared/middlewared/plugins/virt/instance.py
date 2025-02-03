import collections
import json
import os
import platform

import aiohttp

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
from .utils import get_vnc_info_from_config, Status, incus_call, incus_call_and_wait, VNC_BASE_PORT


LC_IMAGES_SERVER = 'https://images.linuxcontainers.org'
LC_IMAGES_JSON = f'{LC_IMAGES_SERVER}/streams/v1/images.json'


class VirtInstanceService(CRUDService):

    class Config:
        namespace = 'virt.instance'
        cli_namespace = 'virt.instance'
        entry = VirtInstanceEntry
        role_prefix = 'VIRT_INSTANCE'
        event_register = True

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
            # config may be empty due to a race condition during stop
            # if thats the case grab instance details without recursion
            # which means aliases and state will be unknown
            if not i.get('config'):
                i = (await incus_call(f'1.0/instances/{i["name"]}', 'get'))['metadata']
            if not i.get('state'):
                status = 'UNKNOWN'
            else:
                status = i['state']['status'].upper()
            entry = {
                'id': i['name'],
                'name': i['name'],
                'type': 'CONTAINER' if i['type'] == 'container' else 'VM',
                'status': status,
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
                },
                **get_vnc_info_from_config(i['config']),
                'raw': None,  # Default required by pydantic
                'secure_boot': None,
                'root_disk_size': None,
            }
            if entry['type'] == 'VM':
                entry['secure_boot'] = True if i['config'].get('security.secureboot') == 'true' else False
                size = i['devices'].get('root', {}).get('size')
                entry['root_disk_size'] = int(size) if size else None

            idmap = None
            if idmap_current := i['config'].get('volatile.idmap.current'):
                idmap_current = json.loads(idmap_current)
                uid = list(filter(lambda x: x.get('Isuid'), idmap_current)) or None
                if uid:
                    uid = {
                        'hostid': uid[0]['Hostid'],
                        'maprange': uid[0]['Maprange'],
                        'nsid': uid[0]['Nsid'],
                    }
                gid = list(filter(lambda x: x.get('Isgid'), idmap_current)) or None
                if gid:
                    gid = {
                        'hostid': gid[0]['Hostid'],
                        'maprange': gid[0]['Maprange'],
                        'nsid': gid[0]['Nsid'],
                    }
                idmap = {
                    'uid': uid,
                    'gid': gid,
                }
            entry['userns_idmap'] = idmap

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

            for v in ((i.get('state') or {}).get('network') or {}).values():
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
        # Do not validate image_choices because its an expansive operation, just fail on creation
        instance_type = new.get('instance_type') or (old or {}).get('type')
        if instance_type and not await self.middleware.call('virt.global.license_active', instance_type):
            verrors.add(
                f'{schema_name}.instance_type', f'System is not licensed to manage {instance_type!r} instances'
            )

        if not old and await self.query([('name', '=', new['name'])]):
            verrors.add(f'{schema_name}.name', f'Name {new["name"]!r} already exists')

        if instance_type != 'VM' and new.get('secure_boot'):
            verrors.add(f'{schema_name}.secure_boot', 'Secure boot is only supported for VMs')

        if new.get('memory'):
            meminfo = await self.middleware.call('system.mem_info')
            if new['memory'] > meminfo['physmem_size']:
                verrors.add(f'{schema_name}.memory', 'Cannot reserve more than physical memory')

        if new.get('cpu') and new['cpu'].isdigit():
            cpuinfo = await self.middleware.call('system.cpu_info')
            if int(new['cpu']) > cpuinfo['core_count']:
                verrors.add(f'{schema_name}.cpu', 'Cannot reserve more than system cores')

        if old:
            if 'secure_boot' not in new:
                new['secure_boot'] = old['secure_boot']

            enable_vnc = new.get('enable_vnc')
            if enable_vnc is False:
                # User explicitly disabled VNC support, let's remove vnc port
                new.update({
                    'vnc_port': None,
                    'vnc_password': None,
                })
            elif enable_vnc is True:
                if not old['vnc_port'] and not new.get('vnc_port'):
                    verrors.add(f'{schema_name}.vnc_port', 'VNC port is required when VNC is enabled')
                elif not new.get('vnc_port'):
                    new['vnc_port'] = old['vnc_port']

                if 'vnc_password' not in new:
                    new['vnc_password'] = old['vnc_password']
            elif enable_vnc is None:
                for k in ('vnc_port', 'vnc_password'):
                    if new.get(k):
                        verrors.add(f'{schema_name}.enable_vnc', f'Should be set when {k!r} is specified')

                if old['vnc_enabled'] and old['vnc_port']:
                    # We want to handle the case where nothing has been changed on vnc attrs
                    new.update({
                        'enable_vnc': True,
                        'vnc_port': old['vnc_port'],
                        'vnc_password': old['vnc_password'],
                    })
                else:
                    new.update({
                        'enable_vnc': False,
                        'vnc_port': None,
                        'vnc_password': None,
                    })
        else:
            # Creation case
            if new['source_type'] == 'ISO' and not await self.middleware.call(
                'virt.volume.query', [['content_type', '=', 'ISO'], ['id', '=', new['iso_volume']]]
            ):
                verrors.add(
                    f'{schema_name}.iso_volume',
                    'Invalid ISO volume selected. Please select a valid ISO volume.'
                )

        if instance_type == 'VM' and new.get('enable_vnc'):
            if not new.get('vnc_port'):
                verrors.add(f'{schema_name}.vnc_port', 'VNC port is required when VNC is enabled')
            else:
                port_verrors = await self.middleware.call(
                    'port.validate_port',
                    f'{schema_name}.vnc_port',
                    new['vnc_port'], '0.0.0.0', 'virt',
                )
                verrors.extend(port_verrors)
                if not port_verrors:
                    port_mapping = await self.get_ports_mapping([['id', '!=', old['id']]] if old else [])
                    if any(new['vnc_port'] in v for v in port_mapping.values()):
                        verrors.add(f'{schema_name}.vnc_port', 'VNC port is already in use by another virt instance')

    def __data_to_config(self, data: dict, raw: dict = None, instance_type=None):
        config = {}
        if 'environment' in data:
            # If we are updating environment we need to remove current values
            if raw:
                for i in list(filter(lambda x: x.startswith('environment.'), raw.keys())):
                    raw.pop(i)
            if data['environment']:
                for k, v in data['environment'].items():
                    config[f'environment.{k}'] = v

        if 'cpu' in data:
            config['limits.cpu'] = data['cpu']

        if 'memory' in data:
            if data['memory']:
                config['limits.memory'] = str(int(data['memory'] / 1024 / 1024)) + 'MiB'
            else:
                config['limits.memory'] = None

        if data.get('autostart') is not None:
            config['boot.autostart'] = str(data['autostart']).lower()

        if instance_type == 'VM':
            config.update({
                'security.secureboot': 'true' if data['secure_boot'] else 'false',
                'user.ix_old_raw_qemu_config': raw.get('raw.qemu', '') if raw else '',
                'user.ix_vnc_config': json.dumps({
                    'vnc_enabled': data['enable_vnc'],
                    'vnc_port': data['vnc_port'],
                    'vnc_password': data['vnc_password'],
                }),
            })

            if data.get('enable_vnc') and data.get('vnc_port'):
                vnc_config = f'-vnc :{data["vnc_port"] - VNC_BASE_PORT}'
                if data.get('vnc_password'):
                    vnc_config = f'-object secret,id=vnc0,data={data["vnc_password"]} {vnc_config},password-secret=vnc0'

                config['raw.qemu'] = vnc_config
            if data.get('enable_vnc') is False:
                config['raw.qemu'] = ''

        return config

    @api_method(VirtInstanceImageChoicesArgs, VirtInstanceImageChoicesResult, roles=['VIRT_INSTANCE_READ'])
    async def image_choices(self, data):
        """
        Provide choices for instance image from a remote repository.
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
                    alias = v['aliases'].split(',', 1)[0]
                    if v['requirements'].get('cdrom_agent'):
                        # We are adding this check to ignore such images because these are cloud images
                        # and require agent to be installed/configured which is obviously not going to
                        # happen
                        continue

                    if alias not in choices:
                        instance_types = set()
                        for i in v['versions'].values():
                            if 'root.tar.xz' in i['items'] and 'desktop' not in v['aliases']:
                                instance_types.add('CONTAINER')
                            if 'disk.qcow2' in i['items']:
                                instance_types.add('VM')
                        if not instance_types:
                            continue
                        choices[alias] = {
                            'label': f'{v["os"]} {v["release"]} ({v["arch"]}, {v["variant"]})',
                            'os': v['os'],
                            'release': v['release'],
                            'archs': [v['arch']],
                            'variant': v['variant'],
                            'instance_types': list(instance_types),
                            'secureboot': (
                                False if v['requirements'].get('secureboot') == 'false' else True
                            ),
                        }
                    else:
                        choices[alias]['archs'].append(v['arch'])
        return choices

    @api_method(VirtInstanceCreateArgs, VirtInstanceCreateResult)
    @job()
    async def do_create(self, job, data):
        """
        Create a new virtualized instance.
        """
        await self.middleware.call('virt.global.check_initialized')
        verrors = ValidationErrors()
        await self.validate(data, 'virt_instance_create', verrors)

        data_devices = data['devices'] or []
        iso_volume = data.pop('iso_volume', None)
        root_device_to_add = None
        zvol_path = data.pop('zvol_path', None)
        if data['source_type'] == 'ZVOL':
            data['source_type'] = None
            root_device_to_add = {
                'name': 'ix_virt_zvol_root',
                'dev_type': 'DISK',
                'source': zvol_path,
                'destination': None,
                'readonly': False,
                'boot_priority': 1,
            }
        elif data['source_type'] == 'ISO':
            root_device_to_add = {
                'name': iso_volume,
                'dev_type': 'DISK',
                'pool': 'default',
                'source': iso_volume,
                'destination': None,
                'readonly': False,
                'boot_priority': 1,
            }

        if root_device_to_add:
            data['source_type'] = None
            data_devices.append(root_device_to_add)

        devices = {
            'root': {
                'path': '/',
                'pool': 'default',
                'type': 'disk',
                'size': f'{data["root_disk_size"] * (1024**3)}',
            }
        } if data['instance_type'] == 'VM' else {}
        for i in data_devices:
            await self.middleware.call(
                'virt.instance.validate_device', i, 'virt_instance_create', verrors, data['instance_type'],
            )
            if i['name'] is None:
                i['name'] = await self.middleware.call('virt.instance.generate_device_name', devices.keys(), i['dev_type'])
            devices[i['name']] = await self.middleware.call('virt.instance.device_to_incus', data['instance_type'], i)

        if not verrors and data['devices']:
            await self.middleware.call('virt.instance.validate_devices', data['devices'], 'virt_instance_create', verrors)

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
            'type': (data['source_type'] or 'none').lower(),
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
        try:
            await incus_call_and_wait('1.0/instances', 'post', {'json': {
                'name': data['name'],
                'ephemeral': False,
                'config': self.__data_to_config(data, instance_type=data['instance_type']),
                'devices': devices,
                'source': source,
                'type': 'container' if data['instance_type'] == 'CONTAINER' else 'virtual-machine',
                'start': data['autostart'],
            }}, running_cb, timeout=15 * 60)
            # We will give 15 minutes to incus to download relevant image and then timeout
        except CallError as e:
            if await self.middleware.call('virt.instance.query', [['name', '=', data['name']]]):
                await (await self.middleware.call('virt.instance.delete', data['name'])).wait()
            raise e

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
        if instance['type'] == 'CONTAINER' and data.get('enable_vnc'):
            verrors.add('virt_instance_update.vnc_port', 'VNC is not supported for containers')

        verrors.check()

        instance['raw']['config'].update(self.__data_to_config(data, instance['raw']['config'], instance['type']))
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
        except CallError as e:
            log = 'lxc.log' if instance['type'] == 'CONTAINER' else 'qemu.log'
            content = await incus_call(f'1.0/instances/{id}/logs/{log}', 'get', json=False)
            output = []
            while line := await content.readline():
                output.append(line)
                output = output[-10:]
            output = b''.join(output).strip()
            errmsg = f'Failed to start instance: {e.errmsg}.'
            try:
                # If we get a json means there is no log file
                json.loads(output.decode())
            except json.decoder.JSONDecodeError:
                await job.logs_fd_write(output)
                errmsg += ' Please check job logs.'
            raise CallError(errmsg)

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

    @private
    def get_shell(self, id):
        """
        Method to get a valid shell to be used by default.
        """

        self.middleware.call_sync('virt.global.check_initialized')
        instance = self.middleware.call_sync('virt.instance.get_instance', id)
        if instance['type'] != 'CONTAINER':
            raise CallError('Only available for containers.')
        if instance['status'] != 'RUNNING':
            raise CallError('Container must be running.')
        config = self.middleware.call_sync('virt.global.config')
        mount_info = self.middleware.call_sync(
            'filesystem.mount_info', [['mount_source', '=', f'{config["dataset"]}/containers/{id}']]
        )
        if not mount_info:
            return None
        rootfs = f'{mount_info[0]["mountpoint"]}/rootfs'
        for i in ('/bin/bash', '/bin/zsh', '/bin/csh', '/bin/sh'):
            if os.path.exists(f'{rootfs}{i}'):
                return i

    @private
    async def get_ports_mapping(self, filters=None):
        ports = collections.defaultdict(list)
        for instance in await self.middleware.call('virt.instance.query', filters or []):
            if instance['vnc_enabled']:
                ports[instance['id']].append(instance['vnc_port'])
            for device in await self.middleware.call('virt.instance.device_list', instance['id']):
                if device['dev_type'] != 'PROXY':
                    continue

                ports[instance['id']].append(device['source_port'])

        return ports
