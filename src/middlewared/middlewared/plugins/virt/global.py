import asyncio
import errno
import re
import shutil
import subprocess
import uuid
from collections import defaultdict
from typing import TYPE_CHECKING

import middlewared.sqlalchemy as sa
from middlewared.api import api_method
from middlewared.api.current import (
    VirtGlobalEntry,
    VirtGlobalUpdateArgs, VirtGlobalUpdateResult,
    VirtGlobalBridgeChoicesArgs, VirtGlobalBridgeChoicesResult,
    VirtGlobalPoolChoicesArgs, VirtGlobalPoolChoicesResult,
    VirtGlobalGetNetworkArgs, VirtGlobalGetNetworkResult,
)

from middlewared.service import job, private
from middlewared.service import ConfigService, ValidationErrors
from middlewared.service_exception import CallError
from middlewared.utils import run, BOOT_POOL_NAME_VALID
from middlewared.utils.zfs import query_imported_fast_impl
from .utils import (
    VirtGlobalStatus, incus_call, VNC_PASSWORD_DIR, TRUENAS_STORAGE_PROP_STR, INCUS_BRIDGE, INCUS_STORAGE
)

if TYPE_CHECKING:
    from middlewared.main import Middleware


BRIDGE_AUTO = '[AUTO]'
POOL_DISABLED = '[DISABLED]'
RE_FAILED_INSTANCE = re.compile(r'Failed creating instance "(.*)" record')


class NoPoolConfigured(Exception):
    pass


class LockedDataset(Exception):
    pass


class VirtGlobalModel(sa.Model):
    __tablename__ = 'virt_global'

    id = sa.Column(sa.Integer(), primary_key=True)
    pool = sa.Column(sa.String(120), nullable=True)
    storage_pools = sa.Column(sa.Text(), nullable=True)
    bridge = sa.Column(sa.String(120), nullable=True)
    v4_network = sa.Column(sa.String(120), nullable=True)
    v6_network = sa.Column(sa.String(120), nullable=True)


