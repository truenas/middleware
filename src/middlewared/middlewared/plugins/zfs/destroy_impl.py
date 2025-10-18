import errno

try:
    import truenas_pylibzfs
except ImportError:
    truenas_pylibzfs = None

__all__ = ("destroy_impl",)


def destroy_impl(tls, data):
    rcpa = {
        "pool_name": data["path"].split("/")[0],
        "script": None,
        "script_arguments_dict": {
            "recursive": data["recursive"],
            "defer": False,
            "target": data["path"].split("@")[0],
        },
        "readonly": False,
    }
    if "@" in data["path"]:
        rcpa["script"] = truenas_pylibzfs.lzc.ChannelProgramEnum.DESTROY_SNAPSHOTS
        rcpa["script_arguments_dict"].update({"pattern": data["path"].split("@")[-1]})
    elif data["all_snapshots"]:
        rcpa["script"] = truenas_pylibzfs.lzc.ChannelProgramEnum.DESTROY_SNAPSHOTS
    else:
        rcpa["script"] = truenas_pylibzfs.lzc.ChannelProgramEnum.DESTROY_RESOURCES

    try_again = False
    res = truenas_pylibzfs.lzc.run_channel_program(**rcpa)
    if res["return"]["holds"] and data["remove_holds"]:
        try_again = True
        truenas_pylibzfs.lzc.release_holds(holds=set(res["holds"].items()))

    if res["return"]["clones"] and data["remove_clones"]:
        try_again = True
        for clone, err in res["clones"].items():
            if err == errno.EBUSY:
                tls.lzh.open_resoure(name=clone).unmount(recursive=data["recursive"])
            # TODO: else raise ZFSException(err) if not EBUSY??

    if try_again:
        res = truenas_pylibzfs.lzc.run_channel_program(**rcpa)
    return res["return"]
