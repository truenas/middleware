from __future__ import annotations

from typing import TYPE_CHECKING, Any

from middlewared.async_validators import check_path_resides_within_volume
from middlewared.plugins.zfs_.validation_utils import check_zvol_in_boot_pool_using_path
from middlewared.utils.mount import resolve_dataset_path
from middlewared.utils.path import FSLocation, path_location

from .crud_service_part import CRUDServicePart

if TYPE_CHECKING:
    from middlewared.service_exception import ValidationErrors
    from middlewared.utils.service.call_mixin import CallMixin


__all__ = ("SharingTaskServicePart", "dataset_split", "validate_s3_bucket_write")


def dataset_split(data: Any) -> tuple[str | None, str | None]:
    """The dataset a path resolved to and the path within it, from a row or a model, `None` for both where the
    path has not been resolved."""
    if isinstance(data, dict):
        return data.get("dataset"), data.get("relative_path")
    return data.dataset, data.relative_path


async def validate_s3_bucket_write(
    caller: CallMixin,
    verrors: ValidationErrors,
    schema: str,
    path_field: str,
    path: str,
    data: Any,
    readonly: tuple[str, bool] | None,
) -> None:
    """Refuse a local path on an S3 bucket's dataset to anything that writes it. A bucket is written only
    through the S3 service, whoever holds the path and wherever on the dataset it points.

    `readonly` is what `local_path_readonly` answered: the field that decides and whether it is read-only, or
    None where it always writes. A write refused for want of the read-only flag is reported on that flag,
    since setting it is the fix.
    """
    if readonly is None:
        field, writes = path_field, True
    else:
        field, writes = readonly[0], not readonly[1]
    if not writes:
        return
    dataset, relative_path = dataset_split(data)
    await caller.call2(
        caller.s.sharing.s3.validate_writable_path,
        verrors, f"{schema}.{field}", path, dataset, relative_path,
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
    `local_path_readonly` reads unless overridden."""

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
        # produce spurious EZFS_NOENT lookups. path_in_locked_datasets accepts bare
        # dataset names (e.g. docker and KMIP already call it this way).
        return bool(await self.middleware.call("pool.dataset.path_in_locked_datasets", data.get("dataset") or path))

    async def validate_external_path(self, verrors: ValidationErrors, name: str, path: str) -> None:
        raise NotImplementedError

    async def validate_zvol_path(self, verrors: ValidationErrors, name: str, path: str) -> None:
        if check_zvol_in_boot_pool_using_path(path):
            verrors.add(name, "Disk residing in boot pool cannot be consumed and is not supported")

    async def validate_local_path(self, verrors: ValidationErrors, name: str, path: str) -> None:
        await check_path_resides_within_volume(verrors, self.middleware, name, path)

    async def local_path_readonly(self, data: dict[str, Any]) -> tuple[str, bool] | None:
        """Whether the share or task only reads its local path, and the field that decides it -- a share's
        read-only flag, a task's direction -- or None where it always writes there. What `validate_path_field`
        tells `sharing.s3`, which never lets a bucket be written from beside the S3 service."""
        if self.readonly_field is None:
            return None
        return self.readonly_field, bool(data[self.readonly_field])

    async def validate_path_field(
        self, data: dict[str, Any], schema: str, verrors: ValidationErrors, *, split_path: bool = False
    ) -> ValidationErrors:
        """Validate the path field and optionally split it into dataset and relative_path components.

        Performs path validation based on location type (LOCAL/EXTERNAL/ZVOL) and optionally
        resolves the path to its ZFS dataset components. A local path on an S3 bucket's dataset is
        allowed only as `local_path_readonly` and `sharing.s3` agree."""
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
            await validate_s3_bucket_write(
                self, verrors, schema, self.path_field, path, data, await self.local_path_readonly(data)
            )

        else:
            self.logger.error("%s: unknown location type", loc.name)
            raise NotImplementedError

        return verrors
