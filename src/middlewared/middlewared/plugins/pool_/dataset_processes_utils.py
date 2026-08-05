from __future__ import annotations

from middlewared.plugins.zfs_.utils import zvol_name_to_path
from middlewared.service import ServiceContext

__all__ = ("processes_using_dataset_tree",)


async def processes_using_dataset_tree(ctx: ServiceContext, name: str) -> list[dict]:
    """Find processes with open files on a dataset or on any dataset beneath it.

    `pool.dataset.processes` only covers the single dataset it is given. It matches
    open files by the device id of the scanned mountpoint, and every ZFS dataset is a
    separate filesystem with its own device id, so a process holding a child dataset
    open is invisible to it. Anything acting on a whole pool has to scan the entire
    tree, otherwise a busy child is missed and the pool fails to export.

    Internal datasets are left out, as they are by any other dataset query. Their
    consumers are shut down separately (the attachment delegates for apps, the
    `pool.pre_export` hook for the system dataset), and treating them as ordinary
    datasets here would mean killing processes that hold the system dataset open.

    Args:
        ctx: Service context
        name: Dataset to scan along with all of its descendants

    Returns:
        Processes as reported by `pool.dataset.processes_using_paths`
    """
    paths = []
    for ds in await ctx.middleware.call(
        "pool.dataset.query",
        [["OR", [["id", "=", name], ["id", "^", f"{name}/"]]]],
        # `keystatus` is what populates `locked`. `mountpoint` is deliberately not
        # requested: left out, it is reported as the live mount state (`null` when the
        # dataset is not mounted) rather than as the ZFS property, which still holds a
        # path. Only the mount state is usable here. An unmounted dataset has no open
        # files by definition, and stat'ing its leftover mountpoint directory would
        # report the device id of whichever filesystem that directory sits on -- the
        # boot environment's /mnt dataset for an unmounted pool root -- so every match
        # against it would be a process that has nothing to do with this pool.
        {"extra": {"properties": ["keystatus"], "retrieve_children": False}},
    ):
        if ds["locked"]:
            continue
        elif ds["type"] == "VOLUME":
            paths.append(zvol_name_to_path(ds["name"]))
        elif ds["mountpoint"]:
            paths.append(ds["mountpoint"])

    return await ctx.middleware.call("pool.dataset.processes_using_paths", paths)
