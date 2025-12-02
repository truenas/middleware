import errno

from urllib.parse import urlparse
from truenas_pylibvirt.utils.gpu import get_gpus

import middlewared.sqlalchemy as sa
from middlewared.api import api_method
from middlewared.api.current import (
    DockerEntry, DockerStatusArgs, DockerStatusResult, DockerUpdateArgs, DockerUpdateResult, DockerNvidiaPresentArgs,
    DockerNvidiaPresentResult,
)
from middlewared.service import CallError, ConfigService, ValidationErrors, job, private
from middlewared.utils.zfs import query_imported_fast_impl
from middlewared.plugins.zfs.utils import get_encryption_info

from .state_utils import Status
from .utils import applications_ds_name
from .validation_utils import validate_address_pools


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


class DockerService(ConfigService):

    class Config:
        datastore = 'services.docker'
        datastore_extend = 'docker.config_extend'
        cli_namespace = 'app.docker'
        role_prefix = 'DOCKER'
        entry = DockerEntry

    @private
    async def config_extend(self, data):
        data['dataset'] = applications_ds_name(data['pool']) if data.get('pool') else None
        data['nvidia'] = (await self.middleware.call('system.advanced.config'))['nvidia']
        return data

    @private
    async def license_active(self):
        can_run_apps = True
        if await self.middleware.call('system.is_ha_capable'):
            license_ = await self.middleware.call('system.license')
            can_run_apps = license_ is not None and 'JAILS' in license_['features']

        return can_run_apps

    @private
    async def validate_data(self, old_config, config, schema='docker_update'):
        verrors = ValidationErrors()

        if config['pool'] and not await self.license_active():
            verrors.add(
                f'{schema}.pool',
                'System is not licensed to use Applications'
            )

        if config['pool'] and not await self.middleware.run_in_thread(query_imported_fast_impl, [config['pool']]):
            verrors.add(f'{schema}.pool', 'Pool not found.')

        if config['address_pools'] != old_config['address_pools']:
            validate_address_pools(
                await self.middleware.call('interface.ip_in_use', {'static': True}), config['address_pools']
            )

        # Validate registry mirrors
        seen_registries = set()
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
                if await self.middleware.call(
                    'zfs.resource.query_impl',
                    {'paths': [applications_ds_name(config['pool'])], 'properties': None}
                ):
                    verrors.add(
                        f'{schema}.migrate_applications',
                        f'Migration of {applications_ds_name(old_config["pool"])!r} to {config["pool"]!r} not '
                        f'possible as {applications_ds_name(config["pool"])} already exists.'
                    )

                ix_apps_ds = await self.middleware.call(
                    'zfs.resource.query_impl',
                    {
                        'paths': [applications_ds_name(old_config['pool'])],
                        'properties': ['encryption']
                    }
                )
                if not ix_apps_ds:
                    # Edge case but handled just to be sure
                    verrors.add(
                        f'{schema}.migrate_applications',
                        f'{applications_ds_name(old_config["pool"])!r} does not exist, migration not possible.'
                    )
                elif get_encryption_info(ix_apps_ds[0]['properties']).encrypted:
                    # This should never happen but better be safe with extra validation
                    verrors.add(
                        f'{schema}.migrate_applications',
                        f'{ix_apps_ds[0]["name"]!r} is encrypted which is not a supported configuration'
                    )

                # Now let's add some validation for destination
                destination_root_ds = await self.middleware.call(
                    'zfs.resource.query_impl',
                    {'paths': [config['pool']], 'properties': ['encryption']}
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

    @api_method(DockerUpdateArgs, DockerUpdateResult, audit='Docker: Updating Configurations')
    @job(lock='docker_update')
    async def do_update(self, job, data):
        """
        Update Docker service configuration.
        """
        old_config = await self.config()
        old_config.pop('dataset')
        config = old_config.copy()
        config.update(data)
        config['cidr_v6'] = str(config['cidr_v6'])
        migrate_apps = config.get('migrate_applications', False)

        nvidia_changed = old_config['nvidia'] != config['nvidia']
        new_nvidia = config.pop('nvidia')
        old_config.pop('nvidia')

        await self.validate_data(old_config, config)

        if migrate_apps:
            await self.middleware.call('docker.migrate_ix_apps_dataset', job, config, old_config, {})
            return

        if old_config != config:
            address_pools_changed = any(config[k] != old_config[k] for k in ('address_pools', 'cidr_v6'))
            pool_changed = config['pool'] != old_config['pool']
            registry_mirrors_changed = config.get('registry_mirrors', []) != old_config.get('registry_mirrors', [])
            if pool_changed:
                # We want to clear upgrade alerts for apps at this point
                await self.middleware.call('app.clear_upgrade_alerts_for_all')
                # We want to stop all apps if pool attr has changed because docker on stopping service
                # does not result in clean umount of ix-apps dataset if we have 20+ running apps
                job.set_progress(15, 'Stopping Apps')
                apps = await self.middleware.call('app.query', [['state', '!=', 'STOPPED']])
                batch_size = 10
                # Let's do this in batches to avoid creating lots of tasks at once
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
                    catalog_sync_job = await self.middleware.call('docker.fs_manage.umount')
                except CallError as e:
                    # We handle this specially, if for whatever reason ix-apps dataset is not there,
                    # we don't make it fatal to change pools etc - however if some dataset other then
                    # boot pool is mounted at ix-apps dir, then we will error out as it's a problem
                    # and needs to be fixed before we can proceed
                    if e.errno != errno.ENOENT or await self.middleware.call('docker.fs_manage.ix_apps_is_mounted'):
                        raise
                finally:
                    if catalog_sync_job:
                        await catalog_sync_job.wait()

                await self.middleware.call('docker.state.set_status', Status.UNCONFIGURED.value)

            await self.middleware.call('datastore.update', self._config.datastore, old_config['id'], config)

            if pool_changed:
                job.set_progress(60, 'Applying requested configuration')
                await self.middleware.call('docker.setup.status_change')
                if config['pool']:
                    # So we for example here had null before and now we set it to some pool
                    # we will like to make sure that collective app config / metadata files
                    # exist so that operations like backup work as desired
                    await self.middleware.call('app.metadata.generate')
            elif config['pool'] and (address_pools_changed or registry_mirrors_changed):
                job.set_progress(60, 'Starting docker')
                catalog_sync_job = await self.middleware.call('docker.fs_manage.mount')
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

    @private
    async def restart_svc(self):
        """
        This is an internal method called when we change nvidia configuration
        so docker picks up the new configuration changes on restart
        """
        await (await self.middleware.call('service.control', 'STOP', 'docker')).wait(raise_error=True)
        await (await self.middleware.call('service.control', 'START', 'docker')).wait(raise_error=True)

    @api_method(DockerStatusArgs, DockerStatusResult, roles=['DOCKER_READ'])
    async def status(self):
        """
        Returns the status of the docker service.
        """
        return await self.middleware.call('docker.state.get_status_dict')

    @api_method(DockerNvidiaPresentArgs, DockerNvidiaPresentResult, roles=['DOCKER_READ'])
    def nvidia_present(self):
        adv_config = self.middleware.call_sync("system.advanced.config")

        for gpu in get_gpus():
            if gpu["addr"]["pci_slot"] in adv_config["isolated_gpu_pci_ids"]:
                continue

            if gpu["vendor"] == "NVIDIA":
                return True

        return False
