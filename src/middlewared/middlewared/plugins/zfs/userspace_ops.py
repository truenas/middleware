from __future__ import annotations

import errno
from typing import TYPE_CHECKING

from middlewared.api.current import ZFSResourceQuery, ZFSResourceUserspaceEntry
from middlewared.service_exception import ValidationError

from .userspace_impl import SCHEMA_LIST, SCHEMA_SET
from .utils import reject_protected_path, reject_snapshot_path

if TYPE_CHECKING:
    from middlewared.api.current import ZFSResourceUserspaceQuery, ZFSResourceUserspaceSetArgsData
    from middlewared.service import ServiceContext

__all__ = ("list_userspace", "set_userspace", "validate_quotas")


def validate_quotas(data: ZFSResourceUserspaceSetArgsData) -> None:
    seen: set[tuple[str, int]] = set()
    for i, q in enumerate(data.quotas):
        attribute = f"{SCHEMA_SET}.quotas.{i}"
        if q.quota is None and q.objquota is None:
            raise ValidationError(attribute, "At least one of 'quota' or 'objquota' must be given.", errno.EINVAL)
        if q.xid == 0:
            raise ValidationError(f"{attribute}.xid", f"Quotas cannot be set on {q.type} id 0.", errno.EINVAL)
        if (q.type, q.xid) in seen:
            raise ValidationError(
                f"{attribute}.xid", f"{q.type.capitalize()} id {q.xid} is given more than once.", errno.EINVAL
            )
        seen.add((q.type, q.xid))


def _vet_paths(context: ServiceContext, attribute: str, paths: list[str], missing_ok: bool) -> list[str]:
    rows = {
        row["name"]: row
        for row in context.call_sync2(
            context.s.zfs.resource.list_impl,
            ZFSResourceQuery(paths=paths, properties=["keystatus"], exclude_internal_paths=False),
        )
    }
    vetted = []
    for path in paths:
        if (row := rows.get(path)) is None:
            if missing_ok:
                continue
            raise ValidationError(attribute, f"{path!r} does not exist.", errno.ENOENT)
        if row["type"] == "VOLUME":
            raise ValidationError(
                attribute, f"{path!r} is a volume; userspace quotas apply to filesystems only.", errno.EINVAL
            )
        if ((row["properties"] or {}).get("keystatus") or {}).get("value") == "unavailable":
            raise ValidationError(attribute, f"{path!r} is locked. Unlock it first.", errno.EACCES)
        vetted.append(path)
    return vetted


def list_userspace(context: ServiceContext, data: ZFSResourceUserspaceQuery) -> list[ZFSResourceUserspaceEntry]:
    for path in data.paths:
        reject_snapshot_path(SCHEMA_LIST, path)
    if not (paths := _vet_paths(context, SCHEMA_LIST, data.paths, True)):
        return []
    rows = context.call_sync2(context.s.zfs.resource.userspace.list_impl, data.model_copy(update={"paths": paths}))
    return [ZFSResourceUserspaceEntry(**row) for row in rows]


def set_userspace(context: ServiceContext, data: ZFSResourceUserspaceSetArgsData) -> None:
    attribute = f"{SCHEMA_SET}.path"
    reject_snapshot_path(attribute, data.path)
    reject_protected_path(attribute, data.path)
    validate_quotas(data)
    _vet_paths(context, attribute, [data.path], False)
    context.call_sync2(context.s.zfs.resource.userspace.set_impl, data)
