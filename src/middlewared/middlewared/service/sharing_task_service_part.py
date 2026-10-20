from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from middlewared.async_validators import check_path_resides_within_volume
from middlewared.plugins.zfs_.validation_utils import check_zvol_in_boot_pool_using_path
from middlewared.utils.mount import resolve_dataset_path
from middlewared.utils.path import FSLocation, path_location
from middlewared.utils.service.path import check_path_service_share_allowed, check_path_service_write_allowed

from .crud_service_part import CRUDServicePart

if TYPE_CHECKING:
    from middlewared.main import Middleware
    from middlewared.service_exception import ValidationErrors


__all__ = (
    "LocalPathInfo",
    "MOUNT_RESOLVE_DELAY",
    "SharingServicePart",
    "SharingTaskServicePart",
    "dataset_split",
    "resolve_stored_paths",
    "send_resolved_events",
    "validate_path_service_share",
    "validate_path_service_write",
)

MOUNT_RESOLVE_DELAY = 2
"""Seconds a share or task service waits after a dataset mounts before resolving the paths under it, so that the
burst of mounts a pool import or a recursive unlock makes is resolved together."""


@dataclass(slots=True, frozen=True, kw_only=True)
class LocalPathInfo:
    """What a share or task's read-only mode says about the local path it holds.

    `readonly_field` is the field that decides -- a share's read-only flag, a task's direction. `readonly`
    is what that field currently says.
    """

    readonly_field: str
    readonly: bool


def dataset_split(data: Any) -> tuple[str | None, str | None]:
    """The dataset a path resolved to and the path within it, from a row or a model, `None` for both where the
    path has not been resolved."""
    if isinstance(data, dict):
        return data.get("dataset"), data.get("relative_path")
    return data.dataset, data.relative_path


async def resolve_stored_paths(
    middleware: Middleware,
    namespace: str,
    datastore: str,
    prefix: str,
    path_field: str,
    filters: Iterable[Sequence[Any]] | None,
    *,
    datasets: list[str] | None = None,
    mountpoints: set[str] | None = None,
) -> list[int]:
    """Resolve the path of each row of a share or task table again and store the dataset and relative path it
    resolves to, returning the ids of the rows whose stored values changed.

    Every row is resolved unless the caller says what changed. With `datasets`, the datasets just unlocked, only
    rows that are unresolved or whose dataset is one of them, inside one or above one are. With `mountpoints`, the
    mountpoints of datasets just mounted, only rows whose path is under one of them are. A row whose path does not
    resolve keeps what it has stored.

    Args:
        middleware: Middleware instance
        namespace: The service's namespace, for logging
        datastore: The service's table
        prefix: The table's column prefix
        path_field: The column, without the prefix, that holds the path
        filters: Datastore filters selecting the rows that have a path to resolve
        datasets: Names of datasets just unlocked
        mountpoints: Mountpoints of datasets just mounted

    Returns:
        The ids of the rows updated
    """
    changed: list[int] = []
    for row in await middleware.call("datastore.query", datastore, list(filters or [])):
        path = row[prefix + path_field]
        stored = (row[prefix + "dataset"], row[prefix + "relative_path"])
        # A cloud backup's zvol source is never under a dataset's mountpoint
        if not path or not path.startswith("/mnt/"):
            continue
        if datasets is not None and stored[0] is not None and not any(
            stored[0] == name or stored[0].startswith(f"{name}/") or name.startswith(f"{stored[0]}/")
            for name in datasets
        ):
            continue
        if mountpoints is not None and not any(
            path == mountpoint or path.startswith(f"{mountpoint}/") for mountpoint in mountpoints
        ):
            continue

        try:
            resolved = await middleware.run_in_thread(resolve_dataset_path, path, middleware)
            if resolved[0] is None:
                middleware.logger.debug("%s id=%d: %r does not resolve to a dataset", namespace, row["id"], path)
                continue
            if resolved == stored:
                continue
            # The row may have been given a new path, or deleted, while the rows before it resolved
            if not await middleware.call(
                "datastore.query", datastore, [["id", "=", row["id"]], [prefix + path_field, "=", path]]
            ):
                continue

            await middleware.call(
                "datastore.update",
                datastore,
                row["id"],
                {prefix + "dataset": resolved[0], prefix + "relative_path": resolved[1]},
            )
        except Exception:
            middleware.logger.error(
                "%s id=%d: failed to resolve the dataset of %r", namespace, row["id"], path, exc_info=True
            )
            continue

        middleware.logger.info("%s id=%d: %r resolved to dataset %r at %r", namespace, row["id"], path, *resolved)
        changed.append(row["id"])

    return changed


