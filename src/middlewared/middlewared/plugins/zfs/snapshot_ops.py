from __future__ import annotations

import errno
from typing import TYPE_CHECKING, Any

import truenas_pylibzfs

from middlewared.api.current import (
    ZFSResourceSnapshotCloneQuery,
    ZFSResourceSnapshotCountQuery,
    ZFSResourceSnapshotCreateQuery,
    ZFSResourceSnapshotDestroyQuery,
    ZFSResourceSnapshotEntry,
    ZFSResourceSnapshotHoldQuery,
    ZFSResourceSnapshotHoldsQuery,
    ZFSResourceSnapshotQuery,
    ZFSResourceSnapshotQueryBase,
    ZFSResourceSnapshotReleaseQuery,
    ZFSResourceSnapshotRenameQuery,
    ZFSResourceSnapshotRollbackQuery,
)
from middlewared.service_exception import CallError, ValidationError

from .destroy_impl import destroy_impl as _raw_destroy
from .exceptions import (
    ZFSPathAlreadyExistsException,
    ZFSPathHasClonesException,
    ZFSPathHasHoldsException,
    ZFSPathInvalidException,
    ZFSPathNotASnapshotException,
    ZFSPathNotFoundException,
    ZFSRollbackBlockedException,
    ZFSRollbackConflictException,
    ZFSRollbackFailedException,
)
from .rename_promote_clone_impl import clone_impl as _raw_clone
from .rename_promote_clone_impl import rename_impl as _raw_rename
from .snapshot_create_impl import create_snapshots_impl
from .snapshot_hold_release_impl import hold_impl as _raw_hold
from .snapshot_hold_release_impl import release_impl as _raw_release
from .snapshot_query_impl import query_snapshots_impl
from .snapshot_rollback_impl import rollback_impl as _raw_rollback
from .utils import open_resource, reject_overlapping_paths, reject_protected_path

if TYPE_CHECKING:
    from middlewared.service import ServiceContext


def validate_recursive_paths(schema: str, data: ZFSResourceSnapshotQueryBase) -> None:
    if data.recursive:
        # Snapshot paths ("tank@snap") are direct lookups rather than recursive walks, so only
        # the dataset paths can overlap. Duplicates are already rejected by Pydantic UniqueList.
        reject_overlapping_paths(schema, [p for p in data.paths if "@" not in p], "recursive")


def query_impl(tls: Any, data: ZFSResourceSnapshotQuery) -> list[dict[str, Any]]:
    return query_snapshots_impl(tls.lzh, data.model_dump())


def query(context: ServiceContext, data: ZFSResourceSnapshotQuery) -> list[ZFSResourceSnapshotEntry]:
    validate_recursive_paths("zfs.resource.snapshot.query", data)
    try:
        return [
            ZFSResourceSnapshotEntry(**snapshot)
            for snapshot in context.call_sync2(context.s.zfs.resource.snapshot.query_impl, data)
        ]
    except ZFSPathNotFoundException as e:
        raise ValidationError("zfs.resource.snapshot.query", e.message, errno.ENOENT)


def exists(context: ServiceContext, snap_name: str) -> bool:
    # properties=None keeps this to an existence probe rather than a full property fetch.
    try:
        context.call_sync2(
            context.s.zfs.resource.snapshot.query_impl,
            ZFSResourceSnapshotQuery(paths=[snap_name], properties=None),
        )
    except ZFSPathNotFoundException:
        return False
    return True


def count(context: ServiceContext, data: ZFSResourceSnapshotCountQuery) -> dict[str, int]:
    validate_recursive_paths("zfs.resource.snapshot.count", data)
    try:
        return context.call_sync2(context.s.zfs.resource.snapshot.count_impl, data)
    except ZFSPathNotFoundException as e:
        raise ValidationError("zfs.resource.snapshot.count", e.message, errno.ENOENT)


def destroy_impl(tls: Any, data: ZFSResourceSnapshotDestroyQuery) -> tuple[str | None, int | None]:
    reject_protected_path("zfs.resource.snapshot.destroy", data.path, data.bypass)
    return _raw_destroy(tls, data.path, data.recursive, data.all_snapshots, data.bypass, data.defer)


