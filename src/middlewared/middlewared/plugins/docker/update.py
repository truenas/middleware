import errno
import os
import subprocess

import middlewared.sqlalchemy as sa

from middlewared.api import api_method
from middlewared.api.current import (
    DockerEntry, DockerStatusArgs, DockerStatusResult, DockerUpdateArgs, DockerUpdateResult, DockerNvidiaPresentArgs,
    DockerNvidiaPresentResult,
)
from middlewared.service import CallError, ConfigService, ValidationErrors, job, private
from middlewared.utils.gpu import get_gpus
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
    nvidia = sa.Column(sa.Boolean(), default=False)
    cidr_v6 = sa.Column(sa.String(), default='fdd0::/64', nullable=False)
    address_pools = sa.Column(sa.JSON(list), default=[
        {'base': '172.17.0.0/12', 'size': 24},
        {'base': 'fdd0::/48', 'size': 64},
    ])
    secure_registry_mirrors = sa.Column(sa.JSON(list), default=[])
    insecure_registry_mirrors = sa.Column(sa.JSON(list), default=[])
    ipv4gateway = sa.Column(sa.String(128), default=None, nullable=True)
    ipv6gateway = sa.Column(sa.String(128), default=None, nullable=True)


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

        await self.middleware.call('network.configuration.validate_gateways', verrors, config, schema)

        if config['address_pools'] != old_config['address_pools']:
            validate_address_pools(
                await self.middleware.call('interface.ip_in_use', {'static': True}), config['address_pools']
            )

        # Validate registry mirrors - first check for duplicates within each list
        for registry_type in ['secure_registry_mirrors', 'insecure_registry_mirrors']:
            seen_registries = set()
            for idx, registry_str in enumerate(config.get(registry_type, [])):
                if registry_str in seen_registries:
                    verrors.add(
                        f'{schema}.{registry_type}.{idx}',
                        f'Duplicate {registry_type.replace("_", " ").replace("mirrors", "mirror")}.'
                    )
                seen_registries.add(registry_str)

        # Check for duplicates across both lists
        secure_set = set(config.get('secure_registry_mirrors', []))
        insecure_set = set(config.get('insecure_registry_mirrors', []))
        cross_duplicates = secure_set & insecure_set

        if cross_duplicates:
            for registry_type in ['secure_registry_mirrors', 'insecure_registry_mirrors']:
                for idx, registry_str in enumerate(config.get(registry_type, [])):
                    if registry_str in cross_duplicates:
                        verrors.add(
                            f'{schema}.{registry_type}.{idx}',
                            f'Registry mirror {registry_str} cannot be in both secure and insecure lists.'
                        )

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

        await self.validate_data(old_config, config)

        if migrate_apps:
            await self.middleware.call('docker.migrate_ix_apps_dataset', job, config, old_config, {})
            return

        if old_config != config:
            address_pools_changed = any(config[k] != old_config[k] for k in ('address_pools', 'cidr_v6'))
            pool_changed = config['pool'] != old_config['pool']
            registry_mirrors_changed = (
                config.get('secure_registry_mirrors', []) != old_config.get('secure_registry_mirrors', []) or
                config.get('insecure_registry_mirrors', []) != old_config.get('insecure_registry_mirrors', [])
            )
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

            nvidia_changed = old_config['nvidia'] != config['nvidia']

            if pool_changed or address_pools_changed or nvidia_changed or registry_mirrors_changed:
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

            if nvidia_changed:
                await self.middleware.call('docker.configure_nvidia')

            if pool_changed:
                job.set_progress(60, 'Applying requested configuration')
                await self.middleware.call('docker.setup.status_change')
                if config['pool']:
                    # So we for example here had null before and now we set it to some pool
                    # we will like to make sure that collective app config / metadata files
                    # exist so that operations like backup work as desired
                    await self.middleware.call('app.metadata.generate')
            elif config['pool'] and (address_pools_changed or nvidia_changed or registry_mirrors_changed):
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

        job.set_progress(100, 'Requested configuration applied')
        return await self.config()

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

    @private
    def configure_nvidia(self):
        config = self.middleware.call_sync('docker.config')
        nvidia_sysext_path = '/run/extensions/nvidia.raw'
        if config['nvidia'] and not os.path.exists(nvidia_sysext_path):
            os.makedirs('/run/extensions', exist_ok=True)
            os.symlink('/usr/share/truenas/sysext-extensions/nvidia.raw', nvidia_sysext_path)
            refresh = True
        elif not config['nvidia'] and os.path.exists(nvidia_sysext_path):
            os.unlink(nvidia_sysext_path)
            refresh = True
        else:
            refresh = False

        if refresh:
            subprocess.run(['systemd-sysext', 'refresh'], capture_output=True, check=True, text=True)
            subprocess.run(['ldconfig'], capture_output=True, check=True, text=True)

        if config['nvidia']:
            cp = subprocess.run(
                ['modprobe', '-a', 'nvidia', 'nvidia_drm', 'nvidia_modeset'],
                capture_output=True,
                text=True
            )
            if cp.returncode != 0:
                self.logger.error('Error loading nvidia driver: %s', cp.stderr)


async def setup(middleware):
    try:
        await middleware.call('docker.configure_nvidia')
    except Exception:
        middleware.logger.error('Unhandled exception configuring nvidia', exc_info=True)