class VirtGlobalService(ConfigService):

    class Config:
        datastore = 'virt_global'
        datastore_extend = 'virt.global.extend'
        namespace = 'virt.global'
        cli_namespace = 'virt.global'
        role_prefix = 'VIRT_GLOBAL'
        entry = VirtGlobalEntry

    @private
    async def extend(self, data):
        if data['pool']:
            data['dataset'] = f'{data["pool"]}/.ix-virt'
        else:
            data['dataset'] = None

        if data['storage_pools']:
            data['storage_pools'] = data['storage_pools'].split()
        else:
            data['storage_pools'] = []

        if data['pool'] and data['pool'] not in data['storage_pools']:
            data['storage_pools'].append(data['pool'])

        data['state'] = INCUS_STORAGE.state.value
        return data

    @private
    async def validate(self, new: dict, schema_name: str, verrors: ValidationErrors):
        bridge = new['bridge']
        if not bridge:
            bridge = BRIDGE_AUTO
        if bridge not in await self.bridge_choices():
            verrors.add(f'{schema_name}.bridge', 'Invalid bridge')
        if bridge == BRIDGE_AUTO:
            new['bridge'] = None

        pool = new['pool']
        if not pool:
            pool = POOL_DISABLED
        if pool not in await self.pool_choices():
            verrors.add(f'{schema_name}.pool', 'Invalid pool')
        if pool == POOL_DISABLED:
            new['pool'] = None

        if pool and not await self.middleware.call('virt.global.license_active'):
            verrors.add(f'{schema_name}.pool', 'System is not licensed to run virtualization')

        if new['pool'] and (mapping := (await self.middleware.call('port.ports_mapping')).get(53)):
            port_usages = set()
            for usages in map(lambda i: mapping.get(i, {}).get('port_details', []), ('0.0.0.0', '::')):
                for u in filter(lambda j: 53 in [i[1] for i in j['ports']], usages):
                    port_usages.add(u['description'])

            if port_usages:
                verrors.add(
                    f'{schema_name}.pool',
                    (
                        f'Port 53 is required for virtualization but is currently in use by the following services '
                        f'on wildcard IPs (0.0.0.0/::): {", ".join(port_usages)}. '
                        'Please reconfigure these services to bind to specific IP addresses instead of wildcard IPs.'
                    )
                )

    @api_method(
        VirtGlobalUpdateArgs,
        VirtGlobalUpdateResult,
        audit='Virt: Update configuration'
    )
    @job(lock='virt_global_configuration')
    async def do_update(self, job, data):
        """
        Update global virtualization settings.

        `pool` which pool to use to store instances.
        None will disable the service.

        `bridge` which bridge interface to use by default.
        None means it will automatically create one.
        """
        old = await self.config()

        new = old.copy()
        new.update(data)
        removed_storage_pools = set(old['storage_pools']) - set(new['storage_pools'])

        verrors = ValidationErrors()
        await self.validate(new, 'virt_global_update', verrors)

        pool_choices = await self.pool_choices()
        for idx, pool in enumerate(new['storage_pools']):
            if pool in pool_choices:
                continue

            verrors.add(
                f'virt_global_update.storage_pools.{idx}',
                f'{pool}: pool is not available for incus storage'
            )

        if new['pool'] and old['pool']:
            # If we're stopping or starting the virt plugin then we don't need to worry
            # about how storage changes will impact the overall running configuration.
            error_message = []
            for pool in removed_storage_pools:
                if usage := (await self.storage_pool_usage(pool)):
                    grouped_usage = defaultdict(list)
                    for item in usage:
                        grouped_usage[item["type"].capitalize()].append(item["name"])

                    usage_list = '\n'.join(
                        f'- Virt-{key}: {", ".join(value)}'
                        for key, value in grouped_usage.items()
                    )

                    error_message.append(
                        f'The pool {pool!r} cannot be removed because it is currently used by the following asset(s):\n'
                        f'{usage_list}'
                    )
            if error_message:
                verrors.add('virt_global_update.storage_pools', '\n\n'.join(error_message))

        if new['pool'] in removed_storage_pools:
            verrors.add(
                'virt_global_update.storage_pools',
                'Default incus pool may not be removed from list of storage pools.'
            )

        verrors.check()

        if new['pool'] and old['pool']:
            # If we're stopping or starting the virt plugin then we don't need to worry
            # about how storage changes will impact the overall running configuration.
            for pool in removed_storage_pools:
                await self.remove_storage_pool(pool)

        # Not part of the database
        new.pop('state')
        new.pop('dataset')
        new['storage_pools'] = ' '.join(new['storage_pools'])

        await self.middleware.call(
            'datastore.update', self._config.datastore,
            new['id'], new,
        )

        job = await self.middleware.call('virt.global.setup')
        await job.wait(raise_error=True)

        return await self.config()

    @api_method(VirtGlobalBridgeChoicesArgs, VirtGlobalBridgeChoicesResult, roles=['VIRT_GLOBAL_READ'])
    async def bridge_choices(self):
        """
        Bridge choices for virtualization purposes.

        Empty means it will be managed/created automatically.
        """
        choices = {BRIDGE_AUTO: 'Automatic'}
        # We do not allow custom bridge on HA because it might have bridge STP issues
        # causing failover problems.
        if not await self.middleware.call('failover.licensed'):
            choices.update({
                i['name']: i['name']
                for i in await self.middleware.call('interface.query', [['type', '=', 'BRIDGE']])
            })
        return choices

    @api_method(VirtGlobalPoolChoicesArgs, VirtGlobalPoolChoicesResult, roles=['VIRT_GLOBAL_READ'])
    async def pool_choices(self):
        """
        Pool choices for virtualization purposes.
        """
        pools = {POOL_DISABLED: '[Disabled]'}
        imported_pools = await self.middleware.run_in_thread(query_imported_fast_impl)
        for p in imported_pools.values():
            # Do not show boot pools or pools with spaces in their name
            # Incus is not gracefully able to handle pools which have spaces in their names
            # https://ixsystems.atlassian.net/browse/NAS-134244
            if p['name'] in BOOT_POOL_NAME_VALID or ' ' in p['name']:
                continue

            ds = await self.middleware.call(
                'pool.dataset.get_instance_quick', p['name'], {'encryption': True},
            )
            if not ds['locked']:
                pools[p['name']] = p['name']
        return pools

    @private
    async def internal_interfaces(self):
        return [INCUS_BRIDGE]

    @private
    async def check_initialized(self, config=None):
        if config is None:
            config = await self.config()
        if config['state'] != VirtGlobalStatus.INITIALIZED.value:
            raise CallError('Virtualization not initialized.')

    @private
    async def check_started(self):
        if not await self.middleware.call('service.started', 'incus'):
            raise CallError('Virtualization service not started.')

    @private
    async def get_profile(self, profile_name):
        result = await incus_call(f'1.0/profiles/{profile_name}', 'get')
        if result.get('status_code') != 200:
            raise CallError(result.get('error'))
        return result['metadata']

    @api_method(VirtGlobalGetNetworkArgs, VirtGlobalGetNetworkResult, roles=['VIRT_GLOBAL_READ'])
    async def get_network(self, name):
        """
        Details for the given network.
        """
        await self.check_initialized()
        result = await incus_call(f'1.0/networks/{name}', 'get')
        if result.get('status_code') != 200:
            raise CallError(result.get('error'))
        data = result['metadata']
        return {
            'type': data['type'].upper(),
            'managed': data['managed'],
            'ipv4_address': data['config']['ipv4.address'],
            'ipv4_nat': data['config']['ipv4.nat'] == 'true',
            'ipv6_address': data['config']['ipv6.address'],
            'ipv6_nat': data['config']['ipv6.nat'] == 'true',
        }

    @private
    @job(lock='virt_global_setup')
    async def setup(self, job):
        """
        Sets up incus through their API.
        Will create necessary storage datasets if required.
        """
        try:
            INCUS_STORAGE.state = VirtGlobalStatus.INITIALIZING
            await self._setup_impl()
        except NoPoolConfigured:
            INCUS_STORAGE.state = VirtGlobalStatus.NO_POOL
        except LockedDataset:
            INCUS_STORAGE.state = VirtGlobalStatus.LOCKED
        except Exception:
            INCUS_STORAGE.state = VirtGlobalStatus.ERROR
            raise
        else:
            INCUS_STORAGE.state = VirtGlobalStatus.INITIALIZED
        finally:
            self.middleware.send_event('virt.global.config', 'CHANGED', fields=await self.config())
            if INCUS_STORAGE.state == VirtGlobalStatus.INITIALIZED:
                # We only want to auto start instances if incus is initialized
                await self.auto_start_instances()

    @private
    async def setup_storage_pool(self, pool_name):
        ds_name = f'{pool_name}/.ix-virt'
        try:
            ds = await self.middleware.call(
                'zfs.dataset.get_instance', ds_name, {
                    'extra': {
                        'retrieve_children': False,
                        'user_properties': True,
                        'properties': ['encryption', 'keystatus'],
                    }
                },
            )
        except Exception:
            ds = None
        if not ds:
            await self.middleware.call('zfs.dataset.create', {
                'name': ds_name,
                'properties': {
                    'aclmode': 'discard',
                    'acltype': 'posix',
                    'exec': 'on',
                    'casesensitivity': 'sensitive',
                    'atime': 'off',
                    TRUENAS_STORAGE_PROP_STR: pool_name,
                },
            })
        else:
            if ds['encrypted'] and not ds['key_loaded']:
                self.logger.info('Dataset %r not unlocked, skipping virt setup.', ds['name'])
                raise LockedDataset()
            if TRUENAS_STORAGE_PROP_STR not in ds['properties']:
                if INCUS_STORAGE.default_storage_pool is not None:
                    if INCUS_STORAGE.default_storage_pool != pool_name:
                        raise CallError(
                            f'ZFS pools {pool_name} and {INCUS_STORAGE.default_storage_pool} are both '
                            'configured as the default incus storage pool and may therefore not be '
                            'used simultaneously for virt storage pools.'
                        )
                else:
                    INCUS_STORAGE.default_storage_pool = pool_name

                pool_name = 'default'

            else:
                expected_pool_name = ds['properties'][TRUENAS_STORAGE_PROP_STR]['value']
                if pool_name != expected_pool_name:
                    raise CallError(
                        f'The configured incus storage pool for the ZFS pool {pool_name} '
                        f'is {expected_pool_name}, which should match the ZFS pool name. '
                        'This mismatch may indicate that the TrueNAS ix-virt dataset was '
                        'not initially created on this ZFS pool.'
                    )

        storage = await incus_call(f'1.0/storage-pools/{pool_name}', 'get')
        if storage['type'] != 'error':
            if storage['metadata']['config']['source'] == ds_name:
                self.logger.debug('Virt storage pool for %s already configured.', ds_name)
                pool_name = None  # skip recovery
            else:
                job = await self.middleware.call('virt.global.reset', True, None)
                await job.wait(raise_error=True)

        return pool_name

    @private
    async def storage_pool_usage(self, pool_name):
        """
        Create a list of various user-managed incus assets that are
        dependent on the specified pool. This can be used for validation prior
        to deletion of an incus storage pool.
        """
        resp = await incus_call(f'1.0/storage-pools/{pool_name}', 'get')
        if resp['type'] == 'error':
            if resp['error_code'] == 404:
                # storage doesn't exist. Nothing to do.
                return []

            raise CallError(resp['error'])

        out = []

        for dependent in resp['metadata']['used_by']:
            if dependent.startswith(('/1.0/images/')):
                continue

            path = dependent.split('/')
            if 'storage-pools' in path:
                # sample:
                # /1.0/storage-pools/dozer/volumes/custom/foo
                incus_type = path[4]
            else:
                # sample:
                # /1.0/instances/myinstance
                incus_type = path[2]

            out.append({'type': incus_type, 'name': path[-1]})

        return out

    @private
    @job(lock='virt_global_recover')
    async def recover(self, job, to_import):
        """
        Call into incus's private API to initiate a recovery action.
        This is roughly equivalent to running the command "incus admin recover", and is performed
        to make it so that incus on TrueNAS does not rely on the contents of /var/lib/incus.

        https://linuxcontainers.org/incus/docs/main/reference/manpages/incus/admin/recover/#incus-admin-recover-md

        The current design is to do this in the following scenarios:
        1. Setting up incus for this first time on the server
        2. After change to the storage pool path
        3. After an HA failover event
        4. After TrueNAS upgrades
        5. After we see user trying to add a volume whose dataset already exists

        NOTE: this will potentially cause user-initiated changes from incus commands to be lost.
        """
        payload = {
            'pools': to_import,
            'project': 'default',
        }

        result = await incus_call('internal/recover/validate', 'post', {'json': payload})
        if result['type'] == 'error':
            raise CallError(f'Internal storage validation failed: {result["error"]}')

        elif result.get('status') == 'Success':
            if result['metadata']['DependencyErrors']:
                raise CallError('Missing dependencies: ' + ', '.join(result['metadata']['DependencyErrors']))

            await self.recover_import_impl(payload, result)
        else:
            raise CallError('Internal storage validation failed')

    @private
    async def recover_import_impl(self, payload, result):
        identified_instances = {
            i['name']: i for i in (result['metadata'].get('UnknownVolumes', []) or [])
            if all(k in i for k in ('name', 'pool', 'type'))
        }
        attempted_recovered_instances = set()
        moved_instances = set()
        misconfigured_parent_datasets = set()
        while True:
            result = await incus_call('internal/recover/import', 'post', {'json': payload})
            if result.get('status') == 'Success':
                # If we succeeded, great - let's break the loop
                break

            # How this will work is the following:
            # Basically we want to identify those instances which have attachments which no longer exists
            # Incus refuses to start in this case so we want to attempt to recover and then move such
            # instances in their respective storage pools under a new dataset
            # i.e tank/.ix-virt/misconfigured_containers
            # This way incus won't attempt to recover them as it will fail hard when it tries
            #
            # There is another problem here that for example you have 2 or more such instances which are
            # problematic, incus wont' give you their names at once - rather it will raise an error
            # as soon as it goes over the first one so we need to do this in a loop
            #
            # To conclude what will happen here is that
            # failed_instance -> attempt recovery -> try recover/import again -> still fails then move
            instance_name = RE_FAILED_INSTANCE.findall(result.get('error', ''))
            if not instance_name:
                # This is the case where in the error we were not able to identify any instance
                raise CallError(result.get('error'))

            instance_name = instance_name[0]
            # If we have already attempted to move such instances and we see an error again about them
            # by incus, let's fail hard as this will be a vicious loop otherwise and something else
            # is wrong. This should not happen as incus won't even recognize such instances at all now
            # because they don't exist where it looks for them, but better safe then sorry
            # However if earlier when the validation call ran, it identified instances which it was to
            # recover, if we don't find the instance there - we still fail hard
            if instance_name in moved_instances or instance_name not in identified_instances:
                # We do not want a vicious infinite loop here
                raise CallError(f'Failed to recover {instance_name!r} instance: {result["error"]}')

            instance = identified_instances[instance_name]
            if instance_name not in attempted_recovered_instances:
                # We will attempt recovery here before trying to move it
                self.logger.debug('Attempting recovery of %r instance', instance_name)
                try:
                    await self.middleware.call('virt.recover.instance', instance)
                except CallError as e:
                    self.logger.error(e, exc_info=True)
                finally:
                    attempted_recovered_instances.add(instance_name)

                continue

            moved_instances.add(instance_name)
            # instance type ds_name
            instance_type_ds = 'containers' if instance['type'] == 'container' else 'virtual-machines'
            # This is the incus instance dataset which we want to move
            instance_ds = f'{instance["pool"]}/.ix-virt/{instance_type_ds}/{instance_name}'
            # This is the parent dataset under which we are going to move this misconfigured instance
            new_ds_parent = f'{instance["pool"]}/.ix-virt/misconfigured_{instance_type_ds}'
            # This is the new dataset name/path of the misconfigured incus instance dataset
            new_ds = f'{new_ds_parent}/{instance_name}'

            # Before we move forward now, we would like to make sure new_ds_parent actually exists
            # Also to avoid repeated calls for example for the case where a lot of instances are in
            # a singe storage pool, we keep a local cache and check if it already exists or if it
            # needs to be created
            if new_ds_parent not in misconfigured_parent_datasets and not await self.middleware.call(
                'zfs.resource.query_impl',
                {'paths': [new_ds_parent], 'properties': None},
            ):
                await self.middleware.call(
                    'zfs.dataset.create', {'name': new_ds_parent, 'type': 'FILESYSTEM'}
                )

            # Caching this now to avoid querying zfs again if this parent ds exists or not
            misconfigured_parent_datasets.add(new_ds_parent)

            # Okay now we might have to rename new_ds because an instance with the same name might
            # exist there
            for i in range(1, 5):
                if await self.middleware.call(
                    'zfs.resource.query_impl',
                    {'paths': [new_ds], 'properties': None}
                ):
                    new_ds = f'{new_ds}_{i}'
                else:
                    # We found a name which hasn't been used
                    break
            else:
                # We will get here if we were not able to find a dataset even after above iterations
                # Let's just add a uuid suffix then
                new_ds = f'{new_ds}_{str(uuid.uuid4()).split("-")[-1]}'

            self.logger.error(
                'Could not recover %r instance because of %r, renaming %r to %r',
                instance_name, result['error'], instance_ds, new_ds
            )
            await self.middleware.call('zfs.dataset.rename', instance_ds, {'new_name': new_ds})
            # For VMs we want move the .block dataset as well
            if instance['type'] != 'container':
                await self.middleware.call(
                    'zfs.dataset.rename', f'{instance_ds}.block', {'new_name': f'{new_ds}.block'}
                )

    @private
    async def remove_storage_pool(self, pool_name):
        resp = await incus_call(f'1.0/storage-pools/{pool_name}', 'get')
        if resp['type'] == 'error':
            if resp['error_code'] == 404:
                # storage doesn't exist. Nothing to do.
                return

            raise CallError(resp['error'])

        to_delete = []

        for dependent in resp['metadata']['used_by']:
            # Middleware internally manages the images and profiles for
            # storage pools
            if dependent.startswith('/1.0/images/'):
                to_delete.append(dependent)

        if remainder := (set(resp['metadata']['used_by']) - set(to_delete)):
            raise CallError(
                f'Storage volume currently used by the following incus resource {", ".join(remainder)}', errno.EBUSY
            )

        for entry in to_delete:
            path = entry[1:]  # remove leading slash
            resp = await incus_call(path, 'delete')
            if resp['type'] == 'error' and resp['error_code'] != 404:
                raise CallError(f"{resp['error_code']}: {resp['error']}")

        # Finally remove the pool itself
        # We get intermittent errors here from incus API (appears to be replaying last command)
        # unless we have a sleep
        await asyncio.sleep(1)

        resp = await incus_call(f'1.0/storage-pools/{pool_name}', 'delete')
        if resp['type'] == 'error':
            raise CallError(resp['error'])

    async def _setup_impl(self):
        config = await self.config()
        to_import = []

        if not config['pool']:
            if await self.middleware.call('service.started', 'incus'):
                job = await self.middleware.call('virt.global.reset', False, config)
                await job.wait(raise_error=True)

            self.logger.debug('No pool set for virtualization, skipping.')
            raise NoPoolConfigured()
        else:
            await (
                await self.middleware.call(
                    'service.control', 'START', 'incus', {'ha_propagate': False}
                )
            ).wait(raise_error=True)

        # Set up the default storage pool
        for pool in config['storage_pools']:
            if (pool_name := (await self.setup_storage_pool(pool))) is not None:
                to_import.append({
                    'config': {'source': f'{pool}/.ix-virt'},
                    'description': '',
                    'name': pool_name,
                    'driver': 'zfs',
                })

        # If no bridge interface has been set, use incus managed
        if not config['bridge']:

            result = await incus_call(f'1.0/networks/{INCUS_BRIDGE}', 'get')
            # Create INCUS_BRIDGE if it doesn't exist
            if result.get('status') != 'Success':
                # Reuse v4/v6 network from database if there is one
                result = await incus_call('1.0/networks', 'post', {'json': {
                    'config': {
                        'ipv4.address': config['v4_network'] or 'auto',
                        'ipv4.nat': 'true',
                        'ipv6.address': config['v6_network'] or 'auto',
                        'ipv6.nat': 'true',
                    },
                    'description': '',
                    'name': INCUS_BRIDGE,
                    'type': 'bridge',
                }})
                if result.get('status_code') != 200:
                    raise CallError(result.get('error'))

                result = await incus_call(f'1.0/networks/{INCUS_BRIDGE}', 'get')
                if result.get('status_code') != 200:
                    raise CallError(result.get('error'))

                update_network = True
            else:

                # In case user sets empty v4/v6 network we need to generate another
                # range automatically.
                update_network = False
                netconfig = {'ipv4.nat': 'true', 'ipv6.nat': 'true'}
                if not config['v4_network']:
                    update_network = True
                    netconfig['ipv4.address'] = 'auto'
                else:
                    netconfig['ipv4.address'] = config['v4_network']
                if not config['v6_network']:
                    update_network = True
                    netconfig['ipv6.address'] = 'auto'
                else:
                    netconfig['ipv6.address'] = config['v6_network']

                update_network |= any(
                    config[f'v{i}_network'] != result['metadata']['config'][f'ipv{i}.address']
                    for i in (4, 6)
                )

                if update_network:
                    result = await incus_call(f'1.0/networks/{INCUS_BRIDGE}', 'put', {'json': {
                        'config': netconfig,
                    }})
                    if result.get('status_code') != 200:
                        raise CallError(result.get('error'))

                    result = await incus_call(f'1.0/networks/{INCUS_BRIDGE}', 'get')
                    if result.get('status_code') != 200:
                        raise CallError(result.get('error'))

            if update_network:
                # Update automatically selected networks into our database
                # so it can persist upgrades.
                await self.middleware.call('datastore.update', 'virt_global', config['id'], {
                    'v4_network': result['metadata']['config']['ipv4.address'],
                    'v6_network': result['metadata']['config']['ipv6.address'],
                })

            nic = {
                'name': 'eth0',
                'network': INCUS_BRIDGE,
                'type': 'nic',
            }
        else:
            nic = {
                'name': 'eth0',
                'type': 'nic',
                'nictype': 'bridged',
                'parent': config['bridge'],
            }

        result = await incus_call('1.0/profiles/default', 'put', {'json': {
            'config': {},
            'description': 'Default TrueNAS profile',
            'devices': {
                'eth0': nic,
            },
        }})
        if result.get('status') != 'Success':
            raise CallError(result.get('error'))

        if to_import:
            await (await self.middleware.call('virt.global.recover', to_import)).wait(raise_error=True)
            await (await self.middleware.call(
                'service.control', 'RESTART', 'incus', {'ha_propagate': False}
            )).wait(raise_error=True)

    @private
    @job(lock='virt_global_reset')
    async def reset(self, job, start: bool = False, config: dict | None = None):
        if config is None:
            config = await self.config()

        if await self.middleware.call('service.started', 'incus'):
            # Stop running instances
            params = [
                [i['id'], {'force': True, 'timeout': 10}]
                for i in await self.middleware.call(
                    'virt.instance.query', [('status', '=', 'RUNNING')],
                    {'extra': {'skip_state': True}},
                )
            ]
            job = await self.middleware.call('core.bulk', 'virt.instance.stop', params, 'Stopping instances')
            await job.wait()

            if await self.middleware.call('virt.instance.query', [('status', '=', 'RUNNING')]):
                raise CallError('Failed to stop instances')

        await (
            await self.middleware.call(
                'service.control', 'STOP', 'incus', {'ha_propagate': False}
            )
        ).wait(raise_error=True)
        if await self.middleware.call('service.started', 'incus'):
            raise CallError('Failed to stop virtualization service')

        if not config['bridge']:
            # Make sure we delete in case it exists
            try:
                await run(['ip', 'link', 'show', INCUS_BRIDGE], check=True)
            except subprocess.CalledProcessError:
                pass
            else:
                await run(['ip', 'link', 'delete', INCUS_BRIDGE], check=True)

        # Have incus start fresh
        # Use subprocess because shutil.rmtree will traverse filesystems
        # and we do have instances datasets that might be mounted beneath
        await run('rm -rf --one-file-system /var/lib/incus/*', shell=True, check=True)

        if start and not await (
            await self.middleware.call(
                'service.control', 'START', 'incus', {'ha_propagate': False}
            )
        ).wait(raise_error=True):
            raise CallError('Failed to start virtualization service')

        if not start:
            await self.middleware.run_in_thread(shutil.rmtree, VNC_PASSWORD_DIR, True)

    @private
    async def auto_start_instances(self):
        await self.middleware.call(
            'core.bulk', 'virt.instance.start', [
                [instance['name']] for instance in await self.middleware.call(
                    'virt.instance.query', [
                        ['autostart', '=', True],
                        ['status', '=', 'STOPPED'],
                        ['type', '=', 'CONTAINER']  # Only autostart CONTAINER type instances
                    ]
                )
                # We have an explicit filter for STOPPED because old virt instances would still have
                # incus autostart enabled and we don't want to attempt to start them again.
                # We can remove this in FT release perhaps.
            ]
        )

    @private
    async def set_status(self, new_status):
        INCUS_STORAGE.state = new_status
        self.middleware.send_event('virt.global.config', 'CHANGED', fields=await self.config())


async def _event_system_ready(middleware: 'Middleware', event_type, args):
    if not await middleware.call('failover.licensed'):
        middleware.create_task(middleware.call('virt.global.setup'))


async def setup(middleware: 'Middleware'):
    middleware.event_register(
        'virt.global.config',
        'Sent on virtualziation configuration changes.',
        roles=['VIRT_GLOBAL_READ']
    )
    middleware.event_subscribe('system.ready', _event_system_ready)
    # Should only happen if middlewared crashes or during development
    failover_licensed = await middleware.call('failover.licensed')
    ready = await middleware.call('system.ready')
    if ready and not failover_licensed:
        await middleware.call('virt.global.setup')
