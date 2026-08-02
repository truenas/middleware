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
    ContainerFilesystemDevice,
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
    ZFSResourceQuery,
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
from .utils import container_dataset

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


async def pool_post_import(middleware: Middleware, pool: dict[str, Any] | None = None, **kwargs: Any) -> None:
    """Re-point containers at their storage after their pool was imported under a new name.

    A container's dataset is always `<pool>/.truenas_containers/containers/<name>`, so the location
    under the newly imported pool is derived rather than guessed. The remap is only committed when
    the old pool is genuinely gone, the derived dataset actually exists, and no other container
    already claims it -- otherwise the record is left alone for the user to sort out, which is the
    safer failure.
    """
    if pool is None:
        # Fired with no pool on boot
        return

    containers = await middleware.call2(middleware.services.container.query)
    assert isinstance(containers, list)
    known_pools = {p['name'] for p in await middleware.call('pool.query')}
    claimed = {c.dataset for c in containers}

    for container in containers:
        old_pool = container.dataset.split('/')[0]
        if old_pool == pool['name'] or old_pool in known_pools:
            continue

        dataset = f'{container_dataset(pool["name"])}/containers/{container.name}'
        if dataset in claimed:
            middleware.logger.warning(
                '%s: not re-pointing container at %r after pool rename, another container already uses it',
                container.name, dataset,
            )
            continue

        if not await middleware.call2(
            middleware.services.zfs.resource.query_impl,
            ZFSResourceQuery(paths=[dataset], properties=None),
        ):
            continue

        # Written through the datastore rather than `container.update` / `container.device.update`
        # so that validation of an unrelated part of the container (a missing bridge device, say)
        # cannot fail the pool import. One container failing must not abort the import or stop the
        # rest from being re-pointed, so each is applied behind its own boundary.
        try:
            for device in container.devices:
                if not isinstance(device.attributes, ContainerFilesystemDevice):
                    continue

                source = device.attributes.source
                if source == f'/mnt/{old_pool}' or source.startswith(f'/mnt/{old_pool}/'):
                    attributes = device.attributes.model_dump()
                    attributes['source'] = f'/mnt/{pool["name"]}' + source[len(f'/mnt/{old_pool}'):]
                    await middleware.call(
                        'datastore.update', 'container.device', device.id, {'attributes': attributes}
                    )

            await middleware.call('datastore.update', 'container.container', container.id, {'dataset': dataset})
        except Exception:
            middleware.logger.error(
                '%s: failed to re-point container at %r after pool rename', container.name, dataset,
                exc_info=True,
            )
            continue

        claimed.add(dataset)
        middleware.logger.info(
            '%s: re-pointed container at %r after its pool was renamed from %r',
            container.name, dataset, old_pool,
        )


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
    middleware.register_hook('pool.post_import', pool_post_import, sync=True)
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
