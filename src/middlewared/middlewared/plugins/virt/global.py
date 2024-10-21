from typing import TYPE_CHECKING
import subprocess
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
from middlewared.utils import run
from middlewared.plugins.boot import BOOT_POOL_NAME_VALID
from middlewared.plugins.virt.websocket import IncusWS

from .utils import incus_call
if TYPE_CHECKING:
    from middlewared.main import Middleware


INCUS_PATH = '/var/lib/incus'
INCUS_BRIDGE = 'incusbr0'


class NoPoolConfigured(Exception):
    pass


class LockedDataset(Exception):
    pass


class VirtGlobalModel(sa.Model):
    __tablename__ = 'virt_global'

    id = sa.Column(sa.Integer(), primary_key=True)
    pool = sa.Column(sa.String(120), nullable=True)
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

    @private
    async def extend(self, data):
        if data['pool']:
            data['dataset'] = f'{data["pool"]}/.ix-virt'
        else:
            data['dataset'] = None
        try:
            data['state'] = await self.middleware.call('cache.get', 'VIRT_STATE')
        except KeyError:
            data['state'] = 'INITIALIZING'
        return data

    @private
    async def validate(self, new: dict, schema_name: str, verrors: ValidationErrors):

        bridge = new['bridge'] or ''
        if bridge not in await self.bridge_choices():
            verrors.add(f'{schema_name}.bridge', 'Invalid bridge')

        pool = new['pool'] or ''
        if pool not in await self.pool_choices():
            verrors.add(f'{schema_name}.pool', 'Invalid pool')

    @api_method(VirtGlobalUpdateArgs, VirtGlobalUpdateResult)
    @job()
    async def do_update(self, job, data):
        """
        Update global virtualization settings.

        `pool` which pool to use to store instances.
        """
        old = await self.config()

        new = old.copy()
        new.update(data)

        verrors = ValidationErrors()
        await self.validate(new, 'virt_global_update', verrors)
        verrors.check()

        # Not part of the database
        new.pop('state')
        new.pop('dataset')

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
        choices = {'': 'Automatic'}
        choices.update({
            i['name']: i['name'] for i in await self.middleware.call('interface.query')
            if i['type'] == 'BRIDGE'
        })
        return choices

    @api_method(VirtGlobalPoolChoicesArgs, VirtGlobalPoolChoicesResult, roles=['VIRT_GLOBAL_READ'])
    async def pool_choices(self):
        """
        Pool choices for virtualization purposes.
        """
        pools = {'': '[Disabled]'}
        for p in (await self.middleware.call('zfs.pool.query_imported_fast')).values():
            if p['name'] in BOOT_POOL_NAME_VALID:
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
    async def get_default_profile(self):
        result = await incus_call('1.0/profiles/default', 'get')
        if result.get('status_code') != 200:
            raise CallError(result.get('error'))
        return result['metadata']

    @api_method(VirtGlobalGetNetworkArgs, VirtGlobalGetNetworkResult, roles=['VIRT_GLOBAL_READ'])
    async def get_network(self, name):
        """
        Details for the given network.
        """
        result = await incus_call(f'1.0/networks/{name}', 'get')
        if result.get('status_code') != 200:
            raise CallError(result.get('error'))
        data = result['metadata']
        return {
            'type': data['type'].upper(),
            'managed': data['managed'],
            'ipv4_address': data['config']['ipv4.address'],
            'ipv4_nat': data['config']['ipv4.nat'],
            'ipv6_address': data['config']['ipv6.address'],
            'ipv6_nat': data['config']['ipv6.nat'],
        }

    @private
    @job()
    async def setup(self, job):
        """
        Sets up incus through their API.
        Will create necessary storage datasets if required.
        """
        try:
            await self.middleware.call('cache.put', 'VIRT_STATE', 'INITIALIZING')
            await self._setup_impl(job)
        except NoPoolConfigured:
            await self.middleware.call('cache.put', 'VIRT_STATE', 'NO_POOL')
        except LockedDataset:
            await self.middleware.call('cache.put', 'VIRT_STATE', 'LOCKED')
        except Exception:
            await self.middleware.call('cache.put', 'VIRT_STATE', 'ERROR')
            raise
        else:
            await self.middleware.call('cache.put', 'VIRT_STATE', 'INITIALIZED')

    async def _setup_impl(self, job):
        config = await self.config()

        if not config['pool']:
            if await self.middleware.call('service.started', 'incus'):
                job = await self.middleware.call('virt.global.reset')
                await job.wait(raise_error=True)
            await IncusWS().stop()

            self.logger.debug('No pool set for virtualization, skipping.')
            raise NoPoolConfigured()
        else:
            if not await self.middleware.call('service.started', 'incus'):
                await self.middleware.call('service.start', 'incus')
            await IncusWS().start()

        try:
            ds = await self.middleware.call(
                'zfs.dataset.get_instance', config['dataset'], {
                    'extra': {
                        'retrieve_children': False,
                        'user_properties': False,
                        'properties': ['encryption', 'keystatus'],
                    }
                },
            )
        except Exception:
            ds = None
        if not ds:
            await self.middleware.call('zfs.dataset.create', {
                'name': config['dataset'],
                'properties': {
                    'aclmode': 'discard',
                    'acltype': 'posix',
                    'exec': 'on',
                    'casesensitivity': 'sensitive',
                    'atime': 'off',
                },
            })
        else:
            if ds['encrypted'] and not ds['key_loaded']:
                self.logger.info('Dataset %r not unlocked, skipping virt setup.', ds['name'])
                raise LockedDataset()

        import_storage = True
        storage = await incus_call('1.0/storage-pools/default', 'get')
        if storage['type'] != 'error':
            if storage['metadata']['config']['source'] == config['dataset']:
                self.logger.debug('Storage pool for virt already configured.')
                import_storage = False
            else:
                job = await self.middleware.call('virt.global.reset', True)
                await job.wait(raise_error=True)

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

        if import_storage:
            payload = {
                'pools': [{
                    'config': {'source': config['dataset']},
                    'description': '',
                    'name': 'default',
                    'driver': 'zfs',
                }],
            }
            result = await incus_call('internal/recover/validate', 'post', {'json': payload})
            if result.get('status') == 'Success':
                if result['metadata']['DependencyErrors']:
                    raise CallError('Missing depedencies: ' + ', '.join(result['metadata']['DependencyErrors']))
                result = await incus_call('internal/recover/import', 'post', {'json': payload})
                if result.get('status') != 'Success':
                    raise CallError(result.get('error'))
            else:
                raise CallError('Invalid storage')

        result = await incus_call('1.0/profiles/default', 'put', {'json': {
            'config': {},
            'description': 'Default TrueNAS profile',
            'devices': {
                'root': {
                    'path': '/',
                    'pool': 'default',
                    'type': 'disk',
                },
                'eth0': nic,
            },
        }})
        if result.get('status') != 'Success':
            raise CallError(result.get('error'))

    @private
    @job()
    async def reset(self, job, start: bool = False):
        config = await self.config()

        if await self.middleware.call('service.started', 'incus'):
            # Stop running instances
            params = [
                [i['id'], {'force': True, 'timeout': 10}]
                for i in await self.middleware.call(
                    'virt.instance.query', [('status', '=', 'RUNNING')]
                )
            ]
            job = await self.middleware.call('core.bulk', 'virt.instance.stop', params, 'Stopping instances')
            await job.wait()

            if await self.middleware.call('virt.instance.query', [('status', '=', 'RUNNING')]):
                raise CallError('Failed to stop instances')

        await self.middleware.call('service.stop', 'incus')
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
        await run(['rm', '-rf', '--one-file-system', INCUS_PATH], check=True)

        if start and not await self.middleware.call('service.start', 'incus'):
            raise CallError('Failed to start virtualization service')


async def _event_system_ready(middleware: 'Middleware', event_type, args):
    middleware.create_task(middleware.call('virt.global.setup'))


async def setup(middleware: 'Middleware'):
    middleware.event_subscribe('system.ready', _event_system_ready)
    # Should only happen if middlewared crashes or during development
    if await middleware.call('system.ready'):
        await middleware.call('virt.global.setup')
