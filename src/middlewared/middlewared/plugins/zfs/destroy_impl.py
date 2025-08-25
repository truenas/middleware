import dataclasses

try:
    from truenas_pylibzfs import ZFSError, ZFSException, lzc
except ImportError:
    ZFSError = ZFSException = lzc = None

__all__ = ("destroy_impl",)


@dataclasses.dataclass(slots=True, kw_only=True)
class DestroyState:
    results: dict[str, str | None]
    destroy_args: dict


def __destroy_fs_or_vols(hdl, dstate):
    for i in sorted(dstate.destroy_args["fs_or_vols"], reverse=True):
        # sorted in reverse to unmount and destroy children
        # first in the event recursive is false.
        # (i.e. tank/a/b/c, tank/a/b, tank/a)
        try:
            rsrc = hdl.open_resource(name=i)
        except ZFSException as e:
            if ZFSError(e.code) == ZFSError.EZFS_NOENT:
                dstate.results.update({i: f"{i!r} does not exist"})
                continue
            else:
                dstate.results.update({i: str(e)})
                continue
        else:
            try:
                rsrc.unmount(
                    force=dstate.destroy_args["force"],
                    recursive=dstate.destroy_args["recursive"],
                )
            except ZFSException as e:
                if (
                    ZFSError(e.code) == ZFSError.EZFS_BUSY
                    and not dstate.destroy_args["recursive"]
                ):
                    dstate.results.update({i: f"Failed to unmount, does {i!r} have children?"})
                    continue
                else:
                    dstate.results.update({i: str(e)})
                    continue
        try:
            if dstate.destroy_args["recursive"]:
                lzc.run_channel_program(
                    pool_name=i.split("/")[0],
                    script=lzc.ChannelProgramEnum.DESTROY_RESOURCES,
                    script_arguments_dict={
                        "recursive": dstate.destroy_args["recursive"],
                        "target": i,
                        "defer": dstate.destroy_args["defer"],
                    },
                    readonly=False,
                )
            else:
                hdl.destroy_resource(name=i)
        except Exception as e:
            dstate.results.update({i: str(e)})
        else:
            dstate.results.update({i: None})


def __destroy_snapshots(hdl, dstate):
    if dstate.destroy_args["snapshots"]["singular"]:
        try:
            lzc.destroy_snapshots(
                snapshot_names=dstate.destroy_args["snapshots"]["singular"]
            )
        except Exception as e:
            dstate.results.update(
                {i: str(e) for i in dstate.destroy_args["snapshots"]["singular"]}
            )
        else:
            dstate.results.update(
                {i: None for i in dstate.destroy_args["snapshots"]["singular"]}
            )

    for i in dstate.destroy_args["snapshots"]["channel_programs"]:
        name = i.pop("path")
        try:
            i.update({"script": lzc.ChannelProgramEnum.DESTROY_SNAPSHOTS})
            lzc.run_channel_program(**i)
        except Exception as e:
            dstate.results.update({name: str(e)})
        else:
            dstate.results.update({name: None})


def destroy_impl(hdl, data):
    """
    If recursive was given to us, then we take the
    liberty of executing the destructive operations
    via channel programs. There are pros and cons
    to using channel programs.
    Pros (not exhaustive):
        1. very fast
        2. efficient
        3. atomic

    The enforcement of atomcity is, arguably, the
    most important since modern programs are
    consistently creating/deleting zfs resources
    (Think CSI drivers for k8s, etc)
    Cons (not exhaustive):
        1. takes global lock at pool level and blocks
            any new zfs_open() (SMB, etc) calls until
            the channel program exits. This can be
            particularly painful if, say, someone is
            deleting many 10's of thousands of resources
            on a very busy system.
        2. can use too much memory and get killed creating
            an undefined state.
    """
    dstate = DestroyState(results=dict(), destroy_args=data)
    __destroy_fs_or_vols(hdl, dstate)
    __destroy_snapshots(hdl, dstate)
    return dstate.results
