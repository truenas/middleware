import os
import subprocess

import middlewared.sqlalchemy as sa
from middlewared.schema import accepts, Bool, Dict, Int, IPAddr, List, Patch, Str, ValidationErrors
from middlewared.service import CallError, ConfigService, job, private, returns
from middlewared.utils.gpu import get_gpus
from middlewared.utils.zfs import query_imported_fast_impl
from middlewared.validators import Range

from .state_utils import Status
from .utils import applications_ds_name
from .validation_utils import validate_address_pools


class DockerModel(sa.Model):
    __tablename__ = 'services_docker'

    id = sa.Column(sa.Integer(), primary_key=True)
    pool = sa.Column(sa.String(255), default=None, nullable=True)
    enable_image_updates = sa.Column(sa.Boolean(), default=True)
    nvidia = sa.Column(sa.Boolean(), default=False)
    address_pools = sa.Column(sa.JSON(list), default=[{'base': '172.17.0.0/12', 'size': 24}])


class DockerService(ConfigService):

    class Config:
        datastore = 'services.docker'
        datastore_extend = 'docker.config_extend'
        cli_namespace = 'app.docker'
        role_prefix = 'DOCKER'

    ENTRY = Dict(
        'docker_entry',
        Bool('enable_image_updates', required=True),
        Int('id', required=True),
        Str('dataset', required=True),
        Str('pool', required=True, null=True),
        Bool('nvidia', required=True),
        List('address_pools', items=[
             Dict(
                 'address_pool',
                 IPAddr('base', cidr=True),
                 Int('size', validators=[Range(min_=1, max_=32)])
             )
        ]),
        update=True,
    )

    @private
    async def config_extend(self, data):
        data['dataset'] = applications_ds_name(data['pool']) if data.get('pool') else None
        return data

    @accepts(
        Patch(
            'docker_entry', 'docker_update',
            ('rm', {'name': 'id'}),
            ('rm', {'name': 'dataset'}),
            ('attr', {'update': True}),
        )
    )
    @job(lock='docker_update')
    async def do_update(self, job, data):
        """
        Update Docker service configuration.
        """
        old_config = await self.config()
        old_config.pop('dataset')
        config = old_config.copy()
        config.update(data)

        verrors = ValidationErrors()
        if config['pool'] and not await self.middleware.run_in_thread(query_imported_fast_impl, [config['pool']]):
            verrors.add('docker_update.pool', 'Pool not found.')

        verrors.check()

        address_pool_changed = config['address_pools'] != old_config['address_pools']
        if address_pool_changed:
            validate_address_pools(
                await self.middleware.call('interface.ip_in_use', {'static': True}), config['address_pools']
            )

        if address_pool_changed or old_config != config:
            apps_pool_changed = config['pool'] != old_config['pool']
            if apps_pool_changed:
                # We want to clear upgrade alerts for apps at this point
                await self.middleware.call('app.clear_upgrade_alerts_for_all')

            nvidia_changed = old_config['nvidia'] != config['nvidia']

            if address_pool_changed or apps_pool_changed or nvidia_changed:
                job.set_progress(20, 'Stopping Docker service')
                try:
                    await self.middleware.call('service.stop', 'docker')
                except Exception as e:
                    if apps_pool_changed:
                        filters = [['id', '=', applications_ds_name(old_config['pool'])]]
                        opts = {'extra': {'retrieve_children': False, 'retrieve_properties': False}}
                        old_apps_pool_exists = await self.middleware.call('zfs.dataset.query', filters, opts)
                        if old_apps_pool_exists:
                            # If the old apps dataset does not exist AND we get an error trying to
                            # stop the docker service, then we DO NOT want to crash here
                            # since it means the user won't be able to change the zpool that
                            # the apps are using. In this scenario, we'll ignore the crash
                            # and fallthrough to the logic below. HOWEVER, if the old apps
                            # dataset does exist and we get an exception, then we consider
                            # this unexpected and we'll raise an error.
                            raise CallError(f'Failed to stop docker service: {e}')

                    await self.middleware.call('docker.state.set_status', Status.UNCONFIGURED.value)

            await self.middleware.call('datastore.update', self._config.datastore, old_config['id'], config)

            if nvidia_changed:
                await self.middleware.call('docker.configure_nvidia')

            if apps_pool_changed:
                job.set_progress(60, 'Applying requested configuration')
                await self.middleware.call('docker.setup.status_change')
            elif config['pool'] and address_pool_changed:
                job.set_progress(60, 'Starting docker')
                await self.middleware.call('service.start', 'docker')

            if config['pool'] and config['address_pools'] != old_config['address_pools']:
                job.set_progress(95, 'Initiating redeployment of applications to apply new address pools changes')
                await self.middleware.call(
                    'core.bulk', 'app.redeploy', [
                        [app['name']] for app in await self.middleware.call('app.query', [['state', '!=', 'STOPPED']])
                    ]
                )

        job.set_progress(100, 'Requested configuration applied')
        return await self.config()

    @accepts(roles=['DOCKER_READ'])
    @returns(Dict(
        Str('status', enum=[e.value for e in Status]),
        Str('description'),
    ))
    async def status(self):
        """
        Returns the status of the docker service.
        """
        return await self.middleware.call('docker.state.get_status_dict')

    @accepts()
    @returns(Bool())
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
