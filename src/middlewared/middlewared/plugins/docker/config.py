from __future__ import annotations

import typing
from typing import Any, Awaitable
from urllib.parse import urlparse

import middlewared.sqlalchemy as sa
from middlewared.api.current import DockerEntry, ZFSResourceQuery
from middlewared.service import CallError, ConfigServicePart, ValidationErrors
from middlewared.utils.zfs import query_imported_fast_impl
from middlewared.plugins.zfs.utils import get_encryption_info

from .fs_manage import ix_apps_is_mounted, mount_docker_ds, umount_docker_ds
from .state_management import set_status as docker_set_status
from. state_setup import status_change as docker_status_change
from .state_utils import Status
from .utils import applications_ds_name
from .validation_utils import validate_address_pools


if typing.TYPE_CHECKING:
    from middlewared.job import Job


class DockerModel(sa.Model):
    __tablename__ = 'services_docker'

    id = sa.Column(sa.Integer(), primary_key=True)
    pool = sa.Column(sa.String(255), default=None, nullable=True)
    enable_image_updates = sa.Column(sa.Boolean(), default=True)
    cidr_v6 = sa.Column(sa.String(), default='fdd0::/64', nullable=False)
    address_pools = sa.Column(sa.JSON(list), default=[
        {'base': '172.17.0.0/12', 'size': 24},
        {'base': 'fdd0::/48', 'size': 64},
    ])
    registry_mirrors = sa.Column(sa.JSON(list), default=[])


