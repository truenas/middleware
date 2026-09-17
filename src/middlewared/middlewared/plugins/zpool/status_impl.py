import json
from pathlib import Path
import subprocess
from typing import Any

from middlewared.service import CallError, ValidationError

__all__ = ("status_impl",)

VDEV_TYPES = ("spares", "logs", "dedup", "special", "l2cache", "data")


def get_zpool_status(pool_name: str | None = None) -> dict[str, Any]:
    args = [pool_name] if pool_name else []
    cp = subprocess.run(["zpool", "status", "-jP", "--json-int"] + args, capture_output=True, check=False)
    if cp.returncode:
        if b"no such pool" in cp.stderr:
            raise ValidationError("zpool.status", f"{pool_name!r} not found")

        raise CallError(f"Failed to get zpool status: {cp.stderr.decode()}")

    pools: dict[str, Any] = json.loads(cp.stdout)["pools"]
    return pools


def resolve_block_path(path: str, should_resolve: bool) -> str:
    if not should_resolve:
        return path

    try:
        dev = Path(path).resolve().name
        resolved = Path(f"/sys/class/block/{dev}").resolve().parent.name
        if resolved == "block":
            # example zpool status
            # NAME                                          STATE     READ WRITE CKSUM
            # tank                                          DEGRADED     0     0     0
            #   mirror-0                                    DEGRADED     0     0     0
            #       sdrh1                                   ONLINE       0     0     0
            #       7008beaf-4fa3-4c43-ba15-f3d5bea3fe0c    REMOVED      0     0     0
            #       sda1                                    ONLINE       0     0     0
            return dev
        return resolved
    except Exception:
        return path


def resolve_block_paths(paths: list[str], should_resolve: bool) -> list[str]:
    if not should_resolve:
        return paths

    return [resolve_block_path(i, should_resolve) for i in paths]


def get_normalized_disk_info(
    pool_name: str, disk: dict[str, Any], vdev_name: str, vdev_type: str, vdev_disks: list[str]
) -> dict[str, Any]:
    return {
        "pool_name": pool_name,
        "disk_status": disk["state"],
        "disk_read_errors": disk.get("read_errors", 0),
        "disk_write_errors": disk.get("write_errors", 0),
        "disk_checksum_errors": disk.get("checksum_errors", 0),
        "vdev_name": vdev_name,
        "vdev_type": vdev_type,
        "vdev_disks": vdev_disks,
    }


def get_zfs_vdev_disks(vdev: dict[str, Any]) -> list[str]:
    # We get this safely because of draid based vdevs
    if vdev.get("state") in ("UNAVAIL", "OFFLINE"):
        return []

    vdev_type = vdev.get("vdev_type")
    if vdev_type == "disk":
        return [vdev["path"]]
    elif vdev_type == "file":
        return []
    else:
        result: list[str] = []
        for i in vdev.get("vdevs", {}).values():
            result.extend(get_zfs_vdev_disks(i))
        return result


def vdev_members_info(pool_name: str, vdev_type: str, members: dict[str, Any], real_paths: bool) -> dict[str, Any]:
    final: dict[str, Any] = dict()
    for member in filter(lambda x: x.get("vdev_type") != "file", members.values()):
        vdev_disks = resolve_block_paths(get_zfs_vdev_disks(member), real_paths)
        if member.get("vdev_type") in ("disk", "dspare"):
            disk = resolve_block_path(member["path"], real_paths)
            final[disk] = get_normalized_disk_info(pool_name, member, "stripe", vdev_type, vdev_disks)
        else:
            for i in member["vdevs"].values():
                if i["vdev_type"] == "spare":
                    i_vdevs = list(i["vdevs"].values())
                    if not i_vdevs:
                        # An edge case but just covering to be safe
                        continue

                    i = next((e for e in i_vdevs if e["class"] == "spare"), i_vdevs[0])
                elif i["vdev_type"] == "replacing":
                    for j in filter(lambda entry: entry.get("path"), list(i["vdevs"].values())):
                        disk = resolve_block_path(j["path"], real_paths)
                        final[disk] = get_normalized_disk_info(pool_name, j, member["name"], vdev_type, vdev_disks)
                    continue

                disk = resolve_block_path(i["path"], real_paths)
                final[disk] = get_normalized_disk_info(pool_name, i, member["name"], vdev_type, vdev_disks)

    return final


def status_impl(name: str | None = None, real_paths: bool = False) -> dict[str, Any]:
    final: dict[str, Any] = {"disks": dict(), "pools": dict()}
    for pool_name, pool_info in get_zpool_status(name).items():
        final["pools"][pool_name] = dict()
        # We need some normalization for data vdev here
        pool_info["data"] = pool_info.get("vdevs", {}).get(pool_name, {}).get("vdevs", {})
        for vdev_type in VDEV_TYPES:
            vdev_members = pool_info.get(vdev_type, {})
            if not vdev_members:
                final["pools"][pool_name][vdev_type] = dict()
                continue

            info = vdev_members_info(pool_name, vdev_type, vdev_members, real_paths)
            # we key on pool name and disk id because
            # this was designed, primarily, for the
            # `webui.enclosure.dashboard` endpoint
            final["pools"][pool_name][vdev_type] = info
            final["disks"].update(info)

    return final
