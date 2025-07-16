from middlewared.service import CallError, periodic, Service, private

from .state_utils import APPS_STATUS, IX_APPS_MOUNT_PATH, Status, STATUS_DESCRIPTIONS


class DockerStateService(Service):

    class Config:
        namespace = 'docker.state'
        private = True

    STATUS = APPS_STATUS(Status.PENDING, STATUS_DESCRIPTIONS[Status.PENDING])

    async def before_start_check(self):
        try:
            if not await self.middleware.call('docker.license_active'):
                raise CallError('System is not licensed to use Applications')

            await self.middleware.call('docker.setup.validate_fs')
        except CallError as e:
            if e.errno != CallError.EDATASETISLOCKED:
                await self.middleware.call(
                    'alert.oneshot_create',
                    'ApplicationsConfigurationFailed',
                    {'error': e.errmsg},
                )

            await self.set_status(Status.FAILED.value, f'Could not validate applications setup ({e.errmsg})')
            raise

        await self.middleware.call('alert.oneshot_delete', 'ApplicationsConfigurationFailed', None)

    async def after_start_check(self):
        if await self.middleware.call('service.started', 'docker'):
            await self.set_status(Status.RUNNING.value)
            await self.middleware.call('alert.oneshot_delete', 'ApplicationsStartFailed', None)
        else:
            await self.set_status(Status.FAILED.value, 'Failed to start docker service')
            await self.middleware.call('alert.oneshot_create', 'ApplicationsStartFailed', {
                'error': 'Docker service could not be started'
            })

    async def start_service(self, mount_datasets: bool = False):
        await self.set_status(Status.INITIALIZING.value)
        catalog_sync_job = None
        try:
            await self.before_start_check()
            if mount_datasets:
                catalog_sync_job = await self.middleware.call('docker.fs_manage.mount')

            config = await self.middleware.call('docker.config')
            # Make sure correct ix-apps dataset is mounted
            if not await self.middleware.call('docker.fs_manage.ix_apps_is_mounted', config['dataset']):
                raise CallError(f'{config["dataset"]!r} dataset is not mounted on {IX_APPS_MOUNT_PATH!r}')
            await (await self.middleware.call('service.control', 'START', 'docker')).wait(raise_error=True)
        except Exception as e:
            await self.set_status(Status.FAILED.value, str(e))
            raise
        else:
            await self.middleware.call('app.certificate.redeploy_apps_consuming_outdated_certs')
        finally:
            if catalog_sync_job:
                await catalog_sync_job.wait()

    async def set_status(self, new_status, extra=None):
        assert new_status in Status.__members__
        new_status = Status(new_status)
        self.STATUS = APPS_STATUS(
            new_status,
            f'{STATUS_DESCRIPTIONS[new_status]}:\n{extra}' if extra else STATUS_DESCRIPTIONS[new_status],
        )
        self.middleware.send_event('docker.state', 'CHANGED', fields=await self.get_status_dict())

    async def get_status_dict(self):
        return {'status': self.STATUS.status.value, 'description': self.STATUS.description}

    async def initialize(self):
        if not await self.middleware.call('system.ready'):
            # Status will be automatically updated when system is ready
            return

        if not (await self.middleware.call('docker.config'))['pool']:
            await self.set_status(Status.UNCONFIGURED.value)
        else:
            if await self.middleware.call('service.started', 'docker'):
                await self.set_status(Status.RUNNING.value)
            else:
                await self.set_status(Status.FAILED.value)

    async def validate(self, raise_error=True):
        # When `raise_error` is unset, we return boolean true if there was no issue with the state
        error_str = ''
        if not (await self.middleware.call('docker.config'))['pool']:
            error_str = 'No pool configured for Docker'
        if not error_str and not await self.middleware.call('service.started', 'docker'):
            error_str = 'Docker service is not running'
        if not await self.middleware.call('docker.license_active'):
            error_str = 'System is not licensed to use Applications'

        if error_str and raise_error:
            raise CallError(error_str)

        return bool(error_str) is False

    @periodic(interval=86400)
    async def periodic_check(self):
        if await self.validate(False) is False:
            return

        await (await self.middleware.call('catalog.sync')).wait()

        docker_config = await self.middleware.call('docker.config')
        if docker_config['enable_image_updates']:
            self.middleware.create_task(self.middleware.call('app.image.op.check_update'))


async def _event_system_ready(middleware, event_type, args):
    # we ignore the 'ready' event on an HA system since the failover event plugin
    # is responsible for starting this service
    if await middleware.call('failover.licensed'):
        return

    if (await middleware.call('docker.config'))['pool']:
        middleware.create_task(middleware.call('docker.state.start_service', True))
    else:
        await middleware.call('docker.state.set_status', Status.UNCONFIGURED.value)


async def _event_system_shutdown(middleware, event_type, args):
    if await middleware.call('service.started', 'docker'):
        await middleware.call('service.control', 'STOP', 'docker')  # No need to wait for this to complete


async def handle_license_update(middleware, *args, **kwargs):
    if not await middleware.call('docker.license_active'):
        # We will like to stop docker in this case
        middleware.create_task(middleware.call('service.stop', 'docker'))


async def setup(middleware):
    middleware.event_register('docker.state', 'Docker state events', roles=['DOCKER_READ'])
    middleware.event_subscribe('system.ready', _event_system_ready)
    middleware.event_subscribe('system.shutdown', _event_system_shutdown)
    await middleware.call('docker.state.initialize')
    middleware.register_hook('system.post_license_update', handle_license_update)