def destroy(context: ServiceContext, data: ZFSResourceSnapshotDestroyQuery) -> None:
    schema = "zfs.resource.snapshot.destroy"
    if data.all_snapshots:
        if "@" in data.path:
            raise ValidationError(schema, "When all_snapshots is True, path must be a dataset path (no '@').")
    elif "@" not in data.path:
        raise ValidationError(
            schema,
            "Path must be a snapshot path (containing '@'). "
            "Use all_snapshots=True to destroy all snapshots for a dataset.",
        )

    try:
        failed, errnum = context.call_sync2(context.s.zfs.resource.snapshot.destroy_impl, data)
    except ZFSPathNotFoundException as e:
        raise ValidationError(schema, e.message, errno.ENOENT)
    except ZFSPathHasClonesException as e:
        raise ValidationError(schema, e.message, errno.EBUSY)
    except ZFSPathHasHoldsException as e:
        raise ValidationError(schema, e.message, errno.EBUSY)

    if failed:
        raise ValidationError(schema, failed, errnum or errno.EFAULT)


def rename_impl(tls: Any, data: ZFSResourceSnapshotRenameQuery) -> None:
    reject_protected_path("zfs.resource.snapshot.rename", data.current_name, data.bypass)
    return _raw_rename(tls, data.current_name, data.new_name, data.recursive, False, False)


def rename(context: ServiceContext, data: ZFSResourceSnapshotRenameQuery) -> None:
    schema = "zfs.resource.snapshot.rename"
    if "@" not in data.current_name:
        raise ValidationError(schema, "current_name must be a snapshot path (containing '@').")
    if "@" not in data.new_name:
        raise ValidationError(schema, "new_name must be a snapshot path (containing '@').")

    current_ds = data.current_name.rsplit("@", 1)[0]
    if current_ds != data.new_name.rsplit("@", 1)[0]:
        raise ValidationError(
            schema,
            f"Cannot rename snapshot to a different dataset. Dataset must remain '{current_ds}'.",
        )

    try:
        context.call_sync2(context.s.zfs.resource.snapshot.rename_impl, data)
    except ZFSPathNotFoundException as e:
        raise ValidationError(schema, e.message, errno.ENOENT)
    except ZFSPathAlreadyExistsException as e:
        raise ValidationError(schema, e.message, errno.EEXIST)


def clone_impl(context: ServiceContext, tls: Any, data: ZFSResourceSnapshotCloneQuery) -> None:
    schema = "zfs.resource.snapshot.clone"
    if "special_small_blocks" in data.properties:
        if context.call_sync2(context.s.zfs.tier.config).enabled:
            raise ValidationError(
                f"{schema}.properties",
                "ZFS tiering is enabled; use zfs.tier.dataset_set_tier to manage special_small_blocks.",
                errno.EINVAL,
            )

    reject_protected_path(schema, data.snapshot, data.bypass)
    reject_protected_path(schema, data.dataset, data.bypass)

    return _raw_clone(tls, current_name=data.snapshot, new_name=data.dataset, properties=data.properties)


def clone(context: ServiceContext, data: ZFSResourceSnapshotCloneQuery) -> None:
    schema = "zfs.resource.snapshot.clone"
    if "@" not in data.snapshot:
        raise ValidationError(schema, "snapshot must be a snapshot path (containing '@').")
    if "@" in data.dataset:
        raise ValidationError(schema, "dataset must be a dataset path (not containing '@').")

    try:
        context.call_sync2(context.s.zfs.resource.snapshot.clone_impl, data)
    except ZFSPathNotFoundException as e:
        raise ValidationError(schema, e.message, errno.ENOENT)
    except ZFSPathAlreadyExistsException as e:
        raise ValidationError(schema, e.message, errno.EEXIST)
    except ZFSPathNotASnapshotException:
        raise ValidationError(schema, f"'{data.snapshot}' is not a snapshot.")


def create_impl(tls: Any, data: ZFSResourceSnapshotCreateQuery) -> Any:
    reject_protected_path("zfs.resource.snapshot.create", data.dataset, data.bypass)
    return create_snapshots_impl(
        tls,
        dataset=data.dataset,
        name=data.name,
        recursive=data.recursive,
        exclude=data.exclude,
        user_properties=data.user_properties,
    )


