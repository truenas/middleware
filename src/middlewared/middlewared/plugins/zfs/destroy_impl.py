import errno
import os
import typing

from .exceptions import ZFSPathHasClonesException, ZFSPathHasHoldsException
from .utils import open_resource

try:
    import truenas_pylibzfs
except ImportError:
    truenas_pylibzfs = None

__all__ = ("destroy_impl", "DestroyArgs")


class DestroyArgs(typing.TypedDict):
    path: str
    """The path of the zfs resource to destroy."""
    recursive: bool
    """Recursively destroy all descedants as well as
    release any holds and destroy any clones or snapshots."""
    all_snapshots: bool
    """If true, will delete all snapshots ONLY for the
    given zfs resource. Will not delete the resource itself."""
    bypass: bool
    """If true, will bypass the safety checks that prevent
    deleting zfs resources that are "protected".
    NOTE: This is only ever set by internal callers and is
    not exposed to the public API."""
    defer: bool
    """Rather than returning error if the given snapshot is ineligible for immediate destruction, mark it for deferred,
    automatic destruction once it becomes eligible."""


def destroy_nonrecursive_impl(tls, data: DestroyArgs):
    path = data["path"]
    rsrc = open_resource(tls, data["path"])
    a_snapshot = rsrc.type == truenas_pylibzfs.ZFSType.ZFS_TYPE_SNAPSHOT
    failed, errnum = None, None
    if a_snapshot:
        holds = rsrc.get_holds()
        if holds:
            raise ZFSPathHasHoldsException(path, holds)
        if not data["defer"]:
            clones = rsrc.get_clones()
            if clones:
                raise ZFSPathHasClonesException(path, clones)

        try:
            truenas_pylibzfs.lzc.destroy_snapshots(snapshot_names=(path,), defer_destroy=data["defer"])
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
            mntpnt = rsrc.get_properties(properties={truenas_pylibzfs.ZFSProperty.MOUNTPOINT})
            if mntpnt.mountpoint.value != "legacy":
                try:
                    os.rmdir(mntpnt.mountpoint.value)
                except Exception:
                    # silently ignore rmdir ops
                    # which mimics upstream zfs
                    pass

    # Both ZFS_TYPE_FILESYSTEM and ZFS_TYPE_VOLUME
    try:
        tls.lzh.destroy_resource(name=path)
    except truenas_pylibzfs.ZFSException as e:
        failed = f"Failed to destroy {path!r}: {e}"
        errnum = e.code

    return failed, errnum


def destroy_impl(tls, data: DestroyArgs):
    recursive = data.get("recursive", False)
    all_snaps = data.get("all_snapshots", False)
    defer = data.get("defer", False)
    if not recursive and not all_snaps:
        return destroy_nonrecursive_impl(tls, data)

    target = data["path"].split("@")[0]
    rcpa = {
        "pool_name": target.split("/")[0],
        "script": None,
        "script_arguments_dict": {
            "recursive": recursive,
            "defer": defer,
            "target": target,
        },
        "readonly": False,
    }
    mntpnts = list()
    if "@" in data["path"]:
        rcpa["script"] = truenas_pylibzfs.lzc.ChannelProgramEnum.DESTROY_SNAPSHOTS
        rcpa["script_arguments_dict"].update({"pattern": data["path"].split("@")[-1]})
    elif all_snaps:
        rcpa["script"] = truenas_pylibzfs.lzc.ChannelProgramEnum.DESTROY_SNAPSHOTS
    else:
        rsrc = open_resource(tls, data["path"])
        if rsrc.type == truenas_pylibzfs.ZFSType.ZFS_TYPE_FILESYSTEM:
            mnt = rsrc.get_properties(properties={truenas_pylibzfs.ZFSProperty.MOUNTPOINT})
            if mnt.mountpoint.value != "legacy":
                mntpnts.append(mnt)
            rsrc.unmount(recursive=recursive)
        rcpa["script"] = truenas_pylibzfs.lzc.ChannelProgramEnum.DESTROY_RESOURCES

    try_again = False
    res = truenas_pylibzfs.lzc.run_channel_program(**rcpa)
    if res["return"]["holds"]:
        try_again = True
        truenas_pylibzfs.lzc.release_holds(holds=set(res["return"]["holds"].items()))

    if res["return"]["clones"]:
        try_again = True
        for clone, err in res["return"]["clones"].items():
            if err == errno.EBUSY:
                rsrc = open_resource(tls, clone)
                if rsrc.type == truenas_pylibzfs.ZFSType.ZFS_TYPE_FILESYSTEM:
                    mnt = rsrc.get_properties(properties={truenas_pylibzfs.ZFSProperty.MOUNTPOINT})
                    if mnt.mountpoint.value != "legacy":
                        mntpnts.append(mnt)
                    rsrc.unmount(recursive=recursive)
            # TODO: else raise ZFSException(err) if not EBUSY??

    if try_again:
        res = truenas_pylibzfs.lzc.run_channel_program(**rcpa)

    failed, errnum = None, None
    if res["return"]["failed"]:
        failed = f"Failed to destroy {data['path']!r}"
        if res["return"]["clones"]:
            failed += f" There are clones ({','.join(tuple(res['clones'].keys()))})"
            errnum = errno.EBUSY
        elif res["return"]["holds"]:
            failed += f" There are holds ({','.join(tuple(res['holds'].keys()))})"
            errnum = errno.EBUSY
        else:
            errnum = res["return"]["failed"].get(data["path"], errno.EFAULT)
            if errnum in truenas_pylibzfs.ZFSError:
                failed += f" ({truenas_pylibzfs.ZFSError(errnum)})"
    else:
        for i in mntpnts:
            try:
                os.rmdir(i.mountpoint.value)
            except Exception:
                # silently ignore rmdir ops
                # which mimics upstream zfs
                pass

    return failed, errnum
