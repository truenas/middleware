from collections.abc import Iterable
import errno
import os
from typing import Any, Literal

import truenas_pylibzfs

from middlewared.utils.filesystem import attrs as fs_attrs

from .exceptions import ZFSPathHasClonesException, ZFSPathHasHoldsException
from .utils import open_resource

__all__ = ("destroy_impl",)


def _remove_mountpoint_dir(mountpoint: str) -> None:
    """Remove the destroyed resource's now-unused mountpoint directory.

    The lock flow marks a locked dataset's mountpoint immutable, so clear
    that first or the rmdir fails and the directory lingers. All failures
    are silently ignored, which mimics upstream zfs.
    """
    try:
        fs_attrs.set_zfs_file_attributes_dict(mountpoint, {"immutable": False})
    except Exception:
        pass
    try:
        os.rmdir(mountpoint)
    except Exception:
        pass


def _own_mountpoint(hdl: Any) -> str | None:
    """Return the directory `hdl` owns, or None when it owns none.

    A "legacy" or "none" mountpoint is not a path and owns no directory.
    """
    mountpoint = hdl.get_properties(properties={truenas_pylibzfs.ZFSProperty.MOUNTPOINT}).mountpoint.value
    return mountpoint if mountpoint and mountpoint.startswith("/") else None


def _collect_mountpoints_callback(hdl: Any, state: list[str]) -> Literal[True]:
    _collect_mountpoints(hdl, state)
    return True


def _collect_mountpoints(hdl: Any, state: list[str]) -> None:
    """Collect the mountpoint of `hdl` and of every filesystem below it.

    The descendants are needed because their directories sit inside their
    parent's, and the parent's rmdir only succeeds once they are gone.
    """
    if hdl.type != truenas_pylibzfs.ZFSType.ZFS_TYPE_FILESYSTEM:
        return

    if (mountpoint := _own_mountpoint(hdl)) is not None:
        state.append(mountpoint)

    hdl.iter_filesystems(callback=_collect_mountpoints_callback, state=state)


def _remove_mountpoint_dirs(mountpoints: Iterable[str]) -> None:
    """Remove the destroyed resources' mountpoint directories, deepest first."""
    for mountpoint in sorted(set(mountpoints), reverse=True):
        _remove_mountpoint_dir(mountpoint)


def destroy_nonrecursive_impl(tls: Any, path: str, defer: bool) -> tuple[str | None, int | None]:
    """
    Destroy a single ZFS resource non-recursively.

    Args:
        path: The path of the zfs resource to destroy.
        defer: Rather than returning error if the given snapshot is ineligible for immediate destruction,
            mark it for deferred, automatic destruction once it becomes eligible.
    """
    rsrc = open_resource(tls, path)
    a_snapshot = rsrc.type == truenas_pylibzfs.ZFSType.ZFS_TYPE_SNAPSHOT
    failed, errnum = None, None
    if a_snapshot:
        holds = rsrc.get_holds()
        if holds:
            raise ZFSPathHasHoldsException(path, holds)
        if not defer:
            clones = rsrc.get_clones()
            if clones:
                raise ZFSPathHasClonesException(path, clones)

        try:
            truenas_pylibzfs.lzc.destroy_snapshots(snapshot_names=(path,), defer_destroy=defer)
        except truenas_pylibzfs.ZFSException as e:
            failed = f"Failed to destroy {path!r}: {e}"
            errnum = e.code
        return failed, errnum
    elif rsrc.type == truenas_pylibzfs.ZFSType.ZFS_TYPE_FILESYSTEM:
        try:
            rsrc.unmount()
        except truenas_pylibzfs.ZFSException as e:
            failed = f"Failed to unmount {path!r}: {e}"
            errnum = e.code
        else:
            # `path` has no children: a non-recursive destroy of a filesystem
            # that has any is rejected before it reaches here
            if (mountpoint := _own_mountpoint(rsrc)) is not None:
                _remove_mountpoint_dir(mountpoint)

    # Both ZFS_TYPE_FILESYSTEM and ZFS_TYPE_VOLUME
    try:
        tls.lzh.destroy_resource(name=path)
    except truenas_pylibzfs.ZFSException as e:
        failed = f"Failed to destroy {path!r}: {e}"
        errnum = e.code

    return failed, errnum