class DockerConfigServicePart(ConfigServicePart[DockerEntry]):
    _datastore = 'services.docker'
    _entry = DockerEntry

    async def extend(self, data: dict[str, Any]) -> dict[str, Any] | Awaitable[dict[str, Any]]:
        data['dataset'] = applications_ds_name(data['pool']) if data.get('pool') else None
        data['nvidia'] = (await self.middleware.call('system.advanced.config'))['nvidia']
        return data

    async def do_update(self, job: Job, data: dict[str, Any]) -> DockerEntry:
        old_config = (await self.config()).model_dump()
        old_config.pop('dataset')
        config = old_config.copy()
        config.update(data)
        config['cidr_v6'] = str(config['cidr_v6'])
        migrate_apps = config.get('migrate_applications', False)

        nvidia_changed = old_config['nvidia'] != config['nvidia']
        new_nvidia = config.pop('nvidia')
        old_config.pop('nvidia')

        await self.validate(old_config, config)

        if migrate_apps:
            await self.middleware.call('docker.migrate_ix_apps_dataset', job, config, old_config, {})
            return await self.config()

        if old_config != config:
            address_pools_changed = any(config[k] != old_config[k] for k in ('address_pools', 'cidr_v6'))
            pool_changed = config['pool'] != old_config['pool']
            registry_mirrors_changed = config.get('registry_mirrors', []) != old_config.get('registry_mirrors', [])
            if pool_changed:
                await self.middleware.call('app.clear_upgrade_alerts_for_all')
                job.set_progress(15, 'Stopping Apps')
                apps = await self.middleware.call('app.query', [['state', '!=', 'STOPPED']])
                batch_size = 10
                for i in range(0, len(apps), batch_size):
                    await (await self.middleware.call(
                        'core.bulk', 'app.stop', [[app['name']] for app in apps[i:i + batch_size]]
                    )).wait()

            if pool_changed or address_pools_changed or registry_mirrors_changed:
                job.set_progress(20, 'Stopping Docker service')
                try:
                    await (await self.middleware.call('service.control', 'STOP', 'docker')).wait(raise_error=True)
                except Exception as e:
                    raise CallError(f'Failed to stop docker service: {e}')

                catalog_sync_job = None
                try:
                    job.set_progress(30, 'Umounting docker apps dataset')
                    catalog_sync_job = await mount_docker_ds(self)
                except Exception:
                    self.logger.exception('Unexpected failure umounting apps dataset')
                    if await ix_apps_is_mounted(self):
                        raise
                finally:
                    if catalog_sync_job:
                        await catalog_sync_job.wait()

                await docker_set_status(self, Status.UNCONFIGURED.value)

            await self.middleware.call('datastore.update', self._datastore, old_config['id'], config)

            if pool_changed:
                job.set_progress(60, 'Applying requested configuration')
                await docker_status_change(self)
                if config['pool']:
                    await self.middleware.call('app.metadata.generate')
            elif config['pool'] and (address_pools_changed or registry_mirrors_changed):
                job.set_progress(60, 'Starting docker')
                catalog_sync_job = await mount_docker_ds(self)
                if catalog_sync_job:
                    await catalog_sync_job.wait()

                await (await self.middleware.call('service.control', 'START', 'docker')).wait(raise_error=True)

            if config['pool'] and address_pools_changed:
                job.set_progress(95, 'Initiating redeployment of applications to apply new address pools changes')
                await self.middleware.call(
                    'core.bulk', 'app.redeploy', [
                        [app['name']] for app in await self.middleware.call('app.query', [['state', '!=', 'STOPPED']])
                    ]
                )

        if nvidia_changed:
            job.set_progress(97, 'Applying requested nvidia configuration changes')
            await self.middleware.call('system.advanced.update', {'nvidia': new_nvidia})

        job.set_progress(100, 'Requested configuration applied')
        return await self.config()

    async def validate(self, old_config: dict[str, Any], config: dict[str, Any], schema: str = 'docker_update') -> None:
        verrors = ValidationErrors()

        if config['pool'] and not await self.middleware.call('docker.license_active'):
            verrors.add(
                f'{schema}.pool',
                'System is not licensed to use Applications'
            )

        if config['pool'] and not await self.to_thread(query_imported_fast_impl, [config['pool']]):
            verrors.add(f'{schema}.pool', 'Pool not found.')

        if config['address_pools'] != old_config['address_pools']:
            validate_address_pools(
                await self.middleware.call('interface.ip_in_use', {'static': True}), config['address_pools']
            )

        seen_registries: set[str] = set()
        for idx, registry in enumerate(config.get('registry_mirrors', [])):
            if registry['url'] in seen_registries:
                verrors.add(
                    f'{schema}.registry_mirrors.{idx}',
                    f'Duplicate registry mirror: {registry["url"]}'
                )
            if urlparse(registry['url']).scheme == 'http' and not registry.get('insecure'):
                verrors.add(
                    f'{schema}.registry_mirrors.{idx}',
                    'Registry mirror URL that starts with "http://" must be marked as insecure.'
                )
            seen_registries.add(registry['url'])

        if config.pop('migrate_applications', False):
            if config['pool'] == old_config['pool']:
                verrors.add(
                    f'{schema}.migrate_applications',
                    'Migration of applications dataset only happens when a new pool is configured.'
                )
            elif not old_config['pool']:
                verrors.add(
                    f'{schema}.migrate_applications',
                    'A pool must have been configured previously for ix-apps dataset migration.'
                )
            else:
                if await self.call2(
                    self.s.zfs.resource.query_impl,
                    ZFSResourceQuery(paths=[applications_ds_name(config['pool'])], properties=None)
                ):
                    verrors.add(
                        f'{schema}.migrate_applications',
                        f'Migration of {applications_ds_name(old_config["pool"])!r} to {config["pool"]!r} not '
                        f'possible as {applications_ds_name(config["pool"])} already exists.'
                    )

                ix_apps_ds = await self.call2(
                    self.s.zfs.resource.query_impl,
                    ZFSResourceQuery(
                        paths=[applications_ds_name(old_config['pool'])],
                        properties=['encryption']
                    )
                )
                if not ix_apps_ds:
                    verrors.add(
                        f'{schema}.migrate_applications',
                        f'{applications_ds_name(old_config["pool"])!r} does not exist, migration not possible.'
                    )
                elif get_encryption_info(ix_apps_ds[0]['properties']).encrypted:
                    verrors.add(
                        f'{schema}.migrate_applications',
                        f'{ix_apps_ds[0]["name"]!r} is encrypted which is not a supported configuration'
                    )

                destination_root_ds = await self.call2(
                    self.s.zfs.resource.query_impl,
                    ZFSResourceQuery(paths=[config['pool']], properties=['encryption'])
                )
                enc = get_encryption_info(destination_root_ds[0]['properties'])
                if enc.encrypted:
                    if enc.encryption_type == 'passphrase':
                        verrors.add(
                            f'{schema}.migrate_applications',
                            f'{ix_apps_ds[0]["name"]!r} can only be migrated to a destination pool '
                            'which is "KEY" encrypted.'
                        )
                    elif enc.locked:
                        verrors.add(
                            f'{schema}.migrate_applications',
                            f'Migration not possible as {config["pool"]!r} is locked'
                        )
                    if not await self.middleware.call(
                        'datastore.query', 'storage.encrypteddataset', [['name', '=', config['pool']]]
                    ):
                        verrors.add(
                            f'{schema}.migrate_applications',
                            f'Migration not possible as system does not has encryption key for {config["pool"]!r} '
                            'stored'
                        )

        verrors.check()
