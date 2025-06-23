import collections
import json
import os
import platform

import aiohttp

from middlewared.service import (
    CallError, CRUDService, ValidationError, ValidationErrors, job, private
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
from middlewared.utils.size import normalize_size

from .utils import (
    create_vnc_password_file, get_max_boot_priority_device, get_root_device_dict, get_vnc_info_from_config,
    VirtGlobalStatus, incus_call, incus_call_and_wait, incus_pool_to_storage_pool, root_device_pool_from_raw,
    storage_pool_to_incus_pool, validate_device_name, generate_qemu_cmd, generate_qemu_cdrom_metadata,
    INCUS_METADATA_CDROM_KEY,
)


LC_IMAGES_SERVER = 'https://images.linuxcontainers.org'
LC_IMAGES_JSON = f'{LC_IMAGES_SERVER}/streams/v1/images.json'


class VirtInstanceService(CRUDService):

    class Config:
        namespace = 'virt.instance'
        cli_namespace = 'virt.instance'
        entry = VirtInstanceEntry
        role_prefix = 'VIRT_INSTANCE'
        event_register = True

    async def query(self, filters, options):
        """
        Query all instances with `query-filters` and `query-options`.
        """
        if not options['extra'].get('skip_state'):
            config = await self.middleware.call('virt.global.config')
            if config['state'] != VirtGlobalStatus.INITIALIZED.value:
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

            autostart = i['config'].get('boot.autostart')
            secureboot = None
            if i['config'].get('image.requirements.secureboot') == 'true':
                secureboot = True
            elif i['config'].get('image.requirements.secureboot') == 'false':
                secureboot = False
            entry = {
                'id': i['name'],
                'name': i['name'],
                'type': 'CONTAINER' if i['type'] == 'container' else 'VM',
                'status': status,
                'cpu': i['config'].get('limits.cpu'),
                'autostart': True if i['config'].get('user.autostart', autostart) == 'true' else False,
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
                    'secureboot': secureboot,
                },
                **get_vnc_info_from_config(i['config']),
                'raw': None,  # Default required by pydantic
                'secure_boot': None,
                'privileged_mode': None,
                'root_disk_size': None,
                'root_disk_io_bus': None,
                'storage_pool': incus_pool_to_storage_pool(root_device_pool_from_raw(i)),
            }
            if entry['type'] == 'VM':
                entry['secure_boot'] = True if i['config'].get('security.secureboot') == 'true' else False
                root_device = i['devices'].get('root', {})
                entry['root_disk_size'] = normalize_size(root_device.get('size'), False)
                # If one isn't set, it defaults to virtio-scsi
                entry['root_disk_io_bus'] = (root_device.get('io.bus') or 'virtio-scsi').upper()
            else:
                entry['privileged_mode'] = i['config'].get('security.privileged') == 'true'

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

            entry['memory'] = normalize_size(i['config'].get('limits.memory'), False)

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
                        'netmask': int(address['netmask']) if address['netmask'] else None,
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

        if instance_type == 'CONTAINER' and new.get('image_os'):
            verrors.add(f'{schema_name}.image_os', 'This attribute is only valid for VMs')

        if new.get('storage_pool'):
            valid_pools = await self.middleware.call('virt.global.pool_choices')
            if new['storage_pool'] not in valid_pools:
                verrors.add(f'{schema_name}.storage_pool', 'Not a valid ZFS pool')

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
            for k in filter(lambda x: x not in new, ('secure_boot', 'privileged_mode')):
                new[k] = old[k]

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

    def __data_to_config(
        self, instance_name: str, data: dict, devices: dict, raw: dict = None, instance_type=None
    ):
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

        config['boot.autostart'] = 'false'
        if data.get('autostart') is not None:
            config['user.autostart'] = str(data['autostart']).lower()

        if instance_type == 'VM':
            if data.get('image_os'):
                config['image.os'] = data['image_os'].capitalize()

            config.update({
                'security.secureboot': 'true' if data['secure_boot'] else 'false',
                'user.ix_old_raw_qemu_config': raw.get('raw.qemu', '') if raw else '',
                'user.ix_vnc_config': json.dumps({
                    'vnc_enabled': data['enable_vnc'],
                    'vnc_port': data['vnc_port'],
                    'vnc_password': data['vnc_password'],
                }),
                INCUS_METADATA_CDROM_KEY: generate_qemu_cdrom_metadata(devices),
            })

            config['raw.qemu'] = generate_qemu_cmd(config, instance_name)
        else:
            config.update({
                'security.privileged': 'true' if data.get('privileged_mode') else 'false',
            })

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
                    if v['variant'] == 'cloud':
                        # cloud-init based images are unsupported for now
                        continue

                    cdrom_agent_required = v['requirements'].get('cdrom_agent', False)
                    alias = v['aliases'].split(',', 1)[0]
                    if alias not in choices:
                        instance_types = set()
                        for i in v['versions'].values():
                            if 'root.tar.xz' in i['items'] and 'desktop' not in v['aliases']:
                                instance_types.add('CONTAINER')
                            if 'disk.qcow2' in i['items'] and not cdrom_agent_required:
                                # VM images that have a cdrom_agent requirement are not
                                # supported at the moment
                                instance_types.add('VM')
                        if not instance_types:
                            continue
                        secureboot = None
                        if v['requirements'].get('secureboot') == 'false':
                            secureboot = False
                        elif v['requirements'].get('secureboot') == 'true':
                            secureboot = True
                        choices[alias] = {
                            'label': f'{v["os"]} {v["release"]} ({v["arch"]}, {v["variant"]})',
                            'os': v['os'],
                            'release': v['release'],
                            'archs': [v['arch']],
                            'variant': v['variant'],
                            'instance_types': list(instance_types),
                            'secureboot': secureboot,
                        }
                    else:
                        choices[alias]['archs'].append(v['arch'])
        return choices

    @api_method(
        VirtInstanceCreateArgs,
        VirtInstanceCreateResult,
        audit='Virt: Creating',
        audit_extended=lambda data: f'{data["name"]!r} instance'
    )
    @job(lock=lambda args: f'instance_action_{args[0].get("name")}')
    async def do_create(self, job, data):
        """
        Create a new virtualized instance.
        """
        await self.middleware.call('virt.global.check_initialized')
        verrors = ValidationErrors()
        await self.validate(data, 'virt_instance_create', verrors)

        if data.get('storage_pool'):
            pool = storage_pool_to_incus_pool(data['storage_pool'])
        else:
            defpool = (await self.middleware.call('virt.global.config'))['pool']
            pool = storage_pool_to_incus_pool(defpool)

        data_devices = data['devices'] or []

        # Since instance_type is now hardcoded to CONTAINER and source_type to IMAGE
        # in the API model, we only need the container root device configuration
        devices = {
            'root': {
                'path': '/',
                'pool': pool,
                'type': 'disk'
            }
        }
        virt_volumes = {v['id']: v for v in await self.middleware.call('virt.volume.query')}
        for i in data_devices:
            validate_device_name(i, verrors)
            await self.middleware.call(
                'virt.instance.validate_device', i, 'virt_instance_create', verrors, data['name'], data['instance_type']
            )
            if i['name'] is None:
                i['name'] = await self.middleware.call(
                    'virt.instance.generate_device_name', devices.keys(), i['dev_type']
                )
            devices[i['name']] = await self.middleware.call(
                'virt.instance.device_to_incus', data['instance_type'], i, virt_volumes,
            )

        if not verrors and data['devices']:
            await self.middleware.call(
                'virt.instance.validate_devices', data['devices'], 'virt_instance_create', verrors
            )

        verrors.check()

        async def running_cb(data):
            if 'metadata' in data['metadata'] and (metadata := data['metadata']['metadata']):
                if 'download_progress' in metadata:
                    job.set_progress(None, metadata['download_progress'])
                if 'create_instance_from_image_unpack_progress' in metadata:
                    job.set_progress(None, metadata['create_instance_from_image_unpack_progress'])

        if data['remote'] == 'LINUX_CONTAINERS':
            url = LC_IMAGES_SERVER

        # Since source_type is hardcoded to IMAGE in the API model
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

        try:
            await incus_call_and_wait('1.0/instances', 'post', {'json': {
                'name': data['name'],
                'ephemeral': False,
                'config': self.__data_to_config(data['name'], data, devices, instance_type=data['instance_type']),
                'devices': devices,
                'source': source,
                'profiles': ['default'],
                'type': 'container',  # Only containers are supported now
                'start': False,
            }}, running_cb, timeout=15 * 60)
            # We will give 15 minutes to incus to download relevant image and then timeout
        except CallError as e:
            if await self.middleware.call('virt.instance.query', [['name', '=', data['name']]]):
                await (await self.middleware.call('virt.instance.delete', data['name'])).wait()
            raise e

        if data['autostart']:
            await self.start_impl(job, data['name'])

        return await self.middleware.call('virt.instance.get_instance', data['name'])

    @api_method(
        VirtInstanceUpdateArgs,
        VirtInstanceUpdateResult,
        audit='Virt: Updating',
        audit_extended=lambda i, data=None: f'{i!r} instance'
    )
    @job(lock=lambda args: f'instance_action_{args[0]}')
    async def do_update(self, job, oid, data):
        """
        Update instance.
        """
        await self.middleware.call('virt.global.check_initialized')
        instance = await self.middleware.call('virt.instance.get_instance', oid, {'extra': {'raw': True}})

        verrors = ValidationErrors()
        await self.validate(data, 'virt_instance_update', verrors, old=instance)
        if instance['type'] == 'CONTAINER':
            for k in ('root_disk_size', 'root_disk_io_bus', 'enable_vnc'):
                if data.get(k):
                    verrors.add(
                        f'virt_instance_update.{k}', 'This attribute is not supported for containers'
                    )

        if instance['type'] == 'VM':
            if data.get('root_disk_size'):
                if ((instance['root_disk_size'] or 0) / (1024 ** 3)) >= data['root_disk_size']:
                    verrors.add(
                        'virt_instance_update.root_disk_size',
                        'Specified size if set should be greater than the current root disk size.'
                    )

            root_key = next((k for k in ('root_disk_size', 'root_disk_io_bus') if data.get(k)), None)
            if root_key and instance['status'] != 'STOPPED':
                verrors.add(
                    f'virt_instance_update.{root_key}',
                    'VM should be stopped before updating the root disk config'
                )

        verrors.check()

        instance['raw']['config'].update(
            self.__data_to_config(oid, data, instance['raw']['devices'], instance['raw']['config'], instance['type'])
        )
        if data.get('root_disk_size') or data.get('root_disk_io_bus'):
            if (pool := root_device_pool_from_raw(instance['raw'])) is None:
                raise CallError(f'{oid}: instance does not have a configured pool')

            root_disk_size = data.get('root_disk_size') or int(instance['root_disk_size'] / (1024 ** 3))
            io_bus = data.get('root_disk_io_bus') or instance['root_disk_io_bus']
            instance['raw']['devices']['root'] = get_root_device_dict(root_disk_size, io_bus, pool)

        await incus_call_and_wait(f'1.0/instances/{oid}', 'put', {'json': instance['raw']})

        return await self.middleware.call('virt.instance.get_instance', oid)

    @api_method(
        VirtInstanceDeleteArgs,
        VirtInstanceDeleteResult,
        audit='Virt: Deleting',
        audit_extended=lambda i: f'{i!r} instance'
    )
    @job(lock=lambda args: f'instance_action_{args[0]}')
    async def do_delete(self, job, oid):
        """
        Delete an instance.
        """
        await self.middleware.call('virt.global.check_initialized')
        instance = await self.middleware.call('virt.instance.get_instance', oid)
        if instance['status'] != 'STOPPED':
            try:
                await incus_call_and_wait(f'1.0/instances/{oid}/state', 'put', {'json': {
                    'action': 'stop',
                    'timeout': -1,
                    'force': True,
                }})
            except CallError:
                self.logger.error(
                    'Failed to stop %r instance having %r status before deletion', oid, instance['status'],
                    exc_info=True
                )

        await incus_call_and_wait(f'1.0/instances/{oid}', 'delete')

        return True

    @api_method(
        VirtInstanceStartArgs,
        VirtInstanceStartResult,
        audit='Virt: Starting',
        audit_extended=lambda i: f'{i!r} instance',
        roles=['VIRT_INSTANCE_WRITE']
    )
    @job(lock=lambda args: f'instance_action_{args[0]}', logs=True)
    async def start(self, job, oid):
        """
        Start an instance.
        """
        await self.middleware.call('virt.global.check_initialized')
        return await self.start_impl(job, oid)

    @private
    async def start_impl(self, job, oid):
        instance = await self.middleware.call('virt.instance.get_instance', oid)
        if instance['status'] not in ('RUNNING', 'STOPPED'):
            raise ValidationError(
                'virt.instance.start.id',
                f'{oid}: instance may not be started because current status is: {instance["status"]}'
            )

        if instance['type'] == 'VM' and not await self.middleware.call('hardware.virtualization.guest_vms_supported'):
            raise ValidationError(
                'virt.instance.start.id',
                f'Cannot start {oid!r} as virtualization is not supported on this system'
            )

        # Apply any idmap changes
        if instance['type'] == 'CONTAINER' and instance['status'] == 'STOPPED' and not instance['privileged_mode']:
            await self.set_account_idmaps(oid)

        if instance['vnc_password']:
            await self.middleware.run_in_thread(create_vnc_password_file, oid, instance['vnc_password'])

        try:
            await incus_call_and_wait(f'1.0/instances/{oid}/state', 'put', {'json': {
                'action': 'start',
            }})
        except CallError as e:
            log = 'lxc.log' if instance['type'] == 'CONTAINER' else 'qemu.log'
            content = await incus_call(f'1.0/instances/{oid}/logs/{log}', 'get', json=False)
            output = collections.deque(maxlen=10)  # only keep last 10 lines
            while line := await content.readline():
                output.append(line)
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

    @api_method(
        VirtInstanceStopArgs,
        VirtInstanceStopResult,
        audit='Virt: Stopping',
        audit_extended=lambda i, data=None: f'{i!r} instance',
        roles=['VIRT_INSTANCE_WRITE']
    )
    @job(lock=lambda args: f'instance_action_{args[0]}')
    async def stop(self, job, oid, data):
        """
        Stop an instance.

        Timeout is how long it should wait for the instance to shutdown cleanly.
        """
        # Only check started because its used when tearing the service down
        await self.middleware.call('virt.global.check_started')
        await incus_call_and_wait(f'1.0/instances/{oid}/state', 'put', {'json': {
            'action': 'stop',
            'timeout': data['timeout'],
            'force': data['force'],
        }})

        return True

    @api_method(
        VirtInstanceRestartArgs,
        VirtInstanceRestartResult,
        audit='Virt: Restarting',
        audit_extended=lambda i, data=None: f'{i!r} instance',
        roles=['VIRT_INSTANCE_WRITE']
    )
    @job(lock=lambda args: f'instance_action_{args[0]}')
    async def restart(self, job, oid, data):
        """
        Restart an instance.

        Timeout is how long it should wait for the instance to shutdown cleanly.
        """
        await self.middleware.call('virt.global.check_initialized')
        instance = await self.middleware.call('virt.instance.get_instance', oid)
        if instance['status'] not in ('RUNNING', 'STOPPED'):
            raise ValidationError(
                f'virt.instance.restart.{oid}',
                f'{oid}: instance may not be restarted because current status is: {instance["status"]}'
            )

        if instance['status'] == 'RUNNING':
            await incus_call_and_wait(f'1.0/instances/{oid}/state', 'put', {'json': {
                'action': 'stop',
                'timeout': data['timeout'],
                'force': data['force'],
            }})

        # Apply any idmap changes
        if instance['type'] == 'CONTAINER' and not instance['privileged_mode']:
            await self.set_account_idmaps(oid)

        if instance['vnc_password']:
            await self.middleware.run_in_thread(create_vnc_password_file, oid, instance['vnc_password'])

        await incus_call_and_wait(f'1.0/instances/{oid}/state', 'put', {'json': {
            'action': 'start',
        }})

        return True

    @private
    def get_shell(self, oid):
        """
        Method to get a valid shell to be used by default.
        """

        self.middleware.call_sync('virt.global.check_initialized')
        instance = self.middleware.call_sync('virt.instance.get_instance', oid)
        if instance['type'] != 'CONTAINER':
            raise CallError('Only available for containers.')
        if instance['status'] != 'RUNNING':
            raise CallError(f'{oid}: container must be running. Current status is: {instance["status"]}')
        config = self.middleware.call_sync('virt.global.config')
        mount_info = self.middleware.call_sync(
            'filesystem.mount_info', [['mount_source', '=', f'{config["dataset"]}/containers/{oid}']]
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

    @private
    async def set_account_idmaps(self, instance_id):
        idmaps = await self.get_account_idmaps()

        raw_idmaps_value = '\n'.join([f'{i["type"]} {i["from"]} {i["to"]}' for i in idmaps])
        instance = await self.middleware.call('virt.instance.get_instance', instance_id, {'extra': {'raw': True}})
        if raw_idmaps_value:
            instance['raw']['config']['raw.idmap'] = raw_idmaps_value
        else:
            # Remove any stale raw idmaps. This is required because entries that don't correlate
            # to subuid / subgid entries will cause validation failure in incus
            instance['raw']['config'].pop('raw.idmap', None)

        await incus_call_and_wait(f'1.0/instances/{instance_id}', 'put', {'json': instance['raw']})

    @private
    async def get_account_idmaps(self, filters=None, options=None):
        """
        Return the list of idmaps that are configured in our user / group plugins
        """

        out = []

        idmap_filters = [
            ['local', '=', True],
            ['userns_idmap', 'nin', [0, None]],  # Prevent UID / GID 0 from ever being used
            ['roles', '=', []]  # prevent using users / groups with roles
        ]

        user_idmaps = await self.middleware.call('user.query', idmap_filters)
        group_idmaps = await self.middleware.call('group.query', idmap_filters)
        for user in user_idmaps:
            out.append({
                'type': 'uid',
                'from': user['uid'],
                'to': user['uid'] if user['userns_idmap'] == 'DIRECT' else user['userns_idmap']
            })

        for group in group_idmaps:
            out.append({
                'type': 'gid',
                'from': group['gid'],
                'to': group['gid'] if group['userns_idmap'] == 'DIRECT' else group['userns_idmap']
            })

        return filter_list(out, filters or [], options or {})

    @private
    async def get_instance_names(self):
        """
        Return list of instance names, this is an endpoint to get just list of names as quickly as possible
        """
        try:
            instances = (await incus_call('1.0/instances', 'get'))['metadata']
        except Exception:
            return []
        else:
            return [name.split('/')[-1] for name in instances]
