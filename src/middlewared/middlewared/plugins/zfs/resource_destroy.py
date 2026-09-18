from __future__ import annotations

import errno
import os
from typing import TYPE_CHECKING, Any

from middlewared.api.current import (
    ZFSResourceDestroyArgsData,
    ZFSResourceQuery,
    ZFSResourceSnapshotCountQuery,
)
from middlewared.service_exception import ValidationError

from .destroy_impl import destroy_impl as _raw_destroy
from .exceptions import (
    ZFSPathHasClonesException,
    ZFSPathHasHoldsException,
    ZFSPathNotFoundException,
)
from .utils import reject_protected_path

if TYPE_CHECKING:
    from middlewared.service import ServiceContext

SCHEMA = "zfs.resource.destroy"


def destroy_impl(
    context: ServiceContext,
    tls: Any,
    path: str,
    recursive: bool = False,
    all_snapshots: bool = False,
    bypass: bool = False,
    defer: bool = False,
) -> tuple[str | None, int | None]:
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
            context.s.zfs.resource.query_impl,
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

    return _raw_destroy(tls, path, recursive, all_snapshots, bypass, defer)


def destroy(context: ServiceContext, data: ZFSResourceDestroyArgsData) -> None:
    try:
        failed, errnum = context.call_sync2(context.s.zfs.resource.destroy_impl, data.path, data.recursive)
    except ZFSPathHasClonesException as e:
        raise ValidationError(
            f"{SCHEMA}.defer",
            f"Snapshot {e.path!r} has dependent clones: {', '.join(e.clones)}",
            errno.ENOTEMPTY,
        )
    except ZFSPathHasHoldsException as e:
        raise ValidationError(SCHEMA, e.message, errno.ENOTEMPTY)
    except ZFSPathNotFoundException as e:
        raise ValidationError(SCHEMA, e.message, errno.ENOENT)
    else:
        if failed:
            # A recursive destroy runs as a channel program, which executes atomically behind
            # the scenes and so reports its failure as a return value rather than an exception.
            assert errnum is not None
            raise ValidationError(SCHEMA, failed, errnum)