def create(context: ServiceContext, data: ZFSResourceSnapshotCreateQuery) -> ZFSResourceSnapshotEntry:
    schema = "zfs.resource.snapshot.create"
    if "@" in data.dataset:
        raise ValidationError(schema, "dataset must be a dataset path (not containing '@').")
    if "@" in data.name:
        raise ValidationError(schema, "name must be a snapshot name (not containing '@').")

    try:
        return ZFSResourceSnapshotEntry(**context.call_sync2(context.s.zfs.resource.snapshot.create_impl, data))
    except ZFSPathNotFoundException as e:
        raise ValidationError(schema, e.message, errno.ENOENT)
    except ZFSPathAlreadyExistsException as e:
        raise ValidationError(schema, e.message, errno.EEXIST)
    except ZFSPathInvalidException as e:
        # create_snapshots_impl only raises this when `exclude` leaves no dataset to snapshot
        raise ValidationError(f"{schema}.exclude", str(e), errno.EINVAL)
    except ValueError as e:
        raise ValidationError(schema, str(e), errno.EINVAL)


def hold_impl(tls: Any, data: ZFSResourceSnapshotHoldQuery) -> None:
    reject_protected_path("zfs.resource.snapshot.hold", data.path, data.bypass)
    return _raw_hold(tls, path=data.path, tag=data.tag, recursive=data.recursive)


def hold(context: ServiceContext, data: ZFSResourceSnapshotHoldQuery) -> None:
    schema = "zfs.resource.snapshot.hold"
    if "@" not in data.path:
        raise ValidationError(schema, "path must be a snapshot path (containing '@').")

    try:
        context.call_sync2(context.s.zfs.resource.snapshot.hold_impl, data)
    except ZFSPathNotFoundException as e:
        raise ValidationError(schema, e.message, errno.ENOENT)
    except ValueError as e:
        raise ValidationError(schema, str(e), errno.EINVAL)


def holds_impl(tls: Any, path: str) -> tuple[str, ...]:
    rsrc = open_resource(tls, path)
    return rsrc.get_holds()  # type: ignore[no-any-return]


def holds(context: ServiceContext, data: ZFSResourceSnapshotHoldsQuery) -> list[str]:
    schema = "zfs.resource.snapshot.holds"
    if "@" not in data.path:
        raise ValidationError(schema, "path must be a snapshot path (containing '@').")

    try:
        return list(context.call_sync2(context.s.zfs.resource.snapshot.holds_impl, data.path))
    except ZFSPathNotFoundException as e:
        raise ValidationError(schema, e.message, errno.ENOENT)


def release_impl(tls: Any, data: ZFSResourceSnapshotReleaseQuery) -> None:
    reject_protected_path("zfs.resource.snapshot.release", data.path, data.bypass)
    return _raw_release(tls, path=data.path, tag=data.tag, recursive=data.recursive)


def release(context: ServiceContext, data: ZFSResourceSnapshotReleaseQuery) -> None:
    schema = "zfs.resource.snapshot.release"
    if "@" not in data.path:
        raise ValidationError(schema, "path must be a snapshot path (containing '@').")

    try:
        context.call_sync2(context.s.zfs.resource.snapshot.release_impl, data)
    except ZFSPathNotFoundException as e:
        raise ValidationError(schema, e.message, errno.ENOENT)


def rollback_impl(tls: Any, data: ZFSResourceSnapshotRollbackQuery) -> None:
    reject_protected_path("zfs.resource.snapshot.rollback", data.path, data.bypass)
    try:
        return _raw_rollback(
            tls,
            path=data.path,
            recursive=data.recursive,
            recursive_clones=data.recursive_clones,
            force=data.force,
            recursive_rollback=data.recursive_rollback,
        )
    except truenas_pylibzfs.ZFSException as e:
        raise CallError(f"Failed to rollback {data.path!r}: {e}")
    except ZFSRollbackBlockedException as e:
        raise CallError(e.message, errno.EBUSY)
    except ZFSRollbackFailedException as e:
        raise CallError(e.message, e.errnum)


def rollback(context: ServiceContext, data: ZFSResourceSnapshotRollbackQuery) -> None:
    schema = "zfs.resource.snapshot.rollback"
    try:
        context.call_sync2(context.s.zfs.resource.snapshot.rollback_impl, data)
    except ZFSPathNotFoundException as e:
        raise ValidationError(schema, e.message, errno.ENOENT)
    except ZFSPathNotASnapshotException as e:
        raise ValidationError(schema, e.message, errno.EINVAL)
    except ZFSRollbackConflictException as e:
        raise ValidationError(schema, e.message, errno.EINVAL)
    except ValueError as e:
        raise ValidationError(schema, str(e), errno.EINVAL)
