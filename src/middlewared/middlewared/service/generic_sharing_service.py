from __future__ import annotations

from typing import TYPE_CHECKING, Any, Iterable, Sequence, cast

from middlewared.alert.base import OneShotAlertClass
from middlewared.alert.source.sharing_tasks import ShareLockedAlert, TaskLockedAlert
from middlewared.utils.mount import resolve_dataset_path

from .crud_service import GenericCRUDService
from .decorators import pass_app, private
from .sharing_task_service_part import SharingTaskServicePart

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
        # Register path resolution hooks for all share/task services
        middleware.register_hook("dataset.post_unlock", self.resolve_paths, sync=True)
        middleware.register_hook("pool.post_import", self.resolve_paths, sync=True)

    @classmethod
    @private
    async def resolve_paths(cls, middleware: Middleware, *_args: Any, **_kwargs: Any) -> None:
        """
        Attempt resolution of NULL dataset paths.

        Note: *_args and **_kwargs are accepted but unused. They're required because hooks
        are called with varying arguments (pool.post_import passes pool, dataset.post_unlock
        passes datasets=[...]), but this hook queries for NULL paths independently.

        IMPORTANT: Used by migration/0018_resolve_dataset_paths.py
        """
        namespace: str = getattr(cls._config, "namespace")  # cls._config is typed `type` at the metaclass level
        # Datastore now lives on the service part; read it off the running instance (the part
        # is set at runtime in the leaf's __init__, mirroring GenericCRUDService._svc_part).
        part = getattr(middleware.get_service(namespace), "_svc_part")
        datastore = part._datastore
        prefix = part._datastore_prefix
        path_field = part.path_field

        unresolved = await middleware.call(
            "datastore.query", datastore, [[prefix + "dataset", "=", None], *(cls.path_resolution_filters or [])]
        )
        if not unresolved:
            return

        for entry in unresolved:
            try:
                entry_id = entry["id"]
                path = entry[prefix + path_field]

                dataset, relative_path = await middleware.run_in_thread(resolve_dataset_path, path, middleware)
                if dataset:
                    await middleware.call(
                        "datastore.update",
                        datastore,
                        entry_id,
                        {
                            prefix + "dataset": dataset,
                            prefix + "relative_path": relative_path,
                        },
                    )
                    middleware.logger.info(f"Resolved {namespace} id={entry_id}: {dataset}@'{relative_path}'")
                else:
                    middleware.logger.info(f"Deferred {namespace} id={entry_id}: {path}")
            except Exception as e:
                middleware.logger.debug(f"Failed to resolve {namespace} id={entry_id} path={path}: {e}")

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
