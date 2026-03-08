from __future__ import annotations

import typing

from middlewared.api import api_method
from middlewared.api.base import Event
from middlewared.api.current import (
    DockerEntry, DockerEventsAddedEvent, DockerStateChangedEvent,
    DockerStatusArgs, DockerStatusResult, DockerStatusInfo,
    DockerUpdateArgs, DockerUpdateResult, DockerUpdate,
    DockerNvidiaPresentArgs, DockerNvidiaPresentResult,
    DockerBackupToPoolArgs, DockerBackupToPoolResult,
    DockerBackupArgs, DockerBackupResult,
    DockerListBackupsArgs, DockerListBackupsResult, DockerBackupMap,
    DockerDeleteBackupArgs, DockerDeleteBackupResult,
    DockerRestoreBackupArgs, DockerRestoreBackupResult,
)
from middlewared.service import GenericConfigService, job, periodic, private

from .backup import backup, delete_backup, list_backups, post_system_update_hook
from .backup_to_pool import backup_to_pool
from .config import DockerConfigServicePart
from .docker_network import DockerNetworkService
from .events import setup_docker_events
from .fs_manage import umount_docker_ds
from .restore_backup import restore_backup
from .service_utils import license_active, restart_docker_service
from .state_management import (
    after_start_check, before_start_check, initialize_state, set_status as docker_set_status, start_service,
    validate_state, periodic_check, terminate, terminate_timeout, get_status,
)
from .state_utils import Status

if typing.TYPE_CHECKING:
    from middlewared.job import Job
    from middlewared.main import Middleware


__all__ = ('DockerService',)


