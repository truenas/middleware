from typing import TypedDict

from .exceptions import (
    ZFSPathNotFoundException,
    ZFSRenamePathAlreadyExistsException,
    ZFSRenameNotASnapshotException,
    ZFSRenamePathNotProvidedException,
)
from .utils import open_resource

__all__ = (
    "rename_impl",
    "RenameArgs",
)


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
    """Recursively rename the snapshots of all descendent resources. Snapshots
    are the only resource that can be renamed recursively."""
    no_unmount: bool
    """Do not remount file systems during rename. If a filesystem's mountpoint
    property is set to legacy or none, the file system is not unmounted even
    if this option is False (default)."""
    force_unmount: bool
    """Force unmount any file systems that need to be unmounted in the process."""


def rename_impl(tls, data: RenameArgs):
    curr = data.pop("current_name", "")
    rsrc = open_resource(tls, curr)
    new = data.pop("new_name", None)
    if not new:
        raise ZFSRenamePathNotProvidedException()

    try:
        open_resource(tls, new)
    except ZFSPathNotFoundException:
        pass
    else:
        raise ZFSRenamePathAlreadyExistsException(new)

    recurse = data.get("recursive", False)
    if (
        recurse is True
        and "@" not in new
        and "@" not in curr
    ):
        raise ZFSRenameNotASnapshotException()

    rsrc.rename(
        new_name=new,
        recursive=recurse,
        no_unmount=data.get("no_unmount", False),
        force_unmount=data.get("force_unmount", True),
    )
