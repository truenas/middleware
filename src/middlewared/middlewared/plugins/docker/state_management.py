from middlewared.service import CallError, private, Service

from .state_utils import APPS_STATUS, Status, STATUS_DESCRIPTIONS


class DockerStateService(Service):

    class Config:
        namespace = 'docker.state'
        private = True

    STATUS = APPS_STATUS(Status.PENDING, STATUS_DESCRIPTIONS[Status.PENDING])

    @private
    async def before_start_check(self):
        try:
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

    @private
    async def after_start_check(self):
        if await self.middleware.call('service.started', 'docker'):
            await self.set_status(Status.RUNNING.value)
        else:
            await self.set_status(Status.FAILED.value, 'Failed to start docker service')

    @private
    async def start_service(self):
        await self.set_status(Status.INITIALIZING.value)
        try:
            # TODO: Check license active
            await self.before_start_check()
            await self.middleware.call('service.start', 'docker')
        except Exception as e:
            await self.set_status(Status.FAILED.value, str(e))
            raise

    @private
    async def set_status(self, new_status, extra=None):
        assert new_status in Status.__members__
        new_status = Status(new_status)
        self.STATUS = APPS_STATUS(
            new_status,
            f'{STATUS_DESCRIPTIONS[new_status]}:\n{extra}' if extra else STATUS_DESCRIPTIONS[new_status],
        )
        self.middleware.send_event('docker.state', 'CHANGED', fields=await self.get_status_dict())

    @private
    async def get_status_dict(self):
        return {'status': self.STATUS.status.value, 'description': self.STATUS.description}

    @private
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


async def _event_system_ready(middleware, event_type, args):
    # we ignore the 'ready' event on an HA system since the failover event plugin
    # is responsible for starting this service
    if await middleware.call('failover.licensed'):
        return

    if (await middleware.call('docker.config'))['pool']:
        middleware.create_task(middleware.call('docker.start_service'))
    else:
        await middleware.call('docker.set_status', Status.UNCONFIGURED.value)


async def _event_system_shutdown(middleware, event_type, args):
    if await middleware.call('service.started', 'docker'):
        middleware.create_task(middleware.call('service.stop', 'docker'))


async def setup(middleware):
    middleware.event_register('docker.state', 'Docker state events')
    middleware.event_subscribe('system.ready', _event_system_ready)
    middleware.event_subscribe('system.shutdown', _event_system_shutdown)
    await middleware.call('docker.state.initialize')
