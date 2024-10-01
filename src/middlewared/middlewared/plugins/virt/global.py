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
        data['state'] = await self.middleware.call('cache.get', 'VIRT_STATE')
        return data

    @private
    async def validate(self, new: dict, schema_name: str, verrors: ValidationErrors):

        bridge = new['bridge'] or ''
        if bridge not in await self.bridge_choices():
            verrors.add(f'{schema_name}.bridge', 'Invalid bridge')

        if new['pool'] not in await self.pool_choices():
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

    @api_method(VirtGlobalBridgeChoicesArgs, VirtGlobalBridgeChoicesResult)
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

    @api_method(VirtGlobalPoolChoicesArgs, VirtGlobalPoolChoicesResult)
    async def pool_choices(self):
        """
        Pool choices for virtualization purposes.
        """
        pools = {'': '[Disabled]'}
        for p in (await self.middleware.call('zfs.pool.query_imported_fast')).values():
            ds = await self.middleware.call(
                'pool.dataset.query',
                [['id', '=', p['name']]],
                {'extra': {'retrieve_children': False}}
            )
            if not ds:
                continue

            if not ds[0]['encrypted'] or not ds[0]['locked'] or ds[0]['key_format']['value'] == 'PASSPHRASE':
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

    @api_method(VirtGlobalGetNetworkArgs, VirtGlobalGetNetworkResult)
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

        storage = await incus_call('1.0/storage-pools/default', 'get')
        if not config['pool']:
            # No pool is configured, make sure Incus does not have storage otherwise reset it
            if storage['type'] != 'error' and storage['metadata']['config']['source']:
                self.logger.debug(
                    'Incus configured with %r, resetting', storage['metadata']['config']['source'],
                )
                job = await self.middleware.call('virt.global.reset')
                await job.wait(raise_error=True)

            self.logger.debug('No pool set for virtualization, skipping.')
            raise NoPoolConfigured()

        ds = await self.middleware.call(
            'pool.dataset.query',
            [['id', '=', config['dataset']]],
            {'extra': {'retrieve_children': False}}
        )
        if not ds:
            await self.middleware.call('pool.dataset.create', {
                'name': config['dataset'],
                'aclmode': 'DISCARD',
                'acltype': 'POSIX',
                'exec': 'ON',
                'casesensitivity': 'SENSITIVE',
                'atime': 'OFF',
                'xattr': 'SA',
            })
        else:
            ds = ds[0]
            if ds['encrypted'] or ds['locked']:
                self.logger.info('Dataset %r not unlocked, skipping virt setup.', ds['name'])
                raise LockedDataset()

        import_storage = True
        if storage['type'] != 'error':
            if storage['metadata']['config']['source'] == config['dataset']:
                self.logger.debug('Storage pool for virt already configured.')
                import_storage = False
            else:
                job = await self.middleware.call('virt.global.reset')
                await job.wait(raise_error=True)

        # If no bridge interface has been set, use incus managed
        if not config['bridge']:

            result = await incus_call(f'1.0/networks/{INCUS_BRIDGE}', 'get')
            # Create INCUS_BRIDGE if it doesn't exist
            if result.get('status') != 'Success':
                result = await incus_call('1.0/networks', 'post', {'json': {
                    'config': {
                        'ipv4.address': 'auto',
                        'ipv6.address': 'auto',
                    },
                    'description': '',
                    'name': INCUS_BRIDGE,
                    'type': '',
                }})
                if result.get('status') != 'Success':
                    raise CallError(result.get('error'))

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
    async def reset(self, job):
        config = await self.config()

        if await self.middleware.call('service.started', 'incus'):
            # Stop running instances
            for instance in await self.middleware.call('virt.instances.query', [('status', '=', 'RUNNING')]):
                await (await self.middleware.call('virt.instances.state', instance['id'], 'STOP', True)).wait()

            if await self.middleware.call('virt.instances.query', [('status', '=', 'RUNNING')]):
                raise CallError('Failed to stop instances')

        if not config['bridge']:
            # Make sure we delete in case it exists
            try:
                await run(['ip', 'link', 'show', INCUS_BRIDGE], check=True)
            except subprocess.CalledProcessError:
                pass
            else:
                await run(['ip', 'link', 'delete', INCUS_BRIDGE], check=True)

        await self.middleware.call('service.stop', 'incus')
        if await self.middleware.call('service.started', 'incus'):
            raise CallError('Failed to stop virtualization service')

        # Have incus start fresh
        await run(['rm', '-rf', '--one-file-system', INCUS_PATH], check=True)

        if not await self.middleware.call('service.start', 'incus'):
            raise CallError('Failed to start virtualization service')


async def _event_system_ready(middleware: 'Middleware', event_type, args):
    middleware.create_task(middleware.call('virt.global.setup'))


async def setup(middleware: 'Middleware'):
    middleware.event_subscribe('system.ready', _event_system_ready)
    # Should only happen if middlewared crashes or during development
    if await middleware.call('system.ready'):
        await middleware.call('virt.global.setup')
