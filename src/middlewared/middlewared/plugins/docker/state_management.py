import errno

from middlewared.api.base import Event
from middlewared.api.current import DockerStateChangedEvent
from middlewared.service import CallError, periodic, Service

from .state_utils import APPS_STATUS, IX_APPS_MOUNT_PATH, Status, STATUS_DESCRIPTIONS

# Docker can take a long time to start on systems with HDDs (2-3+ minutes)
# We set a 16 minute timeout to accommodate slow disk initialization
DOCKER_START_TIMEOUT = 16 * 60
DOCKER_SHUTDOWN_TIMEOUT = 60  # This is seconds


class DockerStateService(Service):

    class Config:
        namespace = 'docker.state'
        private = True
        events = [
            Event(
                name='docker.state',
                description='Docker state events',
                roles=['DOCKER_READ'],
                models={'CHANGED': DockerStateChangedEvent},
            )
        ]

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
            await (
                await self.middleware.call('service.control', 'START', 'docker', {'timeout': DOCKER_START_TIMEOUT})
            ).wait(raise_error=True)
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

        try:
            await (await self.middleware.call('catalog.sync')).wait()
        except CallError as e:
            if e.errno != errno.EBUSY:
                raise

        docker_config = await self.middleware.call('docker.config')
        if docker_config['enable_image_updates']:
            self.middleware.create_task(self.middleware.call('app.image.op.check_update'))

    async def terminate_timeout(self):
        """
        Return timeout value for terminate method.
        We give DOCKER_SHUTDOWN_TIMEOUT seconds for Docker to stop gracefully.
        """
        return DOCKER_SHUTDOWN_TIMEOUT

    async def terminate(self):
        """
        Gracefully stop Docker service during system shutdown/reboot.
        Only applies to single node systems (not HA).
        Waits up to DOCKER_SHUTDOWN_TIMEOUT seconds for Docker to stop gracefully.
        """
        if not await self.middleware.call('failover.licensed') and await self.middleware.call(
            'system.state'
        ) == 'SHUTTING_DOWN' and await self.middleware.call('service.started', 'docker'):
            try:
                job_id = await self.middleware.call('service.control', 'STOP', 'docker')
                await job_id.wait(DOCKER_SHUTDOWN_TIMEOUT)
            except Exception as e:
                self.middleware.logger.warning('Failed to gracefully stop Docker service: %s', e)


async def _event_system_ready(middleware, event_type, args):
    # we ignore the 'ready' event on an HA system since the failover event plugin
    # is responsible for starting this service
    if await middleware.call('failover.licensed'):
        return

    if (await middleware.call('docker.config'))['pool']:
        middleware.create_task(middleware.call('docker.state.start_service', True))
    else:
        await middleware.call('docker.state.set_status', Status.UNCONFIGURED.value)


async def handle_license_update(middleware, *args, **kwargs):
    if not await middleware.call('docker.license_active'):
        # We will like to stop docker in this case
        await middleware.call('service.control', 'STOP', 'docker')


async def setup(middleware):
    middleware.event_subscribe('system.ready', _event_system_ready)
    await middleware.call('docker.state.initialize')
    middleware.register_hook('system.post_license_update', handle_license_update)
