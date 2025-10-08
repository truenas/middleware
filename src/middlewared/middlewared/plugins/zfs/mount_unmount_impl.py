from typing import TypedDict

from .exceptions import ZFSFSNotProvidedError, ZFSPathNotFoundException

try:
    import truenas_pylibzfs
except ImportError:
    truenas_pylibzfs = None


__all__ = (
    "mount_impl",
    "MountArgs",
    "unmount_impl",
    "UnmountArgs",
)


class MountArgs(TypedDict, total=False):
    filesystem: str
    """The zfs filesystem to be mounted."""
    mountpoint: str
    """Optional parameter to manually specify the mountpoint at
    which to mount the datasets. If this is omitted then the
    mountpoint specied in the ZFS mountpoint property will be used.
    Generally the mountpoint should be not be specified and the
    library user should rely on the ZFS mountpoint property."""
    recursive: bool
    """Recursively mount all child filesystems. Default is False."""
    mount_options: list[str] | None
    """List of mount options to use when mounting the ZFS dataset.
    These may be any of MNTOPT constants in the truenas_pylibzfs.constants
    module. Defaults to None.

    NOTE: it's generally preferable to set these as ZFS properties rather
    than overriding via mount options"""
    force: bool
    """Redacted datasets and ones with the `canmount` property set to off
    will fail to mount without explicitly passing the force option.
    Defaults to False."""
    load_encryption_key: bool
    """Load keys for encrypted filesystems as they are being mounted. This is
    equivalent to executing zfs load-key before mounting it. Defaults to False."""


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


def __open_rsrc(tls, data: MountArgs | UnmountArgs):
    fs = data.pop("filesystem", None)
    if not fs:
        raise ZFSFSNotProvidedError()

    try:
        return tls.lzh.open_resource(name=fs)
    except truenas_pylibzfs.ZFSException as e:
        if truenas_pylibzfs.ZFSError(e.code) == truenas_pylibzfs.ZFSError.EZFS_NOENT:
            raise ZFSPathNotFoundException(fs)
        else:
            raise e from None


def __mount_cb(hdl, state):
    mounted = hdl.asdict(properties={truenas_pylibzfs.ZFSProperty.MOUNTED})
    if mounted["properties"]["mounted"]["raw"] == "no":
        hdl.mount(**state["mntopts"])
    if state["recursive"]:
        hdl.iter_filesystems(callback=__mount_cb, state=state)
    return True


def mount_impl(tls, data: MountArgs) -> None:
    rsrc = __open_rsrc(tls, data)
    if rsrc.type != truenas_pylibzfs.ZFSType.ZFS_TYPE_FILESYSTEM:
        return

    state = {"recursive": data.pop("recursive", False), "mntopts": data}
    __mount_cb(rsrc, state)


def unmount_impl(tls, data: UnmountArgs) -> None:
    rsrc = __open_rsrc(tls, data)
    rsrc.unmount(**data)
