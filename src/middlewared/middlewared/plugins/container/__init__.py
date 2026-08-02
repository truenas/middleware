from __future__ import annotations

import functools
from typing import TYPE_CHECKING, Any

from middlewared.api import api_method
from middlewared.api.current import (
    ContainerCreate,
    ContainerCreateArgs,
    ContainerCreateResult,
    ContainerDeleteArgs,
    ContainerDeleteOptions,
    ContainerDeleteResult,
    ContainerEntry,
    ContainerMigrateArgs,
    ContainerMigrateResult,
    ContainerPoolChoicesArgs,
    ContainerPoolChoicesResult,
    ContainerStartArgs,
    ContainerStartResult,
    ContainerStopArgs,
    ContainerStopOptions,
    ContainerStopResult,
    ContainerUpdate,
    ContainerUpdateArgs,
    ContainerUpdateResult,
    QueryOptions,
)
from middlewared.service import GenericCRUDService, job, private
from middlewared.utils.types import AuditCallback

from .container_device import ContainerDeviceService
from .crud import (
    ContainerCreateWithDataset,
    ContainerCreateWithDatasetArgs,
    ContainerCreateWithDatasetResult,
    ContainerServicePart,
)
from .image import ContainerImageService
from .info import pool_choices
from .lifecycle import handle_shutdown, start_on_boot
from .lifecycle import start as start_container
from .lifecycle import stop as stop_container
from .migrate import maybe_migrate_legacy, relocate_container_origin, restore_legacy_parent_mountpoints
from .migrate import migrate as migrate_containers
from .nsenter import nsenter

if TYPE_CHECKING:
    from truenas_pylibvirt.libvirtd.connection import DomainEvent

    from middlewared.job import Job
    from middlewared.main import Middleware


__all__ = ('ContainerService',)