def destroy_impl(
    tls: Any,
    path: str,
    recursive: bool,
    all_snapshots: bool,
    bypass: bool,
    defer: bool,
) -> tuple[str | None, int | None]:
    """
    Destroy a ZFS resource with optional recursive and snapshot handling.

    Args:
        path: The path of the zfs resource to destroy.
        recursive: Recursively destroy all descedants as well as
            release any holds and destroy any clones or snapshots.
        all_snapshots: If true, will delete all snapshots ONLY for the
            given zfs resource. Will not delete the resource itself.
        bypass: If true, will bypass the safety checks that prevent
            deleting zfs resources that are "protected".
            NOTE: This is only ever set by internal callers and is
            not exposed to the public API.
        defer: Rather than returning error if the given snapshot is ineligible for immediate destruction,
            mark it for deferred, automatic destruction once it becomes eligible.
    """
    if not recursive and not all_snapshots:
        return destroy_nonrecursive_impl(tls, path, defer)

    target = path.split("@")[0]
    pool_name = target.split("/")[0]
    script_arguments_dict = {
        "recursive": recursive,
        "defer": defer,
        "target": target,
    }
    readonly = False
    mntpnts: list[str] = list()
    if "@" in path:
        script = truenas_pylibzfs.lzc.ChannelProgramEnum.DESTROY_SNAPSHOTS
        script_arguments_dict.update({"pattern": path.split("@")[-1]})
    elif all_snapshots:
        script = truenas_pylibzfs.lzc.ChannelProgramEnum.DESTROY_SNAPSHOTS
    else:
        rsrc = open_resource(tls, path)
        if rsrc.type == truenas_pylibzfs.ZFSType.ZFS_TYPE_FILESYSTEM:
            _collect_mountpoints(rsrc, mntpnts)
            rsrc.unmount(recursive=recursive)
        script = truenas_pylibzfs.lzc.ChannelProgramEnum.DESTROY_RESOURCES

    try_again = False
    res = truenas_pylibzfs.lzc.run_channel_program(
        pool_name=pool_name,
        script=script,
        script_arguments_dict=script_arguments_dict,
        readonly=readonly,
    )
    if res["return"]["holds"]:
        try_again = True
        truenas_pylibzfs.lzc.release_holds(holds=set(res["return"]["holds"].items()))

    if res["return"]["clones"]:
        try_again = True
        for clone, err in res["return"]["clones"].items():
            if err == errno.EBUSY:
                rsrc = open_resource(tls, clone)
                if rsrc.type == truenas_pylibzfs.ZFSType.ZFS_TYPE_FILESYSTEM:
                    _collect_mountpoints(rsrc, mntpnts)
                    rsrc.unmount(recursive=recursive)
            # TODO: else raise ZFSException(err) if not EBUSY??

    if try_again:
        res = truenas_pylibzfs.lzc.run_channel_program(
            pool_name=pool_name,
            script=script,
            script_arguments_dict=script_arguments_dict,
            readonly=readonly,
        )

    failed, errnum = None, None
    if res["return"]["failed"]:
        failed = f"Failed to destroy {path!r}"
        if res["return"]["clones"]:
            failed += f" There are clones ({','.join(tuple(res['return']['clones'].keys()))})"
            errnum = errno.EBUSY
        elif res["return"]["holds"]:
            failed += f" There are holds ({','.join(tuple(res['return']['holds'].keys()))})"
            errnum = errno.EBUSY
        else:
            errnum = res["return"]["failed"].get(path, errno.EFAULT)
            if isinstance(errnum, int) and errnum in truenas_pylibzfs.ZFSError:
                failed += f" ({truenas_pylibzfs.ZFSError(errnum)})"
    else:
        _remove_mountpoint_dirs(mntpnts)

    return failed, errnum
