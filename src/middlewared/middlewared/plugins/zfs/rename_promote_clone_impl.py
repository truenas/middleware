from truenas_pylibzfs import ZFSProperty, ZFSType

from .exceptions import (
    ZFSPathAlreadyExistsException,
    ZFSPathInvalidException,
    ZFSPathNotASnapshotException,
    ZFSPathNotFoundException,
    ZFSPathNotProvidedException,
)
from .utils import open_resource

__all__ = (
    "clone_impl",
    "promote_impl",
    "rename_impl",
)


def clone_impl(
    tls,
    current_name: str,
    new_name: str,
    properties: dict[str, str | int] | None = None,
):
    """
    Clone a ZFS snapshot.

    Args:
        current_name: The name of the zfs snapshot that should be cloned.
        new_name: The new name to be given to the clone.
        properties: Optional set of properties to set on the cloned resource.
    """
    rsrc = open_resource(tls, current_name)
    if rsrc.type != ZFSType.ZFS_TYPE_SNAPSHOT:
        raise ZFSPathNotASnapshotException(current_name)

    if not new_name:
        raise ZFSPathNotProvidedException()

    try:
        open_resource(tls, new_name)
    except ZFSPathNotFoundException:
        pass
    else:
        raise ZFSPathAlreadyExistsException(new_name)

    if properties:
        rsrc.clone(name=new_name, properties=properties)
    else:
        rsrc.clone(name=new_name)


def promote_impl(tls, current_name: str):
    """
    Promote a ZFS clone to be independent of its origin snapshot.

    Args:
        current_name: The name of the zfs resource to be promoted.
    """
    rsrc = open_resource(tls, current_name)
    origin = rsrc.get_properties(properties={ZFSProperty.ORIGIN}).origin
    if origin.value is None:
        raise ZFSPathInvalidException()
    rsrc.promote()


def rename_impl(
    tls,
    current_name: str,
    new_name: str,
    recursive: bool,
    no_unmount: bool,
    force_unmount: bool,
):
    """
    Rename a ZFS resource.

    Args:
        current_name: The existing name of the zfs resource to be renamed.
        new_name: New name for ZFS object. The new name may not change the
            pool name component of the original name and contain
            alphanumeric characters and the following special characters:

            * Underscore (_)
            * Hyphen (-)
            * Colon (:)
            * Period (.)

            The name length may not exceed 255 bytes, but it is generally advisable
            to limit the length to something significantly less than the absolute
            name length limit.
        recursive: Recursively rename the snapshots of all descendant resources. Snapshots
            are the only resource that can be renamed recursively.
        no_unmount: Do not remount file systems during rename. If a filesystem's mountpoint
            property is set to legacy or none, the file system is not unmounted even
            if this option is False.
        force_unmount: Force unmount any file systems that need to be unmounted in the process.
    """
    rsrc = open_resource(tls, current_name)
    if not new_name:
        raise ZFSPathNotProvidedException()

    try:
        open_resource(tls, new_name)
    except ZFSPathNotFoundException:
        pass
    else:
        raise ZFSPathAlreadyExistsException(new_name)

    if recursive is True and ("@" not in new_name or "@" not in current_name):
        raise ZFSPathNotASnapshotException(current_name if "@" not in current_name else new_name)

    rsrc.rename(
        new_name=new_name,
        recursive=recursive,
        no_unmount=no_unmount,
        force_unmount=force_unmount,
    )
