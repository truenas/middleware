from __future__ import annotations

import typing
from typing import Any

import middlewared.sqlalchemy as sa
from middlewared.api.current import (
    DockerAddressPool, DockerEntry, DockerRegistryMirror, DockerUpdate, ZFSResourceQuery,
)
from middlewared.service import CallError, ConfigServicePart, ValidationErrors
from middlewared.utils.zfs import query_imported_fast_impl
from middlewared.plugins.zfs.utils import get_encryption_info

from .fs_manage import ix_apps_is_mounted, mount_docker_ds, umount_docker_ds
from .migrate import migrate_ix_apps_dataset
from .service_utils import license_active
from .state_management import set_status as docker_set_status
from .state_setup import status_change as docker_status_change
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

    async def extend(self, data: dict[str, Any]) -> dict[str, Any]:
        data['dataset'] = applications_ds_name(data['pool']) if data.get('pool') else None
        data['nvidia'] = (await self.middleware.call('system.advanced.config'))['nvidia']
        data['address_pools'] = [DockerAddressPool.model_validate(p) for p in data.get('address_pools', [])]
        data['registry_mirrors'] = [DockerRegistryMirror.model_validate(m) for m in data.get('registry_mirrors', [])]
        return data

    async def do_update(self, job: Job, data: DockerUpdate) -> DockerEntry:
        old_config = await self.config()
        new_config = old_config.updated(data)

        # migrate_applications is only on DockerUpdate, not DockerEntry
        update_dict = data.model_dump()
        migrate_apps = update_dict.get('migrate_applications', False)

        # nvidia is stored in system.advanced, not docker datastore
        nvidia_changed = old_config.nvidia != new_config.nvidia
        new_nvidia = new_config.nvidia

        await self.validate(old_config, new_config, migrate_apps)

        if migrate_apps:
            await migrate_ix_apps_dataset(self, job, new_config, old_config)
            return await self.config()

        # Detect changes — after updated(), unchanged fields keep the same object reference,
        # so != correctly detects when the user provided new values
        pool_changed = new_config.pool != old_config.pool
        address_pools_changed = (
            new_config.address_pools != old_config.address_pools
            or str(new_config.cidr_v6) != str(old_config.cidr_v6)
        )
        registry_mirrors_changed = new_config.registry_mirrors != old_config.registry_mirrors
        db_changed = (
            pool_changed or address_pools_changed or registry_mirrors_changed
            or new_config.enable_image_updates != old_config.enable_image_updates
        )

        if db_changed:
            if pool_changed:
                await self.call2(self.s.app.clear_upgrade_alerts_for_all)
                job.set_progress(15, 'Stopping Apps')
                apps = await self.call2(self.s.app.query, [['state', '!=', 'STOPPED']])
                batch_size = 10
                for i in range(0, len(apps), batch_size):
                    await (await self.middleware.call(
                        'core.bulk', 'app.stop', [[app.name] for app in apps[i:i + batch_size]]
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
                    catalog_sync_job = await umount_docker_ds(self)
                except Exception:
                    self.logger.exception('Unexpected failure umounting apps dataset')
                    if await ix_apps_is_mounted(self):
                        raise
                finally:
                    if catalog_sync_job:
                        await catalog_sync_job.wait()

                await docker_set_status(self, Status.UNCONFIGURED.value)

            db_update = data.model_dump()
            db_update.pop('nvidia', None)
            db_update.pop('migrate_applications', None)
            # model_dump() preserves complex Python types (IPvAnyInterface, HttpUrl) that
            # are not directly storable in SQLite. Convert them to plain strings for DB storage.
            if 'address_pools' in db_update:
                for pool in db_update['address_pools']:
                    pool['base'] = str(pool['base'])
            if 'cidr_v6' in db_update:
                db_update['cidr_v6'] = str(db_update['cidr_v6'])
            if 'registry_mirrors' in db_update:
                for mirror in db_update['registry_mirrors']:
                    mirror['url'] = str(mirror['url'])
            await self.middleware.call('datastore.update', self._datastore, old_config.id, db_update)

            if pool_changed:
                job.set_progress(60, 'Applying requested configuration')
                await docker_status_change(self)
                if new_config.pool:
                    await self.call2(self.s.app.metadata_generate)
            elif new_config.pool and (address_pools_changed or registry_mirrors_changed):
                job.set_progress(60, 'Starting docker')
                catalog_sync_job = await mount_docker_ds(self)
                if catalog_sync_job:
                    await catalog_sync_job.wait()

                await (await self.middleware.call('service.control', 'START', 'docker')).wait(raise_error=True)

            if new_config.pool and address_pools_changed:
                job.set_progress(95, 'Initiating redeployment of applications to apply new address pools changes')
                await self.middleware.call(
                    'core.bulk', 'app.redeploy', [
                        [app.name] for app in await self.call2(self.s.app.query, [['state', '!=', 'STOPPED']])
                    ]
                )

        if nvidia_changed:
            job.set_progress(97, 'Applying requested nvidia configuration changes')
            await self.middleware.call('system.advanced.update', {'nvidia': new_nvidia})

        job.set_progress(100, 'Requested configuration applied')
        return await self.config()

    async def validate(
        self, old_config: DockerEntry, new_config: DockerEntry, migrate_apps: bool, schema: str = 'docker_update',
    ) -> None:
        verrors = ValidationErrors()

        if new_config.pool and not await license_active(self):
            verrors.add(f'{schema}.pool', 'System is not licensed to use Applications')

        if new_config.pool and not await self.to_thread(query_imported_fast_impl, [new_config.pool]):
            verrors.add(f'{schema}.pool', 'Pool not found.')

        if new_config.address_pools != old_config.address_pools:
            # When changed, new_config.address_pools contains DockerAddressPool objects from DockerUpdate
            validate_address_pools(
                await self.middleware.call('interface.ip_in_use', {'static': True}),
                [pool.model_dump() for pool in new_config.address_pools],
            )

        if new_config.registry_mirrors != old_config.registry_mirrors:
            # When changed, new_config.registry_mirrors contains DockerRegistryMirror objects from DockerUpdate
            # http/insecure check is handled by DockerUpdate Pydantic model validator
            seen_registries: set[str] = set()
            for idx, registry in enumerate(new_config.registry_mirrors):
                url = str(registry.url)
                if url in seen_registries:
                    verrors.add(
                        f'{schema}.registry_mirrors.{idx}',
                        f'Duplicate registry mirror: {url}'
                    )
                seen_registries.add(url)

        if migrate_apps:
            if new_config.pool == old_config.pool:
                verrors.add(
                    f'{schema}.migrate_applications',
                    'Migration of applications dataset only happens when a new pool is configured.'
                )
            elif not old_config.pool:
                verrors.add(
                    f'{schema}.migrate_applications',
                    'A pool must have been configured previously for ix-apps dataset migration.'
                )
            else:
                # Both pools guaranteed non-None: old_config.pool is truthy (elif above),
                # new_config.pool differs from old and DockerUpdate enforces pool when migrating
                assert new_config.pool is not None
                assert old_config.pool is not None
                if await self.call2(
                    self.s.zfs.resource.query_impl,
                    ZFSResourceQuery(paths=[applications_ds_name(new_config.pool)], properties=None)
                ):
                    verrors.add(
                        f'{schema}.migrate_applications',
                        f'Migration of {applications_ds_name(old_config.pool)!r} to {new_config.pool!r} not '
                        f'possible as {applications_ds_name(new_config.pool)} already exists.'
                    )

                ix_apps_ds = await self.call2(
                    self.s.zfs.resource.query_impl,
                    ZFSResourceQuery(
                        paths=[applications_ds_name(old_config.pool)],
                        properties=['encryption']
                    )
                )
                if not ix_apps_ds:
                    verrors.add(
                        f'{schema}.migrate_applications',
                        f'{applications_ds_name(old_config.pool)!r} does not exist, migration not possible.'
                    )
                elif get_encryption_info(ix_apps_ds[0]['properties']).encrypted:
                    verrors.add(
                        f'{schema}.migrate_applications',
                        f'{ix_apps_ds[0]["name"]!r} is encrypted which is not a supported configuration'
                    )

                destination_root_ds = await self.call2(
                    self.s.zfs.resource.query_impl,
                    ZFSResourceQuery(paths=[new_config.pool], properties=['encryption'])
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
                            f'Migration not possible as {new_config.pool!r} is locked'
                        )
                    if not await self.middleware.call(
                        'datastore.query', 'storage.encrypteddataset', [['name', '=', new_config.pool]]
                    ):
                        verrors.add(
                            f'{schema}.migrate_applications',
                            f'Migration not possible as system does not has encryption key for '
                            f'{new_config.pool!r} stored'
                        )

        verrors.check()
