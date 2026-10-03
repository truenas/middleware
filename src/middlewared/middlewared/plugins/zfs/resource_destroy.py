from __future__ import annotations

import errno
import os
from typing import TYPE_CHECKING, Any

from middlewared.api.current import (
    ZFSResourceDestroyArgsData,
    ZFSResourceQuery,
    ZFSResourceSnapshotCountQuery,
)
from middlewared.service_exception import CallError, ValidationError
from middlewared.utils.filesystem import attrs as fs_attrs

from .destroy_impl import destroy_impl as _raw_destroy
from .exceptions import (
    ZFSDestroyFailedException,
    ZFSPathHasClonesException,
    ZFSPathHasHoldsException,
    ZFSPathNotFoundException,
)
from .resource_attachments import for_stop
from .utils import get_encryption_info, reject_protected_path, resource_mountpoint

if TYPE_CHECKING:
    from middlewared.service import ServiceContext

SCHEMA = "zfs.resource.destroy"


def _validate(context: ServiceContext, path: str, recursive: bool, bypass: bool) -> None:
    if os.path.isabs(path):
        raise ValidationError(
            SCHEMA,
            "Absolute path is invalid. Must be in form of <pool>/<resource>.",
            errno.EINVAL,
        )
    elif path.endswith("/"):
        raise ValidationError(SCHEMA, "Path must not end with a forward-slash.", errno.EINVAL)

    reject_protected_path(SCHEMA, path, bypass)

    if "@" in path:
        raise ValidationError(SCHEMA, "Use `zfs.resource.snapshot.destroy` to destroy snapshots.")

    tmp = path.split("/")
    if len(tmp) == 1 or tmp[-1] == "":
        raise ValidationError(SCHEMA, "Destroying the root filesystem is not allowed.", errno.EINVAL)

    if not recursive:
        rv = context.call_sync2(
            context.s.zfs.resource.list_impl,
            ZFSResourceQuery(paths=[path], properties=None, get_children=True),
        )
        extra = "Set recursive=True to remove them."
        if not rv:
            raise ValidationError(SCHEMA, f"{path!r} does not exist.", errno.ENOENT)
        elif len(rv) > 1:
            raise ValidationError(SCHEMA, f"{path!r} has children. {extra}", errno.ENOTEMPTY)
        else:
            snap_counts = context.call_sync2(
                context.s.zfs.resource.snapshot.count,
                ZFSResourceSnapshotCountQuery(paths=[path]),
            )
            if snap_counts.get(path, 0) > 0:
                raise ValidationError(SCHEMA, f"{path!r} has snapshots. {extra}", errno.ENOTEMPTY)


def destroy_impl(
    context: ServiceContext,
    tls: Any,
    path: str,
    recursive: bool = False,
    all_snapshots: bool = False,
    bypass: bool = False,
    defer: bool = False,
) -> None:
    _validate(context, path, recursive, bypass)
    _raw_destroy(tls, path, recursive, all_snapshots, bypass, defer)


async def _destroy_with_truesearch_paused(
    context: ServiceContext, mountpoint: str | None, path: str, recursive: bool
) -> None:
    async with context.s.truesearch.remove_mountpoint(mountpoint):
        await context.call2(context.s.zfs.resource.destroy_impl, path, recursive)


def destroy(context: ServiceContext, data: ZFSResourceDestroyArgsData) -> None:
    _validate(context, data.path, data.recursive, False)
    rows = context.call_sync2(
        context.s.zfs.resource.list_impl,
        ZFSResourceQuery(
            paths=[data.path], properties=["mountpoint", "encryption", "keystatus", "keyformat", "keylocation"]
        ),
    )
    mountpoint = resource_mountpoint(rows[0]) if rows else None
    if mountpoint:
        for delegate in for_stop():
            if attachments := context.run_coroutine(delegate.query(mountpoint, True)):
                context.run_coroutine(delegate.delete(attachments))
        if get_encryption_info(rows[0]["properties"]).locked and os.path.exists(mountpoint):
            # a locked dataset's mountpoint is immutable, which would keep the destroy from removing it
            fs_attrs.set_zfs_file_attributes_dict(mountpoint, {"immutable": False})

    try:
        context.run_coroutine(_destroy_with_truesearch_paused(context, mountpoint, data.path, data.recursive))
    except ZFSPathHasClonesException as e:
        raise ValidationError(
            SCHEMA,
            f"Snapshot {e.path!r} has dependent clones: {', '.join(e.clones)}",
            errno.ENOTEMPTY,
        )
    except ZFSPathHasHoldsException as e:
        raise ValidationError(SCHEMA, e.message, errno.ENOTEMPTY)
    except ZFSPathNotFoundException as e:
        raise ValidationError(SCHEMA, e.message, errno.ENOENT)
    except ZFSDestroyFailedException as e:
        raise CallError(e.message, e.errnum)
