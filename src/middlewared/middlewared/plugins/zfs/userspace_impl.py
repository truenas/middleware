from __future__ import annotations

import errno
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

import truenas_pylibzfs
from truenas_pylibzfs import ZFSUserQuota

from middlewared.service_exception import CallError, ValidationError

from .create_impl import libzfs_error
from .utils import reject_protected_path

if TYPE_CHECKING:
    from middlewared.api.current import ZFSResourceUserspaceQuery, ZFSResourceUserspaceSetArgsData

__all__ = ("SCHEMA_LIST", "SCHEMA_SET", "list_impl", "set_impl")

SCHEMA_LIST = "zfs.resource.userspace.list"
SCHEMA_SET = "zfs.resource.userspace.set"
NOENT_MESSAGE = "was removed while its quotas were being set"

PASSES = MappingProxyType(
    {
        "user": (
            (ZFSUserQuota.USER_USED, "used"),
            (ZFSUserQuota.USER_QUOTA, "quota"),
            (ZFSUserQuota.USEROBJ_USED, "objused"),
            (ZFSUserQuota.USEROBJ_QUOTA, "objquota"),
        ),
        "group": (
            (ZFSUserQuota.GROUP_USED, "used"),
            (ZFSUserQuota.GROUP_QUOTA, "quota"),
            (ZFSUserQuota.GROUPOBJ_USED, "objused"),
            (ZFSUserQuota.GROUPOBJ_QUOTA, "objquota"),
        ),
        "project": (
            (ZFSUserQuota.PROJECT_USED, "used"),
            (ZFSUserQuota.PROJECT_QUOTA, "quota"),
            (ZFSUserQuota.PROJECTOBJ_USED, "objused"),
            (ZFSUserQuota.PROJECTOBJ_QUOTA, "objquota"),
        ),
    }
)

LIMITS = MappingProxyType(
    {
        "user": (ZFSUserQuota.USER_QUOTA, ZFSUserQuota.USEROBJ_QUOTA),
        "group": (ZFSUserQuota.GROUP_QUOTA, ZFSUserQuota.GROUPOBJ_QUOTA),
        "project": (ZFSUserQuota.PROJECT_QUOTA, ZFSUserQuota.PROJECTOBJ_QUOTA),
    }
)


def _collect(quota: Any, state: tuple[dict[tuple[str, int], dict[str, Any]], str, str, str]) -> bool:
    rows, path, type_, field = state
    row = rows.setdefault(
        (type_, quota.xid),
        {"dataset": path, "type": type_, "xid": quota.xid, "used": 0, "quota": 0, "objused": 0, "objquota": 0},
    )
    row[field] = quota.value
    return True


def list_impl(tls: Any, data: ZFSResourceUserspaceQuery) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for path in data.paths:
        rows: dict[tuple[str, int], dict[str, Any]] = {}
        try:
            rsrc = tls.lzh.open_resource(name=path)
            for type_ in data.types:
                for quota_type, field in PASSES[type_]:
                    rsrc.iter_userspace(callback=_collect, state=(rows, path, type_, field), quota_type=quota_type)
        except truenas_pylibzfs.ZFSException as e:
            if e.code == truenas_pylibzfs.ZFSError.EZFS_NOENT:
                continue
            message = f"Failed to read the userspace quotas of {path!r}: {e}"
            raise libzfs_error(path, e, f"{SCHEMA_LIST}.types", e.err_str, message, NOENT_MESSAGE) from e
        except (TypeError, ValueError) as e:
            raise CallError(
                f"ZFS rejected a userspace query for {path!r} that middleware accepted: {e}", errno.EINVAL
            ) from e
        result.extend(rows.values())
    return result


def set_impl(tls: Any, data: ZFSResourceUserspaceSetArgsData) -> None:
    path = data.path
    reject_protected_path(f"{SCHEMA_SET}.path", path)
    quotas: list[dict[str, Any]] = []
    for q in data.quotas:
        for quota_type, value in zip(LIMITS[q.type], (q.quota, q.objquota)):
            if value is not None:
                quotas.append({"xid": q.xid, "quota_type": quota_type, "value": value})
    try:
        rsrc = tls.lzh.open_resource(name=path)
        # Writing a userspace quota to a locked filesystem crashes the kernel, so the key is checked again
        # immediately before the write in case the filesystem was locked after validation.
        if (crypto := rsrc.crypto()) is not None and not crypto.info().key_is_loaded:
            raise ValidationError(f"{SCHEMA_SET}.path", f"{path!r} is locked. Unlock it first.", errno.EACCES)
        rsrc.set_userquotas(quotas=quotas)
    except truenas_pylibzfs.ZFSException as e:
        message = f"Failed to set the userspace quotas of {path!r}: {e}"
        raise libzfs_error(path, e, f"{SCHEMA_SET}.quotas", e.err_str, message, NOENT_MESSAGE) from e
    except (TypeError, ValueError) as e:
        raise CallError(
            f"ZFS rejected a userspace quota for {path!r} that middleware accepted: {e}", errno.EINVAL
        ) from e
