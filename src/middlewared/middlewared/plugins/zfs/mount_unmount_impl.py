from typing import TypedDict

__all__ = ("UnmountArgs",)


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
