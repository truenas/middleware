from __future__ import annotations

import errno
import os
import typing

from middlewared.service_exception import CallError
from middlewared.utils.privilege_constants import LocalBuiltinUsers

if typing.TYPE_CHECKING:
    from middlewared.service import ServiceContext
    from middlewared.service_exception import ValidationErrors

__all__ = ("SHARE_PRESETS", "apply_share_acl", "share_acl", "share_type_choices")

SCHEMA = "zfs.resource.create"

_NFS = {
    "casesensitivity": "sensitive",
    "atime": "off",
    "acltype": "nfsv4",
    "aclmode": "passthrough",
    "aclinherit": "passthrough",
}
SHARE_PRESETS: dict[str, dict[str, str]] = {
    "smb": {"casesensitivity": "insensitive", "acltype": "nfsv4", "aclmode": "restricted", "aclinherit": "passthrough"},
    "multiprotocol": _NFS,
    "nfs": _NFS,
    "apps": _NFS,
}
_APPS_PERMS = (
    "READ_DATA",
    "WRITE_DATA",
    "DELETE",
    "DELETE_CHILD",
    "READ_ACL",
    "APPEND_DATA",
    "READ_NAMED_ATTRS",
    "WRITE_NAMED_ATTRS",
    "READ_ATTRIBUTES",
    "WRITE_ATTRIBUTES",
)


def share_type_choices() -> dict[str, dict[str, str]]:
    return {st: dict(props) for st, props in SHARE_PRESETS.items()}


def share_acl(
    context: ServiceContext, share_type: str, path: str, parent: dict[str, typing.Any], verrors: ValidationErrors
) -> list[dict[str, typing.Any]] | None:
    parent_mp = parent["properties"]["mountpoint"]["raw"]
    if (
        parent["properties"]["mounted"]["raw"] == "yes"
        and parent_mp not in ("none", "legacy")
        and context.middleware.call_sync("filesystem.path_get_acltype", parent_mp) == "NFS4"
        and context.middleware.call_sync("filesystem.stat", parent_mp).acl
    ):
        acl: list[dict[str, typing.Any]] = context.middleware.call_sync(
            "filesystem.get_inherited_acl", {"path": parent_mp}
        )
        add_apps = share_type == "apps" and not any(
            entry["id"] == LocalBuiltinUsers.APPS.value
            and entry["tag"] == "USER"
            and entry["type"] == "ALLOW"
            and entry["flags"]["FILE_INHERIT"]
            and entry["flags"]["DIRECTORY_INHERIT"]
            and all(entry["perms"][role] for role in _APPS_PERMS)
            for entry in acl
        )
    elif share_type in ("smb", "apps"):
        acl = context.middleware.call_sync(
            "filesystem.acltemplate.by_path",
            {"query-filters": [("name", "=", "NFS4_RESTRICTED")], "format-options": {"ensure_builtins": True}},
        )[0]["acl"]
        add_apps = share_type == "apps"
    else:
        return None

    if add_apps:
        acl.append(
            {
                "tag": "USER",
                "id": LocalBuiltinUsers.APPS.value,
                "perms": {"BASIC": "MODIFY"},
                "flags": {"BASIC": "INHERIT"},
                "type": "ALLOW",
            }
        )

    try:
        context.middleware.call_sync("filesystem.check_acl_execute", os.path.join("/mnt", path), acl, -1, -1)
    except CallError as e:
        if e.errno != errno.EPERM:
            raise
        verrors.add(f"{SCHEMA}.share_type", e.errmsg)
    return acl


def apply_share_acl(context: ServiceContext, path: str, acl: list[dict[str, typing.Any]]) -> None:
    # We're potentially auto-inheriting an ACL containing nested
    # security groups and so we need to skip the ACL validation
    context.middleware.call_sync(
        "filesystem.setacl",
        {"path": os.path.join("/mnt", path), "dacl": acl, "options": {"validate_effective_acl": False}},
    ).wait_sync(raise_error=True)
