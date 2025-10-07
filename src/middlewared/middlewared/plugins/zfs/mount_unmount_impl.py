from typing import TypedDict

try:
    import truenas_pylibzfs
except ImportError:
    truenas_pylibzfs = None

__all__ = ("unmount_impl",)


class UnmountArgs(TypedDict, total=False):
    filesystem: str
    """The zfs filesystem to be unmounted."""
    mountpoint: str
    """Optional parameter to manually specify the mountpoint at
    which the dataset is mounted. This may be required for datasets with
    legacy mountpoints and is benefical if the mountpoint is known apriori."""
    recursive: bool
    """Unmount any children inheriting the mountpoint property."""
    force: bool
    """Forcefully unmount the file system, even if it is currently in use.
    Defaults to False."""
    lazy: bool
    """Perform a lazy unmount: make the mount unavailable for new accesses,
    immediately disconnect the filesystem and all filesystems mounted below
    it from each other and from the mount table, and actually perform the
    unmount when the mount ceases to be busy. Defaults to False."""
    unload_encryption_key: bool
    """Unload keys for any encryption roots unmounted by this operation.
    Defaults to False."""


def unmount_impl(lzh, data: UnmountArgs) -> None:
    rsrc = lzh.open_resource(name=data["filesystem"])
    rsrc.unmount(
        **{
            "force": data.get("force", False),
            "lazy": data.get("lazy", False),
            "recursive": data.get("recursive", False),
            "mountpoint": data.get("mountpoint", False),
            "unload_encryption_key": data.get("unload_encryption_key", False)
        }
    )
