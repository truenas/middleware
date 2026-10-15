from __future__ import annotations

import errno
from typing import TYPE_CHECKING, Any

import truenas_pylibzfs
from truenas_pylicensed.features import LicenseFeature

from middlewared.api.current import (
    ZFSResourceQuery,
    ZFSResourceSnapshotCloneArgsData,
    ZFSResourceSnapshotCountQuery,
    ZFSResourceSnapshotCreateArgsData,
    ZFSResourceSnapshotDestroyArgsData,
    ZFSResourceSnapshotEntry,
    ZFSResourceSnapshotHoldArgsData,
    ZFSResourceSnapshotHoldsQuery,
    ZFSResourceSnapshotQuery,
    ZFSResourceSnapshotQueryBase,
    ZFSResourceSnapshotReleaseArgsData,
    ZFSResourceSnapshotRenameArgsData,
    ZFSResourceSnapshotRollbackArgsData,
)
from middlewared.service_exception import CallError, ValidationError

from . import resource_query as _resource_query
from .create_impl import ZFS_INVALID_INPUT_ERRORS
from .destroy_impl import destroy_impl as _raw_destroy
from .exceptions import (
    ZFSDestroyFailedException,
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
from .property_management import PROPERTY_TEMPLATES
from .rename_promote_clone_impl import clone_impl as _raw_clone
from .rename_promote_clone_impl import rename_impl as _raw_rename
from .rules_common import (
    apply_acl_defaults,
    reject_bad_acl_combination,
    reject_bad_recordsize,
    reject_bad_user_property_names,
    reject_bad_user_property_values,
    reject_ssb_out_of_range,
    reject_tier_managed_ssb,
    reject_unentitled_dedup,
)
from .snapshot_create_impl import create_snapshots_impl
from .snapshot_hold_release_impl import hold_impl as _raw_hold
from .snapshot_hold_release_impl import release_impl as _raw_release
from .snapshot_query_impl import query_snapshots_impl
from .snapshot_rollback_impl import rollback_impl as _raw_rollback
from .utils import has_internal_path, open_resource, reject_overlapping_paths, reject_protected_path

if TYPE_CHECKING:
    from collections.abc import Iterable

    from middlewared.service import ServiceContext


def validate_recursive_paths(schema: str, data: ZFSResourceSnapshotQueryBase) -> None:
    if data.recursive:
        # Snapshot paths ("tank@snap") are direct lookups rather than recursive walks, so only
        # the dataset paths can overlap. Duplicates are already rejected by Pydantic UniqueList.
        reject_overlapping_paths(schema, [p for p in data.paths if "@" not in p], "recursive")


def list_impl(tls: Any, data: ZFSResourceSnapshotQuery) -> list[dict[str, Any]]:
    return query_snapshots_impl(tls.lzh, data.model_dump())


def list_snapshots(context: ServiceContext, data: ZFSResourceSnapshotQuery) -> list[ZFSResourceSnapshotEntry]:
    validate_recursive_paths("zfs.resource.snapshot.list", data)
    try:
        snapshots = context.call_sync2(context.s.zfs.resource.snapshot.list_impl, data)
    except ZFSPathNotFoundException as e:
        raise ValidationError("zfs.resource.snapshot.list", e.message, errno.ENOENT)
    return [ZFSResourceSnapshotEntry(**snapshot) for snapshot in snapshots]


def exists(context: ServiceContext, snap_name: str) -> bool:
    try:
        return bool(
            context.call_sync2(
                context.s.zfs.resource.snapshot.list_impl,
                ZFSResourceSnapshotQuery(paths=[snap_name], properties=None),
            )
        )
    except ZFSPathNotFoundException:
        return False


def count(context: ServiceContext, data: ZFSResourceSnapshotCountQuery) -> dict[str, int]:
    validate_recursive_paths("zfs.resource.snapshot.count", data)
    try:
        return context.call_sync2(context.s.zfs.resource.snapshot.count_impl, data)
    except ZFSPathNotFoundException as e:
        raise ValidationError("zfs.resource.snapshot.count", e.message, errno.ENOENT)


def destroy_impl(tls: Any, data: ZFSResourceSnapshotDestroyArgsData) -> None:
    reject_protected_path("zfs.resource.snapshot.destroy.path", data.path, data.bypass)
    _raw_destroy(tls, data.path, data.recursive, data.all_snapshots, data.bypass, data.defer)


def destroy(context: ServiceContext, data: ZFSResourceSnapshotDestroyArgsData) -> None:
    schema = "zfs.resource.snapshot.destroy"
    if data.all_snapshots:
        if "@" in data.path:
            raise ValidationError(
                f"{schema}.path", "When all_snapshots is True, path must be a dataset path (no '@').", errno.EINVAL,
            )
    elif "@" not in data.path:
        raise ValidationError(
            f"{schema}.path",
            "Path must be a snapshot path (containing '@'). "
            "Use all_snapshots=True to destroy all snapshots for a dataset.",
            errno.EINVAL,
        )

    try:
        context.call_sync2(context.s.zfs.resource.snapshot.destroy_impl, data)
    except ZFSPathNotFoundException as e:
        raise ValidationError(f"{schema}.path", e.message, errno.ENOENT)
    except ZFSPathHasClonesException as e:
        raise ValidationError(schema, e.message, errno.EBUSY)
    except ZFSPathHasHoldsException as e:
        raise ValidationError(schema, e.message, errno.EBUSY)
    except ZFSDestroyFailedException as e:
        raise ValidationError(schema, e.message, e.errnum)


def _visible(name: str) -> bool:
    return not has_internal_path(name.split("@", 1)[0])


def _announce_added(context: ServiceContext, tls: Any, names: Iterable[str]) -> None:
    if not (visible := [name for name in names if _visible(name)]):
        # empty `paths` would list the snapshots of every pool's root filesystem
        return
    try:
        for row in list_impl(tls, ZFSResourceSnapshotQuery(paths=visible)):
            context.middleware.send_event("zfs.resource.snapshot.list", "ADDED", id=row["name"], fields=row)
    except Exception:
        context.logger.warning("%s: failed to announce new snapshots", visible[0], exc_info=True)


def _announce_holds(context: ServiceContext, tls: Any, paths: Iterable[str]) -> None:
    try:
        for path in paths:
            if not _visible(path):
                continue
            try:
                holds = list(open_resource(tls, path).get_holds())
            except ZFSPathNotFoundException:
                continue
            context.middleware.send_event("zfs.resource.snapshot.list", "CHANGED", id=path, fields={"holds": holds})
    except Exception:
        context.logger.warning("failed to announce snapshot holds", exc_info=True)


def rename_impl(context: ServiceContext, tls: Any, data: ZFSResourceSnapshotRenameArgsData) -> None:
    schema = "zfs.resource.snapshot.rename"
    reject_protected_path(f"{schema}.current_name", data.current_name, data.bypass)
    reject_protected_path(f"{schema}.new_name", data.new_name, data.bypass)
    _raw_rename(tls, data.current_name, data.new_name, data.recursive, False, False)
    if _visible(data.current_name):
        context.middleware.send_event("zfs.resource.snapshot.list", "REMOVED", id=data.current_name)
    _announce_added(context, tls, [data.new_name])


def rename(context: ServiceContext, data: ZFSResourceSnapshotRenameArgsData) -> None:
    schema = "zfs.resource.snapshot.rename"
    if not data.force:
        raise ValidationError(
            f"{schema}.force",
            "No safety checks are performed when renaming ZFS resources; this may break existing usages. "
            "If you understand the risks, please set force and proceed.",
            errno.EINVAL,
        )
    if "@" not in data.current_name:
        raise ValidationError(
            f"{schema}.current_name", "current_name must be a snapshot path (containing '@').", errno.EINVAL,
        )
    if "@" not in data.new_name:
        raise ValidationError(f"{schema}.new_name", "new_name must be a snapshot path (containing '@').", errno.EINVAL)

    current_ds = data.current_name.rsplit("@", 1)[0]
    if current_ds != data.new_name.rsplit("@", 1)[0]:
        raise ValidationError(
            f"{schema}.new_name",
            f"Cannot rename snapshot to a different dataset. Dataset must remain '{current_ds}'.",
            errno.EINVAL,
        )

    try:
        context.call_sync2(context.s.zfs.resource.snapshot.rename_impl, data)
    except ZFSPathNotFoundException as e:
        raise ValidationError(f"{schema}.current_name", e.message, errno.ENOENT)
    except ZFSPathAlreadyExistsException as e:
        raise ValidationError(f"{schema}.new_name", e.message, errno.EEXIST)


def clone_impl(context: ServiceContext, tls: Any, data: ZFSResourceSnapshotCloneArgsData) -> bool:
    schema = "zfs.resource.snapshot.clone"
    reject_protected_path(f"{schema}.snapshot", data.snapshot, data.bypass)
    reject_protected_path(f"{schema}.dataset", data.dataset, data.bypass)
    reject_bad_user_property_names(f"{schema}.user_properties", data.user_properties)
    reject_bad_user_property_values(f"{schema}.user_properties", data.user_properties)

    try:
        parent = open_resource(tls, data.snapshot.split("@", 1)[0])
    except ZFSPathNotFoundException:
        raise ZFSPathNotFoundException(data.snapshot) from None
    is_filesystem = bool(parent.type == truenas_pylibzfs.ZFSType.ZFS_TYPE_FILESYSTEM)
    valid = PROPERTY_TEMPLATES.fs if is_filesystem else PROPERTY_TEMPLATES.vol
    for name in data.properties.model_dump(exclude_none=True):
        if truenas_pylibzfs.ZFSProperty[name.upper()] not in valid:
            kind = "FILESYSTEM" if is_filesystem else "VOLUME"
            raise ValidationError(f"{schema}.properties.{name}", f"{name!r} is not valid for a {kind}.", errno.EINVAL)
    if is_filesystem and data.properties.refreservation == "auto":
        raise ValidationError(f"{schema}.properties.refreservation", "'auto' is only valid on volumes.", errno.EINVAL)
    if (ssb := data.properties.special_small_blocks) is not None:
        if context.call_sync2(context.s.zfs.tier.config).enabled:
            reject_tier_managed_ssb(f"{schema}.properties.special_small_blocks")
        reject_ssb_out_of_range(f"{schema}.properties.special_small_blocks", ssb)
    if is_filesystem and data.properties.recordsize is not None:
        reject_bad_recordsize(
            f"{schema}.properties.recordsize", context, data.dataset.split("/")[0], data.properties.recordsize,
            draid_floor=False,
        )
    if str(data.properties.dedup or "off").lower() != "off":
        reject_unentitled_dedup(
            f"{schema}.properties.dedup",
            context.call_sync2(context.s.truenas.entitlements.check, LicenseFeature.DEDUP),
        )

    properties = data.properties.model_copy()
    if properties.quota == 0:
        properties.quota = None
    if properties.refquota == 0:
        properties.refquota = None
    if is_filesystem:
        if not data.bypass:
            apply_acl_defaults(properties)
        if data.properties.acltype is not None and data.properties.aclmode is not None:
            reject_bad_acl_combination(
                f"{schema}.properties.aclmode", data.properties.acltype, data.properties.aclmode,
            )

    try:
        _raw_clone(
            tls, current_name=data.snapshot, new_name=data.dataset,
            properties=properties.model_dump(exclude_none=True) or None,
            user_properties=data.user_properties or None,
        )
    except ValueError as e:
        raise ValidationError(f"{schema}.properties", str(e), errno.EINVAL)
    except truenas_pylibzfs.ZFSException as e:
        if e.code in ZFS_INVALID_INPUT_ERRORS:
            raise ValidationError(schema, str(e), errno.EINVAL)
        raise

    if not has_internal_path(data.dataset):
        try:
            for row in _resource_query.list_impl(context, tls, ZFSResourceQuery(paths=[data.dataset], properties=None)):
                context.middleware.send_event("zfs.resource.list", "ADDED", id=row["name"], fields=row)
        except Exception:
            context.logger.warning("%s: failed to announce the clone", data.dataset, exc_info=True)
    return is_filesystem


def clone(context: ServiceContext, data: ZFSResourceSnapshotCloneArgsData) -> None:
    schema = "zfs.resource.snapshot.clone"
    if "@" not in data.snapshot:
        raise ValidationError(f"{schema}.snapshot", "snapshot must be a snapshot path (containing '@').", errno.EINVAL)
    if "@" in data.dataset:
        raise ValidationError(
            f"{schema}.dataset", "dataset must be a dataset path (not containing '@').", errno.EINVAL,
        )

    try:
        is_filesystem = context.call_sync2(context.s.zfs.resource.snapshot.clone_impl, data)
    except ZFSPathNotFoundException as e:
        raise ValidationError(f"{schema}.snapshot", e.message, errno.ENOENT)
    except ZFSPathAlreadyExistsException as e:
        raise ValidationError(f"{schema}.dataset", e.message, errno.EEXIST)
    except ZFSPathNotASnapshotException:
        raise ValidationError(f"{schema}.snapshot", f"'{data.snapshot}' is not a snapshot.", errno.EINVAL)

    if is_filesystem and not data.no_mount:
        try:
            context.call_sync2(context.s.zfs.resource.mount, data.dataset)
        except Exception as e:
            raise CallError(f"{data.dataset!r} was created but could not be mounted: {e}") from e


def create_impl(context: ServiceContext, tls: Any, data: ZFSResourceSnapshotCreateArgsData) -> dict[str, Any]:
    reject_protected_path("zfs.resource.snapshot.create.dataset", data.dataset, data.bypass)
    names = create_snapshots_impl(
        tls, dataset=data.dataset, name=data.name, recursive=data.recursive,
        exclude=data.exclude, user_properties=data.user_properties,
    )
    _announce_added(context, tls, names)
    primary = f"{data.dataset}@{data.name}"
    for row in list_impl(tls, ZFSResourceSnapshotQuery(paths=[primary], properties=["creation", "createtxg"])):
        return row
    return {
        "name": primary, "pool": data.dataset.split("/")[0], "dataset": data.dataset, "snapshot_name": data.name,
        "type": "SNAPSHOT", "createtxg": 0, "guid": 0, "holds": None, "properties": {}, "user_properties": {},
    }


def create(context: ServiceContext, data: ZFSResourceSnapshotCreateArgsData) -> ZFSResourceSnapshotEntry:
    schema = "zfs.resource.snapshot.create"
    if "@" in data.dataset:
        raise ValidationError(
            f"{schema}.dataset", "dataset must be a dataset path (not containing '@').", errno.EINVAL,
        )
    if "@" in data.name:
        raise ValidationError(f"{schema}.name", "name must be a snapshot name (not containing '@').", errno.EINVAL)

    try:
        return ZFSResourceSnapshotEntry(**context.call_sync2(context.s.zfs.resource.snapshot.create_impl, data))
    except ZFSPathNotFoundException as e:
        raise ValidationError(f"{schema}.dataset", e.message, errno.ENOENT)
    except ZFSPathAlreadyExistsException as e:
        raise ValidationError(f"{schema}.name", e.message, errno.EEXIST)
    except ZFSPathInvalidException as e:
        # create_snapshots_impl only raises this when `exclude` leaves no dataset to snapshot
        raise ValidationError(f"{schema}.exclude", e.message, errno.EINVAL)
    except ValueError as e:
        raise ValidationError(schema, str(e), errno.EINVAL)


def hold_impl(context: ServiceContext, tls: Any, data: ZFSResourceSnapshotHoldArgsData) -> None:
    reject_protected_path("zfs.resource.snapshot.hold.path", data.path, data.bypass)
    _announce_holds(context, tls, _raw_hold(tls, path=data.path, tag=data.tag, recursive=data.recursive))


def hold(context: ServiceContext, data: ZFSResourceSnapshotHoldArgsData) -> None:
    schema = "zfs.resource.snapshot.hold"
    if "@" not in data.path:
        raise ValidationError(f"{schema}.path", "path must be a snapshot path (containing '@').", errno.EINVAL)

    try:
        context.call_sync2(context.s.zfs.resource.snapshot.hold_impl, data)
    except ZFSPathNotFoundException as e:
        raise ValidationError(f"{schema}.path", e.message, errno.ENOENT)
    except ValueError as e:
        raise ValidationError(schema, str(e), errno.EINVAL)


def holds_impl(tls: Any, path: str) -> tuple[str, ...]:
    rsrc = open_resource(tls, path)
    return rsrc.get_holds()  # type: ignore[no-any-return]


def holds(context: ServiceContext, data: ZFSResourceSnapshotHoldsQuery) -> list[str]:
    schema = "zfs.resource.snapshot.holds"
    if "@" not in data.path:
        raise ValidationError(f"{schema}.path", "path must be a snapshot path (containing '@').", errno.EINVAL)

    try:
        return list(context.call_sync2(context.s.zfs.resource.snapshot.holds_impl, data.path))
    except ZFSPathNotFoundException as e:
        raise ValidationError(f"{schema}.path", e.message, errno.ENOENT)


def release_impl(context: ServiceContext, tls: Any, data: ZFSResourceSnapshotReleaseArgsData) -> None:
    reject_protected_path("zfs.resource.snapshot.release.path", data.path, data.bypass)
    _announce_holds(context, tls, _raw_release(tls, path=data.path, tag=data.tag, recursive=data.recursive))


def release(context: ServiceContext, data: ZFSResourceSnapshotReleaseArgsData) -> None:
    schema = "zfs.resource.snapshot.release"
    if "@" not in data.path:
        raise ValidationError(f"{schema}.path", "path must be a snapshot path (containing '@').", errno.EINVAL)

    try:
        context.call_sync2(context.s.zfs.resource.snapshot.release_impl, data)
    except ZFSPathNotFoundException as e:
        raise ValidationError(f"{schema}.path", e.message, errno.ENOENT)


def rollback_impl(tls: Any, data: ZFSResourceSnapshotRollbackArgsData) -> None:
    reject_protected_path("zfs.resource.snapshot.rollback.path", data.path, data.bypass)
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


def rollback(context: ServiceContext, data: ZFSResourceSnapshotRollbackArgsData) -> None:
    schema = "zfs.resource.snapshot.rollback"
    try:
        context.call_sync2(context.s.zfs.resource.snapshot.rollback_impl, data)
    except ZFSPathNotFoundException as e:
        raise ValidationError(f"{schema}.path", e.message, errno.ENOENT)
    except ZFSPathNotASnapshotException as e:
        raise ValidationError(f"{schema}.path", e.message, errno.EINVAL)
    except ZFSRollbackConflictException as e:
        raise ValidationError(schema, e.message, errno.EINVAL)
    except ValueError as e:
        raise ValidationError(schema, str(e), errno.EINVAL)
