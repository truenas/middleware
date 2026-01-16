from typing import Any

from .utils import open_resource

__all__ = (
    "unload_key_impl",
)


def unload_key_impl(tls: Any, filesystem: str, recursive: bool, force_unmount: bool) -> None:
    """
    Unload the encryption key from ZFS.

    libzfs doesn't allow (though it's misleading) the ability
    to unload the encryption key of a zfs resource without first
    unmounting it. This is why it's calling "unmount" method.

    Args:
        filesystem: Unload the encryption key from ZFS, removing the ability to access the
            resource (filesystem or zvol) and all of its children that inherit the
            'keylocation' property. This requires that the resource is not currently
            open or mounted.
        recursive: Recursively unload encryption keys for any child resources of the
            parent.
        force_unmount: Forcefully unmount the resource before unloading the encryption key.
    """
    rsrc = open_resource(tls, filesystem)
    rsrc.unmount(
        force=force_unmount,
        recursive=recursive,
        unload_encryption_key=True
    )
