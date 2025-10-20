import errno

try:
    import truenas_pylibzfs
except ImportError:
    truenas_pylibzfs = None

__all__ = ("destroy_impl",)


def destroy_impl(tls, data):
    target = data["path"].split("@")[0]
    recursive = data.get("recursive", False)
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
    elif data.get("all_snapshots", False):
        rcpa["script"] = truenas_pylibzfs.lzc.ChannelProgramEnum.DESTROY_SNAPSHOTS
    else:
        try:
            tls.lzh.open_resource(name=target).unmount(recursive=recursive)
        except Exception:
            # EBUSY will be raised if it has ancestors and recursive is false
            # in the channel program, so we'll pass here
            pass
        rcpa["script"] = truenas_pylibzfs.lzc.ChannelProgramEnum.DESTROY_RESOURCES

    try_again = False
    res = truenas_pylibzfs.lzc.run_channel_program(**rcpa)
    if res["return"]["holds"] and data.get("remove_holds", False):
        try_again = True
        truenas_pylibzfs.lzc.release_holds(holds=set(res["return"]["holds"].items()))

    if res["return"]["clones"] and data.get("remove_clones", False):
        try_again = True
        for clone, err in res["return"]["clones"].items():
            if err == errno.EBUSY:
                tls.lzh.open_resource(name=clone).unmount(recursive=recursive)
            # TODO: else raise ZFSException(err) if not EBUSY??

    if try_again:
        res = truenas_pylibzfs.lzc.run_channel_program(**rcpa)
    return res["return"]
