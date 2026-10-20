from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, Iterable, Sequence, cast

from middlewared.alert.base import OneShotAlertClass
from middlewared.alert.source.sharing_tasks import ShareLockedAlert, TaskLockedAlert
from middlewared.api import API_LOADING_FORBIDDEN

from .crud_service import GenericCRUDService
from .decorators import pass_app, private
from .sharing_task_service_part import (
    MOUNT_RESOLVE_DELAY,
    SharingTaskServicePart,
    resolve_stored_paths,
    send_resolved_events,
)

if not API_LOADING_FORBIDDEN:
    from middlewared.api.current import QueryOptions

if TYPE_CHECKING:
    from middlewared.main import Middleware
    from middlewared.utils.types import AuditCallback


__all__ = ("GenericSharingTaskService", "GenericSharingService", "GenericTaskPathService")


class GenericSharingTaskService[E, PK = int](GenericCRUDService[E, PK]):
    """Typesafe base for share/task services that carry a filesystem path.

    Pairs with a :class:`SharingTaskServicePart` (set as ``self._svc_part`` in the leaf's
    ``__init__``). Read/write/locked logic lives on the part; this class owns the
    service-level concerns that must stay registered as service methods: path resolution
    hooks, locked-alert lifecycle and the ``update``/``delete`` alert cleanup.

    Mirrors the legacy :class:`SharingTaskService` while coexisting with it untouched, the
    same way :class:`GenericCRUDService` coexists with :class:`CRUDService`.
    """

    # Field configuration (path/enabled/locked field names) and the datastore live on the
    # service part (self._svc_part, set by the leaf's __init__). The service reads them from
    # there; the LockableFSAttachmentDelegate reads them off the running instance's part too.
    _svc_part: SharingTaskServicePart[E, PK]

    # Supplied by the leaf:
    share_task_type: str
    path_resolution_filters: Iterable[Sequence[Any]] | None = None
    # Supplied by GenericSharingService / GenericTaskPathService:
    locked_alert_class: type[OneShotAlertClass]

    def __init__(self, middleware: Middleware) -> None:
        super().__init__(middleware)
        self._mounted_unresolved: set[str] = set()
        # Register path resolution hooks for all share/task services
        middleware.register_hook("dataset.post_unlock", self.resolve_paths, sync=True)
        middleware.register_hook("pool.post_import", self.resolve_paths, sync=True)
        middleware.register_hook("zfs.dataset.mounted", self.resolve_mounted_paths, sync=False)

    @classmethod
    @private
    async def resolve_paths(
        cls,
        middleware: Middleware,
        *_args: Any,
        datasets: list[dict[str, Any]] | None = None,
        mountpoints: set[str] | None = None,
    ) -> None:
        """
        Resolve paths again and store the dataset and relative path each one is in.

        Every path is resolved unless `datasets` (the datasets ``dataset.post_unlock`` passes) or `mountpoints`
        (from `resolve_mounted_paths`) narrow it to the paths they can have changed. Positional arguments are
        accepted but unused: ``pool.post_import`` passes the pool, and every path is resolved after an import.

        IMPORTANT: Used by migration/0018_resolve_dataset_paths.py
        """
        namespace: str = getattr(cls._config, "namespace")  # cls._config is typed `type` at the metaclass level
        # Datastore now lives on the service part; read it off the running instance (the part
        # is set at runtime in the leaf's __init__, mirroring GenericCRUDService._svc_part).
        part = getattr(middleware.get_service(namespace), "_svc_part")
        changed = await resolve_stored_paths(
            middleware,
            namespace,
            part._datastore,
            part._datastore_prefix,
            part.path_field,
            cls.path_resolution_filters,
            datasets=None if datasets is None else [ds["name"] for ds in datasets],
            mountpoints=mountpoints,
        )
        if changed and getattr(cls._config, "event_send"):
            try:
                entries = await part.query(
                    [[part._datastore_primary_key, "in", changed]], QueryOptions(force_sql_filters=True)
                )
                send_resolved_events(middleware, namespace, entries)
            except Exception:
                # Raising would have the hook's arguments logged, and dataset.post_unlock's carry encryption keys
                middleware.logger.error("%s: failed to send change events for %r", namespace, changed, exc_info=True)

    @private
    async def resolve_mounted_paths(self, middleware: Middleware, data: dict[str, Any]) -> None:
        """``zfs.dataset.mounted`` hook: resolve the paths under a dataset that was just mounted, together with
        those under any other dataset mounted in the next `MOUNT_RESOLVE_DELAY` seconds."""
        waiting = bool(self._mounted_unresolved)
        self._mounted_unresolved.add(data["mountpoint"])
        if waiting:
            return

        await asyncio.sleep(MOUNT_RESOLVE_DELAY)
        mountpoints, self._mounted_unresolved = self._mounted_unresolved, set()
        await self.resolve_paths(middleware, mountpoints=mountpoints)

    @private
    async def human_identifier(self, share_task: Any) -> Any:
        raise NotImplementedError

    @private
    async def generate_locked_alert(self, share_task_id: int) -> None:
        share_task = await self.get_instance(cast(PK, share_task_id))
        await self.call2(
            self.s.alert.oneshot_create,
            self.locked_alert_class.from_args(
                {
                    "type": self.share_task_type,
                    "identifier": await self.human_identifier(share_task),
                    "id": getattr(share_task, "id"),
                }
            ),
        )

    @private
    async def remove_locked_alert(self, share_task_id: int) -> None:
        await self.call2(
            self.s.alert.oneshot_delete,
            self.locked_alert_class.config.name,
            f"{self.share_task_type}_{share_task_id}",
        )

    @pass_app(message_id=True)  # type: ignore[misc]  # pass_app is an untyped attribute-tagger decorator
    async def update(self, app: Any, audit_callback: AuditCallback, message_id: Any, id_: PK, data: Any) -> E:
        rv = await super().update(app, audit_callback, message_id, id_, data)
        enabled = getattr(rv, self._svc_part.enabled_field)
        locked = getattr(rv, self._svc_part.locked_field)
        if not enabled or not locked:
            await self.remove_locked_alert(cast(int, id_))
        return cast(E, rv)

    update.audit_callback = True

    @pass_app(message_id=True)  # type: ignore[misc]  # pass_app is an untyped attribute-tagger decorator
    async def delete(self, app: Any, audit_callback: AuditCallback, message_id: Any, id_: PK, *args: Any) -> Any:
        rv = await super().delete(app, audit_callback, message_id, id_, *args)
        await self.remove_locked_alert(cast(int, id_))
        return rv

    delete.audit_callback = True


class GenericSharingService[E, PK = int](GenericSharingTaskService[E, PK]):
    locked_alert_class = ShareLockedAlert

    @private
    async def human_identifier(self, share_task: Any) -> Any:
        if isinstance(share_task, dict):
            # FIXME: Remove all the cases where this is dict
            return share_task["name"]
        return share_task.name


class GenericTaskPathService[E, PK = int](GenericSharingTaskService[E, PK]):
    locked_alert_class = TaskLockedAlert

    @private
    async def human_identifier(self, share_task: Any) -> Any:
        return await self._svc_part.get_path_field(share_task)
