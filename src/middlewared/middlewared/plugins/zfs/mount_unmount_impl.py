from typing import Any, Literal

import truenas_pylibzfs

from .utils import open_resource

__all__ = (
    "mount_impl",
    "unmount_impl",
)


def __mount_cb(hdl: Any, state: dict[str, Any]) -> Literal[True]:
    if hdl.type == truenas_pylibzfs.ZFSType.ZFS_TYPE_FILESYSTEM:
        mounted = hdl.asdict(properties={truenas_pylibzfs.ZFSProperty.MOUNTED})
        if mounted["properties"]["mounted"]["raw"] == "no":
            hdl.mount(**state["mntopts"])
    if state["recursive"]:
        hdl.iter_filesystems(callback=__mount_cb, state=state)
    return True


def mount_impl(
    tls: Any,
    filesystem: str,
    mountpoint: str | None,
    recursive: bool,
    mount_options: list[str] | None,
    force: bool,
    load_encryption_key: bool,
) -> None:
    """
    Mount a ZFS filesystem.

    Args:
        filesystem: The zfs filesystem to be mounted.
        mountpoint: Optional parameter to manually specify the mountpoint at
            which to mount the datasets. If this is omitted then the
            mountpoint specied in the ZFS mountpoint property will be used.
            Generally the mountpoint should be not be specified and the
            library user should rely on the ZFS mountpoint property.
        recursive: Recursively mount all child filesystems.
        mount_options: List of mount options to use when mounting the ZFS dataset.
            These may be any of MNTOPT constants in the truenas_pylibzfs.constants
            module.

            NOTE: it's generally preferable to set these as ZFS properties rather
            than overriding via mount options
        force: Redacted datasets and ones with the `canmount` property set to off
            will fail to mount without explicitly passing the force option.
        load_encryption_key: Load keys for encrypted filesystems as they are being mounted. This is
            equivalent to executing zfs load-key before mounting it.
    """
    rsrc = open_resource(tls, filesystem)
    mntopts: dict[str, Any] = {}
    if mountpoint is not None:
        mntopts["mountpoint"] = mountpoint
    if mount_options is not None:
        mntopts["mount_options"] = mount_options
    if force:
        mntopts["force"] = force
    if load_encryption_key:
        mntopts["load_encryption_key"] = load_encryption_key
    state = {"recursive": recursive, "mntopts": mntopts}
    __mount_cb(rsrc, state)


def unmount_impl(
    tls: Any,
    filesystem: str,
    mountpoint: str | None,
    recursive: bool,
    force: bool,
    lazy: bool,
    unload_encryption_key: bool,
) -> None:
    """
    Unmount a ZFS filesystem.

    Args:
        filesystem: The zfs filesystem to be unmounted.
        mountpoint: Optional parameter to manually specify the mountpoint at
            which the dataset is mounted. This may be required for datasets with
            legacy mountpoints and is benefical if the mountpoint is known apriori.
        recursive: Unmount any children inheriting the mountpoint property.
        force: Forcefully unmount the file system, even if it is currently in use.
        lazy: Perform a lazy unmount: make the mount unavailable for new accesses,
            immediately disconnect the filesystem and all filesystems mounted below
            it from each other and from the mount table, and actually perform the
            unmount when the mount ceases to be busy.
        unload_encryption_key: Unload keys for any encryption roots unmounted by this operation.
    """
    rsrc = open_resource(tls, filesystem)
    kwargs: dict[str, Any] = {}
    if mountpoint is not None:
        kwargs["mountpoint"] = mountpoint
    if recursive:
        kwargs["recursive"] = recursive
    if force:
        kwargs["force"] = force
    if lazy:
        kwargs["lazy"] = lazy
    if unload_encryption_key:
        kwargs["unload_encryption_key"] = unload_encryption_key
    rsrc.unmount(**kwargs)
