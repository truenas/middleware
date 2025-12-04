from typing import TypedDict

from .exceptions import (
    ZFSPathAlreadyExistsException,
    ZFSPathInvalidException,
    ZFSPathNotASnapshotException,
    ZFSPathNotFoundException,
    ZFSPathNotProvidedException,
)
from .utils import open_resource

try:
    from truenas_pylibzfs import ZFSProperty, ZFSType
except ImportError:
    ZFSProperty = ZFSType = None


__all__ = (
    "clone_impl",
    "CloneArgs",
    "promote_impl",
    "PromoteArgs",
    "rename_impl",
    "RenameArgs",
)


class CloneArgs(TypedDict, total=False):
    current_name: str
    """The name of the zfs snapshot that should be cloned."""
    new_name: str
    """The new name to be given to the clone."""
    properties: dict[str, str | int]
    """Optional set of properties to set on the cloned resource."""


class PromoteArgs(TypedDict):
    current_name: str
    """The name of the zfs resource to be promoted."""


class RenameArgs(TypedDict, total=False):
    current_name: str
    """The existing name of the zfs resource to be renamed."""
    new_name: str
    """New name for ZFS object. The new name may not change the
    pool name component of the original name and contain
    alphanumeric characters and the following special characters:

    * Underscore (_)
    * Hyphen (-)
    * Colon (:)
    * Period (.)

    The name length may not exceed 255 bytes, but it is generally advisable
    to limit the length to something significantly less than the absolute
    name length limit."""
    recursive: bool
    """Recursively rename the snapshots of all descendant resources. Snapshots
    are the only resource that can be renamed recursively."""
    no_unmount: bool
    """Do not remount file systems during rename. If a filesystem's mountpoint
    property is set to legacy or none, the file system is not unmounted even
    if this option is False (default)."""
    force_unmount: bool
    """Force unmount any file systems that need to be unmounted in the process."""


def clone_impl(tls, data: CloneArgs):
    curr = data.pop("current_name", "")
    rsrc = open_resource(tls, curr)
    if rsrc.type != ZFSType.ZFS_TYPE_SNAPSHOT:
        raise ZFSPathNotASnapshotException()

    new = data.pop("new_name", None)
    if not new:
        raise ZFSPathNotProvidedException()

    try:
        open_resource(tls, new)
    except ZFSPathNotFoundException:
        pass
    else:
        raise ZFSPathAlreadyExistsException(new)

    if props := data.get("props", None):
        rsrc.clone(name=new, properties=props)
    else:
        rsrc.clone(name=new)


def promote_impl(tls, data: PromoteArgs):
    rsrc = open_resource(tls, data["current_name"])
    origin = rsrc.get_properties(properties={ZFSProperty.ORIGIN}).origin
    if origin.value is None:
        raise ZFSPathInvalidException()
    rsrc.promote()


def rename_impl(tls, data: RenameArgs):
    curr = data.pop("current_name", "")
    rsrc = open_resource(tls, curr)
    new = data.pop("new_name", None)
    if not new:
        raise ZFSPathNotProvidedException()

    try:
        open_resource(tls, new)
    except ZFSPathNotFoundException:
        pass
    else:
        raise ZFSPathAlreadyExistsException(new)

    recurse = data.get("recursive", False)
    if recurse is True and ("@" not in new or "@" not in curr):
        raise ZFSPathNotASnapshotException()

    rsrc.rename(
        new_name=new,
        recursive=recurse,
        no_unmount=data.get("no_unmount", False),
        force_unmount=data.get("force_unmount", True),
    )
