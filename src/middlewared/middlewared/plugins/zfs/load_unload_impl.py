from typing import TypedDict

from .utils import open_resource

try:
    import truenas_pylibzfs
except ImportError:
    truenas_pylibzfs = None


__all__ = (
    "unload_key_impl",
    "UnloadKeyArgs",
)


class UnloadKeyArgs(TypedDict):
    filesystem: str
    """Unload the encryption key from ZFS, removing the ability to access the
    resource (filesystem or zvol) and all of its children that inherit the
    'keylocation' property. This requires that the resource is not currently
    open or mounted."""
    recursive: bool
    """Recursively unload encryption keys for any child resources of the
    parent."""


def unload_key_impl(tls, data: UnloadKeyArgs):
    """libzfs doesn't allow (though it's misleading) the ability
    to unload the encryption key of a zfs resource without first
    unmounting it. This is why it's calling "unmount" method."""
    rsrc = open_resource(tls, data.get("filesystem", ""))
    rsrc.unmount(recursive=data.get("recursive", False), unload_encryption_key=True)