def send_resolved_events(middleware: Middleware, namespace: str, entries: Iterable[Any]) -> None:
    """Send the change event for each share or task whose stored dataset and relative path `resolve_stored_paths`
    updated, which writes them past the CRUD methods that would otherwise send it."""
    for entry in entries:
        if isinstance(entry, BaseModel):
            entry = entry.model_dump()
        middleware.send_event(f"{namespace}.query", "CHANGED", id=entry["id"], fields=entry)


async def validate_path_service_write(
    middleware: Middleware,
    verrors: ValidationErrors,
    schema: str,
    path_field: str,
    path: str,
    data: Any,
    local_path_info: LocalPathInfo | None,
) -> None:
    """Ask `check_path_service_write_allowed` about a share or task's local path, where it is the one writing there.
    A path whose writes belong to another service is refused wherever on that service's dataset it points.

    `local_path_info` is what the share or task answered, None where it always writes its local path. A
    write refused for want of the read-only flag is reported on that flag, since setting it is the fix.
    """
    if local_path_info is None:
        field, writes = path_field, True
    else:
        field, writes = local_path_info.readonly_field, not local_path_info.readonly
    if not writes:
        return
    dataset, relative_path = dataset_split(data)
    await check_path_service_write_allowed(verrors, middleware, f"{schema}.{field}", path, dataset, relative_path)


async def validate_path_service_share(
    middleware: Middleware,
    verrors: ValidationErrors,
    schema: str,
    path_field: str,
    path: str,
    data: Any,
    readonly_field: str | None,
) -> None:
    """Ask `check_path_service_share_allowed` about a share's local path: where another service keeps private
    state on that path's dataset, the share may serve only what that service keeps for clients.

    A task is not held to this; what it copies goes to the administrator. `readonly_field` is the share's
    read-only flag, None where it has none -- such a share writes whatever it is given, so
    `validate_path_service_write` has already refused the whole of such a dataset on this same field.
    """
    if readonly_field is None or path_location(path) is not FSLocation.LOCAL:
        return
    dataset, relative_path = dataset_split(data)
    await check_path_service_share_allowed(
        verrors, middleware, f"{schema}.{path_field}", path, dataset, relative_path
    )


