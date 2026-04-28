import errno

from middlewared.alert.source.applications import ApplicationsConfigurationFailedAlert, ApplicationsStartFailedAlert
from middlewared.api.current import DockerStatusInfo
from middlewared.service import CallError, ServiceContext

from .fs_manage import ix_apps_is_mounted, mount_docker_ds
from .service_utils import license_active
from .state_setup import validate_fs as docker_validate_fs
from .state_utils import APPS_STATUS, IX_APPS_MOUNT_PATH, STATUS_DESCRIPTIONS, Status

# Docker can take a long time to start on systems with HDDs (2-3+ minutes)
# We set a 16 minute timeout to accommodate slow disk initialization
DOCKER_START_TIMEOUT = 16 * 60
DOCKER_SHUTDOWN_TIMEOUT = 60  # This is seconds
STATUS = APPS_STATUS(Status.PENDING, STATUS_DESCRIPTIONS[Status.PENDING])


def get_status() -> DockerStatusInfo:
    return DockerStatusInfo(status=STATUS.status.value, description=STATUS.description)


async def set_status(context: ServiceContext, new_status: str, extra: str | None = None) -> None:
    global STATUS
    assert new_status in Status.__members__
    status = Status(new_status)
    STATUS = APPS_STATUS(
        status,
        f'{STATUS_DESCRIPTIONS[status]}:\n{extra}' if extra else STATUS_DESCRIPTIONS[status],
    )
    context.middleware.send_event('docker.state', 'CHANGED', fields=get_status().model_dump())


async def before_start_check(context: ServiceContext) -> None:
    try:
        if not await license_active(context):
            raise CallError('System is not licensed to use Applications')

        await docker_validate_fs(context)
    except CallError as e:
        if e.errno != CallError.EDATASETISLOCKED:
            await context.call2(
                context.s.alert.oneshot_create,
                ApplicationsConfigurationFailedAlert(error=e.errmsg),
            )

        await set_status(context, Status.FAILED.value, f'Could not validate applications setup ({e.errmsg})')
        raise

    await context.call2(context.s.alert.oneshot_delete, 'ApplicationsConfigurationFailed', None)


async def after_start_check(context: ServiceContext) -> None:
    if await context.middleware.call('service.started', 'docker'):
        await set_status(context, Status.RUNNING.value)
        await context.call2(context.s.alert.oneshot_delete, 'ApplicationsStartFailed', None)
    else:
        await set_status(context, Status.FAILED.value, 'Failed to start docker service')
        await context.call2(
            context.s.alert.oneshot_create,
            ApplicationsStartFailedAlert(error='Docker service could not be started'),
        )


async def start_service(context: ServiceContext, mount_datasets: bool = False) -> None:
    await set_status(context, Status.INITIALIZING.value)
    catalog_sync_job = None
    try:
        await before_start_check(context)
        if mount_datasets:
            catalog_sync_job = await mount_docker_ds(context)

        config = await context.call2(context.s.docker.config)
        # Make sure correct ix-apps dataset is mounted
        if not await ix_apps_is_mounted(context, config.dataset):
            raise CallError(f'{config.dataset!r} dataset is not mounted on {IX_APPS_MOUNT_PATH!r}')
        await (
            await context.middleware.call('service.control', 'START', 'docker', {'timeout': DOCKER_START_TIMEOUT})
        ).wait(raise_error=True)
    except Exception as e:
        await set_status(context, Status.FAILED.value, str(e))
        raise
    else:
        await context.middleware.call('app.certificate.redeploy_apps_consuming_outdated_certs')
    finally:
        if catalog_sync_job:
            await catalog_sync_job.wait()


async def initialize_state(context: ServiceContext) -> None:
    if not await context.middleware.call('system.ready'):
        # Status will be automatically updated when system is ready
        return

    if not (await context.call2(context.s.docker.config)).pool:
        await set_status(context, Status.UNCONFIGURED.value)
    else:
        if await context.middleware.call('service.started', 'docker'):
            await set_status(context, Status.RUNNING.value)
        else:
            await set_status(context, Status.FAILED.value)


async def validate_state(context: ServiceContext, raise_error: bool = True) -> bool:
    # When `raise_error` is unset, we return boolean true if there was no issue with the state
    error_str = ''
    if not (await context.call2(context.s.docker.config)).pool:
        error_str = 'No pool configured for Docker'
    if not error_str and not await context.middleware.call('service.started', 'docker'):
        error_str = 'Docker service is not running'
    if not await license_active(context):
        error_str = 'System is not licensed to use Applications'

    if error_str and raise_error:
        raise CallError(error_str)

    return bool(error_str) is False


async def periodic_check(context: ServiceContext) -> None:
    if await validate_state(context, False) is False:
        return

    try:
        await (await context.call2(context.s.catalog.sync)).wait()
    except CallError as e:
        if e.errno != errno.EBUSY:
            raise

    docker_config = await context.call2(context.s.docker.config)
    if docker_config.enable_image_updates:
        context.create_task(context.middleware.call('app.image.op.check_update'))


def terminate_timeout() -> int:
    """
    Return timeout value for terminate method.
    We give DOCKER_SHUTDOWN_TIMEOUT seconds for Docker to stop gracefully.
    """
    return DOCKER_SHUTDOWN_TIMEOUT


async def terminate(context: ServiceContext) -> None:
    """
    Gracefully stop Docker service during system shutdown/reboot.
    Only applies to single node systems (not HA).
    Waits up to DOCKER_SHUTDOWN_TIMEOUT seconds for Docker to stop gracefully.
    """
    if not await context.middleware.call('failover.licensed') and await context.middleware.call(
        'system.state'
    ) == 'SHUTTING_DOWN' and await context.middleware.call('service.started', 'docker'):
        try:
            job_id = await context.middleware.call('service.control', 'STOP', 'docker')
            await job_id.wait(DOCKER_SHUTDOWN_TIMEOUT)
        except Exception as e:
            context.logger.warning('Failed to gracefully stop Docker service: %s', e)