class ContainerService(GenericCRUDService[ContainerEntry]):

    class Config:
        cli_namespace = 'service.container'
        role_prefix = 'CONTAINER'
        entry = ContainerEntry
        generic = True

    def __init__(self, middleware: Middleware) -> None:
        super().__init__(middleware)
        self.device = ContainerDeviceService(middleware)
        self.image = ContainerImageService(middleware)
        self._svc_part = ContainerServicePart(self.context)

    @api_method(
        ContainerCreateArgs,
        ContainerCreateResult,
        audit='Container create',
        audit_extended=lambda data: data['name'],
        check_annotations=True
    )
    @job(lock=lambda args: f'container_create:{args[0].get("name")}')
    async def do_create(self, job: Job, data: ContainerCreate) -> ContainerEntry:
        """
        Create a Container.
        """
        return await self._svc_part.do_create(job, data)

    @api_method(
        ContainerUpdateArgs,
        ContainerUpdateResult,
        audit='Container update',
        audit_callback=True,
        check_annotations=True,
    )
    async def do_update(self, audit_callback: AuditCallback, id_: int, data: ContainerUpdate) -> ContainerEntry:
        """
        Update a Container.
        """
        return await self._svc_part.do_update(id_, data, audit_callback=audit_callback)

    @api_method(
        ContainerDeleteArgs,
        ContainerDeleteResult,
        audit='Container delete',
        audit_callback=True,
        check_annotations=True,
    )
    @job(lock=lambda args: f'container_delete:{args[0]}')
    def do_delete(
        self, job: Job, audit_callback: AuditCallback, id_: int, options: ContainerDeleteOptions,
    ) -> None:
        """
        Delete a Container.

        The container must be stopped, unless ``force`` is set - which tears it down first.

        A container whose dataset has child datasets or snapshots is refused unless ``recursive`` is
        set, which destroys them along with any clones of those snapshots - data that cannot be
        recovered afterwards.
        """
        return self._svc_part.do_delete(id_, options, audit_callback=audit_callback)

    @api_method(ContainerStartArgs, ContainerStartResult, roles=['CONTAINER_WRITE'], check_annotations=True)
    def start(self, id_: int) -> None:
        """Start container."""
        return start_container(self.context, id_)

    @api_method(ContainerStopArgs, ContainerStopResult, roles=['CONTAINER_WRITE'], check_annotations=True)
    @job(lock=lambda args: f'container_stop_{args[0]}')
    def stop(self, job: Job, id_: int, options: ContainerStopOptions) -> None:
        """Stop ``id`` container."""
        return stop_container(self.context, id_, options)

    @api_method(ContainerMigrateArgs, ContainerMigrateResult, roles=['CONTAINER_WRITE'], check_annotations=True)
    @job(lock='container.migrate', logs=True)
    async def migrate(self, job: Job) -> None:
        """Migrate incus containers to new API."""
        return await migrate_containers(self.context, job)

    @api_method(ContainerPoolChoicesArgs, ContainerPoolChoicesResult, roles=['CONTAINER_READ'], check_annotations=True)
    async def pool_choices(self) -> dict[str, str]:
        """
        Pool choices for container creation.
        """
        return await pool_choices(self.context)

    @api_method(ContainerCreateWithDatasetArgs, ContainerCreateWithDatasetResult, private=True, check_annotations=True)
    async def create_with_dataset(self, data: ContainerCreateWithDataset) -> ContainerEntry:
        return await self._svc_part.create_with_dataset(data)

    @private
    def delete_container_from_libvirt(self, container: ContainerEntry) -> None:
        self._svc_part.delete_container_from_libvirt(container)

    @private
    def delete_container_from_db(self, container: ContainerEntry) -> None:
        self._svc_part.delete_container_from_db(container)

    @private
    async def migrate_and_start_on_boot(self) -> None:
        """Bring containers up on boot, migrating any legacy incus ones first.

        Shared by the ``system.ready`` path and the failover path so the ordering
        lives in one place: HA systems ignore ``system.ready`` and would otherwise
        start containers without ever migrating them.
        """
        await self.call2(self.s.container.maybe_migrate_legacy)
        await self.call2(self.s.container.start_on_boot)

    @private
    def start_on_boot(self) -> None:
        start_on_boot(self.context)

    @private
    async def handle_shutdown(self) -> None:
        await handle_shutdown(self.context)

    @private
    async def nsenter(self, id_: int) -> list[str]:
        return await nsenter(self.context, id_)

    @private
    async def maybe_migrate_legacy(self) -> None:
        return await maybe_migrate_legacy(self.context)

    @private
    def relocate_container_origin(self, container_ds: str) -> str:
        return relocate_container_origin(self.context, container_ds)

    @private
    def restore_legacy_parent_mountpoints(self, pool: str) -> None:
        restore_legacy_parent_mountpoints(self.context, pool)


async def __event_system_ready(middleware: Middleware, event_type: str, args: Any) -> None:
    # we ignore the 'ready' event on an HA system since the failover event plugin
    # is responsible for starting this service, however, the containers still need to be
    # initialized (which is what the above callers are doing)
    if await middleware.call('failover.licensed'):
        return

    middleware.create_task(middleware.call2(middleware.services.container.migrate_and_start_on_boot))


async def __event_system_shutdown(middleware: Middleware, event_type: str, args: Any) -> None:
    middleware.create_task(middleware.call2(middleware.services.container.handle_shutdown))


def domain_event_callback(middleware: Middleware, event: DomainEvent) -> None:
    containers = middleware.call_sync2(
        middleware.services.container.query, [['uuid', '=', event.uuid]], QueryOptions(force_sql_filters=True)
    )
    if containers:
        container = containers[0]
        middleware.send_event('container.query', 'CHANGED', id=container.id, fields=container.model_dump())


async def setup(middleware: Middleware) -> None:
    middleware.event_subscribe('system.ready', __event_system_ready)
    middleware.event_subscribe('system.shutdown', __event_system_shutdown)
    middleware.libvirt_domains_manager.containers.connection.register_domain_event_callback(
        functools.partial(domain_event_callback, middleware)
    )
    if await middleware.call('system.ready'):
        # Reconcile runtime state on every middleware startup. system.ready is
        # only fired at first boot, so a `systemctl restart middlewared` would
        # otherwise skip the boot-path reconcile. Idempotent; safe to run again
        # from start_on_boot at boot time.
        try:
            await middleware.run_in_thread(middleware.libvirt_domains_manager.reconcile_runtime_state)
        except Exception:
            middleware.logger.error('Failed to reconcile container runtime state on startup', exc_info=True)