class SharingTaskServicePart[E, PK = int](CRUDServicePart[E, PK]):
    """
    Typesafe service-part base for share/task services that carry a filesystem path.

    Holds everything a :class:`GenericSharingTaskService` needs on the read/write path:
    path validation/splitting, the ``locked`` field computation, tier info and the
    extend/extend_context plumbing. Concrete leaf parts subclass this and override the
    ``sharing_task_extend`` / ``sharing_task_extend_context`` hooks instead of wiring the
    old string-based ``datastore_extend`` / ``datastore_extend_context`` Config methods.
    """

    __slots__ = ()

    path_field: str = "path"
    allowed_path_types: list[FSLocation] = [FSLocation.LOCAL]
    enabled_field: str = "enabled"
    locked_field: str = "locked"
    include_tier_info: bool = False
    readonly_field: str | None = None
    """The flag that makes the share or task read-only for its local path, or None where nothing does: what
    `local_path_info` reads unless overridden."""

    async def sharing_task_extend(self, data: dict[str, Any], service_context: Any) -> dict[str, Any]:
        """Per-row transform for this specific service (replaces legacy ``datastore_extend``).

        ``service_context`` is whatever ``sharing_task_extend_context`` returned (``None`` by default)."""
        return data

    async def sharing_task_extend_context(self, rows: list[dict[str, Any]], extra: dict[str, Any]) -> Any:
        return None

    async def extend_context(self, rows: list[dict[str, Any]], extra: dict[str, Any]) -> dict[str, Any]:
        retrieve_locked_info = extra.get("retrieve_locked_info", True)
        if select := extra.get("select"):
            select_fields = set()
            for entry in select:
                if isinstance(entry, list) and entry:
                    select_fields.add(entry[0])
                elif isinstance(entry, str):
                    select_fields.add(entry)
            if self.locked_field not in select_fields:
                retrieve_locked_info = False

        tier_map: dict[Any, Any] = {}
        if self.include_tier_info:
            datasets = [r["dataset"] for r in rows if r.get("dataset")]
            if datasets:
                tier_map = await self.call2(self.s.zfs.tier.bulk_get_tier_info, datasets)

        return {
            "service_extend": await self.sharing_task_extend_context(rows, extra),
            "retrieve_locked_info": retrieve_locked_info,
            "tier_map": tier_map,
        }

    async def extend(self, data: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        data = await self.sharing_task_extend(data, context["service_extend"])

        if context["retrieve_locked_info"]:
            data[self.locked_field] = await self.sharing_task_determine_locked(data)
        else:
            data[self.locked_field] = None

        if self.include_tier_info and "tier" not in data:
            data["tier"] = context["tier_map"].get(data.get("dataset"))

        return data

    async def get_path_field(self, data: E) -> Any:
        return getattr(data, self.path_field)

    async def sharing_task_determine_locked(self, data: dict[str, Any]) -> bool:
        path = data[self.path_field]
        if path_location(path) is not FSLocation.LOCAL:
            return False

        # When the dataset is resolved, pass it directly to avoid iterating over
        # relative_path subdirectory components, which are not datasets and always
        # produce spurious EZFS_NOENT lookups.
        return await self.call2(self.s.zfs.resource.path_is_locked, data.get("dataset") or path)

    async def validate_external_path(self, verrors: ValidationErrors, name: str, path: str) -> None:
        raise NotImplementedError

    async def validate_zvol_path(self, verrors: ValidationErrors, name: str, path: str) -> None:
        if check_zvol_in_boot_pool_using_path(path):
            verrors.add(name, "Disk residing in boot pool cannot be consumed and is not supported")

    async def validate_local_path(self, verrors: ValidationErrors, name: str, path: str) -> None:
        await check_path_resides_within_volume(verrors, self.middleware, name, path)

    async def local_path_info(self, data: dict[str, Any]) -> LocalPathInfo | None:
        """Whether the share or task only reads its local path, and the field that decides it -- a share's
        read-only flag, a task's direction -- or None where it always writes there. What `validate_path_field`
        passes to `validate_path_service_write`."""
        if self.readonly_field is None:
            return None
        return LocalPathInfo(readonly_field=self.readonly_field, readonly=bool(data[self.readonly_field]))

    async def validate_path_field(
        self, data: dict[str, Any], schema: str, verrors: ValidationErrors, *, split_path: bool = False
    ) -> ValidationErrors:
        """Validate the path field and optionally split it into dataset and relative_path components.

        Performs path validation based on location type (LOCAL/EXTERNAL/ZVOL) and optionally
        resolves the path to its ZFS dataset components. A local path whose writes belong to another
        service is refused unless `local_path_info` says this share or task only reads it."""
        name = f"{schema}.{self.path_field}"
        path = data[self.path_field]
        await self.validate_zvol_path(verrors, name, path)
        loc = path_location(path)

        if loc not in self.allowed_path_types:
            verrors.add(name, f"{loc.name}: path type is not allowed.")

        elif loc is FSLocation.EXTERNAL:
            await self.validate_external_path(verrors, name, path)
            if split_path:
                data.update(dataset=None, relative_path=None)

        elif loc is FSLocation.LOCAL:
            await self.validate_local_path(verrors, name, path)
            if split_path:
                ds, rel_path = await self.middleware.run_in_thread(resolve_dataset_path, path, self.middleware)
                data.update(dataset=ds, relative_path=rel_path)
            await validate_path_service_write(
                self.middleware, verrors, schema, self.path_field, path, data, await self.local_path_info(data)
            )

        else:
            self.logger.error("%s: unknown location type", loc.name)
            raise NotImplementedError

        return verrors


class SharingServicePart[E, PK = int](SharingTaskServicePart[E, PK]):
    __slots__ = ()

    async def validate_path_field(
        self, data: dict[str, Any], schema: str, verrors: ValidationErrors, *, split_path: bool = False
    ) -> ValidationErrors:
        await super().validate_path_field(data, schema, verrors, split_path=split_path)
        await validate_path_service_share(
            self.middleware, verrors, schema, self.path_field, data[self.path_field], data, self.readonly_field
        )
        return verrors
