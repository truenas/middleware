from dataclasses import dataclass, field
from os import stat

from middlewared.plugins.zfs_.utils import TNUserProp
from middlewared.utils import BOOT_POOL_NAME_VALID
from middlewared.utils.filesystem.constants import ZFSCTL

try:
    import truenas_pylibzfs
except ImportError:
    truenas_pylibzfs = None

__all__ = (
    "CallbackState",
    "details_callback",
)


@dataclass(slots=True, kw_only=True)
class CallbackState:
    index: dict = field(default_factory=dict)
    results: list = field(default_factory=list)


def build_zfs_properties_set(hdl) -> set[truenas_pylibzfs.ZFSProperty]:
    props = {
        truenas_pylibzfs.ZFSProperty.USED,
        truenas_pylibzfs.ZFSProperty.AVAILABLE,
        truenas_pylibzfs.ZFSProperty.USEDSNAP,
        truenas_pylibzfs.ZFSProperty.USEDDS,
        truenas_pylibzfs.ZFSProperty.USEDCHILD,
        truenas_pylibzfs.ZFSProperty.ORIGIN,
        truenas_pylibzfs.ZFSProperty.REFRESERVATION,
        truenas_pylibzfs.ZFSProperty.RESERVATION,
        truenas_pylibzfs.ZFSProperty.ENCRYPTION,
        truenas_pylibzfs.ZFSProperty.ENCRYPTION_ROOT,
        truenas_pylibzfs.ZFSProperty.KEYFORMAT,
        truenas_pylibzfs.ZFSProperty.KEYSTATUS,
        truenas_pylibzfs.ZFSProperty.SYNC,
        truenas_pylibzfs.ZFSProperty.COMPRESSION,
        truenas_pylibzfs.ZFSProperty.COMPRESSRATIO,
        truenas_pylibzfs.ZFSProperty.DEDUP,
        truenas_pylibzfs.ZFSProperty.READONLY,
    }
    if hdl.type == truenas_pylibzfs.ZFSType.ZFS_TYPE_FILESYSTEM:
        props.add(truenas_pylibzfs.ZFSProperty.QUOTA)
        props.add(truenas_pylibzfs.ZFSProperty.REFQUOTA)
        props.add(truenas_pylibzfs.ZFSProperty.MOUNTPOINT)
        props.add(truenas_pylibzfs.ZFSProperty.CASESENSITIVE)
    elif hdl.type == truenas_pylibzfs.ZFSType.ZFS_TYPE_VOLUME:
        props.add(truenas_pylibzfs.ZFSProperty.VOLSIZE)
    return props


def parse_zfs_properties(zprops: dict[str, dict]) -> dict[str, dict]:
    props = dict()
    for zfs_prop_name, vdict in zprops.items():
        props[zfs_prop_name] = {
            "parsed": vdict["value"],
            "rawvalue": vdict["raw"],
            "value": vdict["raw"].upper(),
            "source": truenas_pylibzfs.PropertySource(vdict["source"]["type"]).name,
            "source_info": vdict["source"]["value"],
        }
    return props


def parse_zfs_user_properties(uprops: dict[str, str]) -> dict[str, dict]:
    props = {"user_properties": dict()}
    for k in (
        TNUserProp.REFQUOTA_CRIT.value,
        TNUserProp.REFQUOTA_WARN.value,
        TNUserProp.QUOTA_CRIT.value,
        TNUserProp.QUOTA_WARN.value,
    ):
        if val := uprops.get(k, None):
            props["user_properties"][k] = val
    return props


def snap_callback(hdl, state: dict[str, int]) -> dict[str, int]:
    if mp := state["properties"].get("mountpoint"):
        if not mp["parsed"] or mp["parsed"] == "legacy":
            return True

        # Retrieve snapshot count in most efficient way possible.
        # If dataset is mounted, then retrieve from st_nlink
        # otherwise, iter snapshots from dataset handle
        try:
            st = stat(f"{mp}/.zfs/snapshot")
            if st.st_ino == ZFSCTL.INO_SNAPDIR.value:
                state["snapshot_count"] += st.st_nlink - 2
        except Exception:
            pass
    return True


def use_iter_snaps_fallback(mountpoint: str | None, state: dict) -> bool:
    if mountpoint is None or mountpoint == "legacy":
        return True

    # Retrieve snapshot count in most efficient way possible.
    # If dataset is mounted, then retrieve from st_nlink
    # otherwise, iter snapshots from dataset handle
    try:
        st = stat(f"{mountpoint}/.zfs/snapshot")
        if st.st_ino == ZFSCTL.INO_SNAPDIR.value:
            state["snapshot_count"] += st.st_nlink - 2
    except Exception:
        return True

    return False


def get_info(hdl):
    info = hdl.asdict(
        properties=build_zfs_properties_set(hdl),
        get_user_properties=True,
        get_crypto=True,
        get_source=True,
    )
    final = {
        "id": info["name"],
        "type": info["type"].removeprefix("ZFS_TYPE_"),
        "name": info["name"],
        "pool": hdl.pool_name,
        "snapshot_count": 0,
        **parse_zfs_properties(info["properties"]),
        **parse_zfs_user_properties(info["user_properties"]),
        "children": list(),
    }
    if use_iter_snaps_fallback(final.get("mountpoint"), final):
        hdl.iter_snapshots(callback=snap_callback, state=final, fast=True)
    return final


def details_callback(hdl, state: CallbackState):
    """
    Builds a nested tree-like dictionary structure from a list of filesystem-style paths.

    Each path is split by forward slashes ("/"), and a nested dictionary is created where each
    part of the path becomes a node. All nodes, including leaf nodes, contain a "children" key
    (an empty list if there are no further children).

    Parameters:
        paths (list of str): A list of string paths, e.g., ["a", "a/b", "a/b/c"].

    Returns:
        list: A list representing the nested tree structure, where each node is a dictionary
              with a single key (the part name) mapping to a dictionary with a "children" list.
    """
    if hdl.name in BOOT_POOL_NAME_VALID:
        # ignore boot pool
        return True

    curr_path = ""
    curr_list = state.results
    for part in hdl.name.split("/"):
        curr_path = f"{curr_path}/{part}" if curr_path else part
        if curr_path not in state.index:
            if curr_path == hdl.name:
                node = {curr_path: get_info(hdl)}
            else:
                node = {curr_path: {"children": []}}
            curr_list.append(node[curr_path])
            state.index[curr_path] = node[curr_path]["children"]
        curr_list = state.index[curr_path]
    hdl.iter_filesystems(callback=details_callback, state=state, fast=True)
    return True
