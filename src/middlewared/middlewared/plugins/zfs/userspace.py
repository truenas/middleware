from __future__ import annotations

import builtins
from typing import Any

from middlewared.api import api_method
from middlewared.api.current import (
    ZFSResourceUserspaceEntry,
    ZFSResourceUserspaceListArgs,
    ZFSResourceUserspaceListResult,
    ZFSResourceUserspaceQuery,
    ZFSResourceUserspaceSetArgs,
    ZFSResourceUserspaceSetArgsData,
    ZFSResourceUserspaceSetResult,
)
from middlewared.service import Service, private
from middlewared.service.decorators import pass_thread_local_storage

from . import userspace_impl as _impl
from . import userspace_ops as _ops

__all__ = ("ZFSResourceUserspaceService",)


def _audit_set(data: dict[str, Any]) -> str:
    targets = ", ".join(f"{q.get('type')}:{q.get('xid')}" for q in data.get("quotas") or [])
    return f"{data.get('path')} ({targets})"


class ZFSResourceUserspaceService(Service):
    class Config:
        namespace = "zfs.resource.userspace"
        cli_private = True
        role_prefix = "ZFS_RESOURCE"

    @api_method(
        ZFSResourceUserspaceListArgs,
        ZFSResourceUserspaceListResult,
        roles=["ZFS_RESOURCE_READ"],
        check_annotations=True,
    )
    def list(self, data: ZFSResourceUserspaceQuery) -> builtins.list[ZFSResourceUserspaceEntry]:
        """
        List the space and object usage and limits ZFS accounts per user, group or project on filesystems.

        A row is returned for every id ZFS has accounting for, including ids that only use space and have no limit.
        A usage or limit of 0 means none. Ids are not resolved to names.

        Limits on the filesystem itself are the ``quota`` and ``refquota`` properties, read with
        :method:`zfs.resource.list` and changed with :method:`zfs.resource.set`. The limits given to ids that have
        none of their own are the ``defaultuserquota`` family of properties, also read with
        :method:`zfs.resource.list`.

        A validation error is raised when:

        - a snapshot path is supplied (``EINVAL``)
        - a path is a volume (``EINVAL``)
        - a path is locked (``EACCES``). Unlike :method:`zfs.resource.processes`, which reports nothing for a locked
          resource, the accounting exists here but cannot be read.
        - ZFS does not support a requested type on a filesystem (``EINVAL``)

        Examples:

        List the user and group rows of a filesystem:

        .. code:: json

            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "zfs.resource.userspace.list",
                "params": [{"paths": ["tank/home"], "types": ["user", "group"]}]
            }
        """
        return _ops.list_userspace(self.context, data)

    @api_method(
        ZFSResourceUserspaceSetArgs,
        ZFSResourceUserspaceSetResult,
        roles=["ZFS_RESOURCE_WRITE"],
        audit="ZFS resource userspace set",
        audit_extended=_audit_set,
        check_annotations=True,
    )
    def set(self, data: ZFSResourceUserspaceSetArgsData) -> None:
        """
        Set or remove the space and object limits of users, groups or projects on a filesystem.

        A limit left as null is not changed and a limit of 0 or ``"none"`` is removed. Read the result back with
        :method:`zfs.resource.userspace.list`. Limits on the filesystem itself are set with
        :method:`zfs.resource.set`.

        A validation error is raised when:

        - a snapshot path is supplied (``EINVAL``)
        - the path references a protected internal resource (``EACCES``)
        - the filesystem does not exist (``ENOENT``)
        - the path is a volume (``EINVAL``)
        - the filesystem is locked (``EACCES``)
        - an entry sets neither ``quota`` nor ``objquota`` (``EINVAL``)
        - an entry names user or group id 0 (``EINVAL``)
        - the same type and id are given more than once (``EINVAL``)

        .. note:: Every check runs before anything is written, but ZFS applies the limits one at a time, so a
           failure reported by ZFS may leave part of the request applied.

        Examples:

        Limit a user to 10 GiB and 100000 objects:

        .. code:: json

            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "zfs.resource.userspace.set",
                "params": [
                    {"path": "tank/home", "quotas": [{"type": "user", "xid": 1000, "quota": "10G", "objquota": 100000}]}
                ]
            }

        Remove the space limit of a group:

        .. code:: json

            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "zfs.resource.userspace.set",
                "params": [{"path": "tank/home", "quotas": [{"type": "group", "xid": 1001, "quota": 0}]}]
            }
        """
        _ops.set_userspace(self.context, data)

    @private
    @pass_thread_local_storage
    def list_impl(self, tls: Any, data: ZFSResourceUserspaceQuery) -> builtins.list[dict[str, Any]]:
        return _impl.list_impl(tls, data)

    @private
    @pass_thread_local_storage
    def set_impl(self, tls: Any, data: ZFSResourceUserspaceSetArgsData) -> None:
        _impl.set_impl(tls, data)