class DockerService(GenericConfigService[DockerEntry]):

    class Config:
        cli_namespace = 'app.docker'
        role_prefix = 'DOCKER'
        entry = DockerEntry
        events = [
            Event(
                name='docker.state',
                description='Docker state events',
                roles=['DOCKER_READ'],
                models={'CHANGED': DockerStateChangedEvent},
            ),
            Event(
                name='docker.events',
                description='Docker container events',
                roles=['DOCKER_READ'],
                models={'ADDED': DockerEventsAddedEvent},
            )
        ]
        generic = True

    def __init__(self, middleware: Middleware) -> None:
        super().__init__(middleware)
        self.network = DockerNetworkService(middleware)
        self._svc_part = DockerConfigServicePart(self.context)

    @api_method(
        DockerBackupArgs, DockerBackupResult,
        audit='Docker: Backup',
        audit_extended=lambda backup_name: backup_name,
        roles=['DOCKER_WRITE'],
        check_annotations=True,
    )
    @job(lock='docker_backup')
    def backup(self, job: Job, backup_name: str | None) -> str:
        """
        Create a backup of existing apps.

        This creates a backup of existing apps on the same pool in which docker is initialized.
        """
        return backup(self.context, job, backup_name)

    @api_method(
        DockerBackupToPoolArgs, DockerBackupToPoolResult,
        audit='Docker: Backup to pool',
        audit_extended=lambda target_pool: target_pool,
        roles=['DOCKER_WRITE'],
        check_annotations=True,
    )
    @job(lock='docker_backup_to_pool')
    async def backup_to_pool(self, job: Job, target_pool: str) -> None:
        """
        Create a backup of existing apps on `target_pool`.

        This creates a backup of existing apps on the `target_pool` specified. If this is executed multiple times,
        in the next iteration it will incrementally backup the apps that have changed since the last backup.

        Note: This will stop the docker service (which means current active apps will be stopped) and
        then start it again after snapshot has been taken of the current apps dataset.
        """
        return await backup_to_pool(self.context, job, target_pool)

    @api_method(
        DockerDeleteBackupArgs, DockerDeleteBackupResult,
        audit='Docker: Deleting Backup',
        audit_extended=lambda backup_name: backup_name,
        roles=['DOCKER_WRITE'],
        check_annotations=True,
    )
    def delete_backup(self, backup_name: str) -> None:
        """
        Delete `backup_name` app backup.
        """
        delete_backup(self.context, backup_name)

    @api_method(DockerListBackupsArgs, DockerListBackupsResult, roles=['DOCKER_READ'], check_annotations=True)
    def list_backups(self) -> DockerBackupMap:
        """
        List existing app backups.
        """
        return list_backups(self.context)

    @api_method(DockerNvidiaPresentArgs, DockerNvidiaPresentResult, roles=['DOCKER_READ'], check_annotations=True)
    async def nvidia_present(self) -> bool:
        """Returns whether a non-isolated NVIDIA GPU is present in the system."""
        return await self.middleware.call('system.advanced.nvidia_present')  # type: ignore[no-any-return]

    @api_method(
        DockerRestoreBackupArgs, DockerRestoreBackupResult,
        audit='Docker: Restoring Backup',
        audit_extended=lambda backup_name: backup_name,
        roles=['DOCKER_WRITE'],
        check_annotations=True,
    )
    @job(lock='docker_restore_backup')
    def restore_backup(self, job: Job, backup_name: str) -> None:
        """
        Restore a backup of existing apps.
        """
        restore_backup(self.context, job, backup_name)

    @api_method(DockerStatusArgs, DockerStatusResult, roles=['DOCKER_READ'], check_annotations=True)
    async def status(self) -> DockerStatusInfo:
        """
        Returns the status of the docker service.
        """
        return get_status()

    @api_method(DockerUpdateArgs, DockerUpdateResult, audit='Docker: Updating Configurations', check_annotations=True)
    @job(lock='docker_update')
    async def do_update(self, job: Job, data: DockerUpdate) -> DockerEntry:
        """
        Update Docker service configuration.
        """
        return await self._svc_part.do_update(job, data)

    @private
    async def after_start_check(self) -> None:
        return await after_start_check(self.context)

    @private
    async def before_start_check(self) -> None:
        await before_start_check(self.context)

    @private
    async def initialize_state(self) -> None:
        return await initialize_state(self.context)

    @private
    async def license_active(self) -> bool:
        return await license_active(self.context)

    @private
    async def restart_service(self) -> None:
        await restart_docker_service(self.context)

    @private
    async def set_status(self, new_status: str, extra: str | None = None) -> None:
        await docker_set_status(self.context, new_status, extra)

    @private
    async def setup_docker_events(self) -> None:
        await self.context.to_thread(setup_docker_events, self.context)

    @private
    async def start_service(self, mount_datasets: bool = False) -> None:
        await start_service(self.context, mount_datasets)

    @private
    @periodic(interval=86400)
    async def state_periodic_check(self) -> None:
        await periodic_check(self.context)

    @private
    async def terminate(self) -> None:
        await terminate(self.context)

    @private
    async def terminate_timeout(self) -> int:
        return terminate_timeout()

    @private
    async def umount_docker_ds(self) -> Job | None:
        return await umount_docker_ds(self.context)

    @private
    async def validate_state(self, raise_error: bool = True) -> bool:
        return await validate_state(self.context, raise_error)


async def _event_system_ready(middleware: Middleware, event_type: str, args: typing.Any) -> None:
    # we ignore the 'ready' event on an HA system since the failover event plugin
    # is responsible for starting this service
    if await middleware.call('failover.licensed'):
        return

    if (await middleware.call2(middleware.services.docker.config)).pool:
        middleware.create_task(middleware.call2(middleware.services.docker.start_service, True))
    else:
        await middleware.call2(middleware.services.docker.set_status, Status.UNCONFIGURED.value)


async def handle_license_update(middleware: Middleware, *args: typing.Any, **kwargs: typing.Any) -> None:
    if not await middleware.call('docker.license_active'):
        # We will like to stop docker in this case
        await middleware.call('service.control', 'STOP', 'docker')


async def setup(middleware: Middleware) -> None:
    middleware.event_subscribe('system.ready', _event_system_ready)
    await middleware.call2(middleware.services.docker.initialize_state)
    middleware.register_hook('system.post_license_update', handle_license_update)
    middleware.register_hook('update.post_run', post_system_update_hook, sync=True)
    # We are going to check in setup docker events if setting up events is relevant or not
    middleware.create_task(middleware.call2(middleware.services.docker.setup_docker_events))
