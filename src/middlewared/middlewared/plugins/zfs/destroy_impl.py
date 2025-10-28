import errno

from .exceptions import ZFSPathHasClonesException, ZFSPathHasHoldsException
from .utils import open_resource

try:
    import truenas_pylibzfs
except ImportError:
    truenas_pylibzfs = None

__all__ = ("destroy_impl",)


def destroy_nonrecursive_impl(tls, data):
    path = data["path"]
    rsrc = open_resource(tls, data["path"])
    if rsrc == truenas_pylibzfs.ZFSType.ZFS_TYPE_SNAPSHOT:
        holds = rsrc.get_holds()
        if holds:
            raise ZFSPathHasHoldsException(path, holds)
        clones = rsrc.get_clones()
        if clones:
            raise ZFSPathHasClonesException(path, clones)

    failed, errnum = None, None
    if "@" not in path:
        try:
            rsrc.unmount()
        except truenas_pylibzfs.ZFSException as e:
            failed = f"Failed to unmount {path!r}: {e}"
            errnum = e.code
        else:
            try:
                tls.lzh.destroy_resource(name=path)
            except truenas_pylibzfs.ZFSException as e:
                failed = f"Failed to destroy {path!r}: {e}"
                errnum = e.code
    else:
        try:
            truenas_pylibzfs.lzc.destroy_snapshots(snapshot_names=(path,))
        except truenas_pylibzfs.ZFSException as e:
            failed = f"Failed to destroy {path!r}: {e}"
            errnum = e.code

    return failed, errnum


def destroy_impl(tls, data):
    recursive = data.get("recursive", False)
    all_snaps = data.get("all_snapshots", False)
    if not recursive and not all_snaps:
        return destroy_nonrecursive_impl(tls, data)

    target = data["path"].split("@")[0]
    rcpa = {
        "pool_name": data["path"].split("/")[0],
        "script": None,
        "script_arguments_dict": {
            "recursive": recursive,
            "defer": False,
            "target": target,
        },
        "readonly": False,
    }
    if "@" in data["path"]:
        rcpa["script"] = truenas_pylibzfs.lzc.ChannelProgramEnum.DESTROY_SNAPSHOTS
        rcpa["script_arguments_dict"].update({"pattern": data["path"].split("@")[-1]})
    elif all_snaps:
        rcpa["script"] = truenas_pylibzfs.lzc.ChannelProgramEnum.DESTROY_SNAPSHOTS
    else:
        rsrc = open_resource(tls, data["path"])
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
                rsrc = open_resource(name=clone)
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

    return failed, errnum
