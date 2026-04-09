from __future__ import annotations
import errno
import os
import time
import typing

import truenas_pylibzfs

from middlewared.api.current import (
    ZPoolCreate, ZPoolCreateTopology, ZPoolCreateDataVdev, ZPoolCreateVdevDRAID, ZPoolCreateVdevNonDRAID
)
from middlewared.service import ValidationErrors
if typing.TYPE_CHECKING:
    from middlewared.main import Job, Middleware

__all__ = ("create_impl",)

_PARTUUID_DIR = "/dev/disk/by-partuuid"
_VDEV_GROUPS = ("data", "cache", "log", "special", "dedup")


def _validate(
    middleware: Middleware,
    lzh: truenas_pylibzfs.libzfs_types.ZFS,
    data: ZPoolCreate,
) -> None:
    """Pre-format validation: pool name, disk availability, DRAID+spares."""
    verrors = ValidationErrors()
    name = data.name
    topology = data.topology

    # Pool name format
    if not truenas_pylibzfs.name_is_valid(name=name, type=truenas_pylibzfs.ZFSType.ZFS_TYPE_POOL):
        verrors.add("zpool_create.name", "Invalid pool name", errno.EINVAL)

    # Pool name uniqueness (only check if format is valid)
    if not verrors:
        try:
            lzh.open_pool(name=name)
        except truenas_pylibzfs.ZFSException:
            pass  # Pool does not exist — good
        else:
            verrors.add(
                "zpool_create.name",
                "A pool with this name already exists.",
                errno.EEXIST,
            )

    # Disk availability
    disk_names = _collect_disk_names(topology)
    if disk_names:
        disk_verrors = middleware.call_sync(
            "disk.check_disks_availability",
            disk_names,
            data.allow_duplicate_serials,
        )
        verrors.extend(disk_verrors)

    # DRAID + dedicated spares
    # NAS-140629 for context
    has_draid = any(isinstance(vdev, ZPoolCreateVdevDRAID) for vdev in topology.data)
    if has_draid and topology.spares:
        verrors.add(
            "zpool_create.topology.spares",
            "Dedicated spare disks should not be used with dRAID.",
        )

    verrors.check()


def _collect_disk_names(topology: ZPoolCreateTopology) -> list[str]:
    """Gather every unique disk name referenced in the topology."""
    names: set[str] = set()
    for group in _VDEV_GROUPS:
        for vdev in getattr(topology, group):
            vdev: ZPoolCreateDataVdev
            names.update(vdev.disks)
    names.update(topology.spares)
    return list(names)


def _format_disks(
    middleware: Middleware,
    job: Job,
    topology: ZPoolCreateTopology,
) -> dict[str, str]:
    """Format every disk in the topology and return {disk_name: by-partuuid path}.

    Each disk is formatted via DiskEntry.format() which returns a uuid.UUID
    for the newly-created ZFS partition.  We then wait for udev to materialise
    the /dev/disk/by-partuuid/<uuid> symlinks before returning.
    """
    disk_names = _collect_disk_names(topology)
    if not disk_names:
        return {}

    entries = {e.name: e for e in middleware.call_sync("disk.get_disks", disk_names)}
    disk_to_path: dict[str, str] = {}
    total = len(disk_names)
    for idx, name in enumerate(disk_names):
        entry = entries[name]
        part_uuid = entry.format()
        disk_to_path[name] = f"{_PARTUUID_DIR}/{part_uuid}"
        job.set_progress(
            int((idx + 1) / total * 80),
            f"Formatted disk {idx + 1}/{total} ({name})",
        )

    _wait_for_udev(middleware, disk_to_path, entries)
    return disk_to_path


def _wait_for_udev(
    middleware: Middleware,
    disk_to_path: dict[str, str],
    entries: dict,
    retries: int = 20,
    interval: float = 0.5,
) -> None:
    """Poll until every by-partuuid symlink exists, triggering udev if needed."""
    triggered = False
    for attempt in range(retries):
        missing = [
            name for name, path in disk_to_path.items() if not os.path.exists(path)
        ]
        if not missing:
            return

        if not triggered:
            for name in missing:
                middleware.call_sync(
                    "device.trigger_udev_events", entries[name].devpath
                )
            middleware.call_sync("device.settle_udev_events")
            triggered = True

        time.sleep(interval)

    still_missing = [
        f"{name} ({disk_to_path[name]})"
        for name in disk_to_path
        if not os.path.exists(disk_to_path[name])
    ]
    if still_missing:
        raise OSError(
            f"Timed out waiting for udev symlinks: {', '.join(still_missing)}"
        )


def _build_vdev_specs(
    vdevs: typing.Iterable[ZPoolCreateDataVdev],
    disk_to_path: dict[str, str],
) -> list[truenas_pylibzfs.libzfs_types.struct_vdev_create_spec] | None:
    """Convert a list of vdev dicts into create_vdev_spec objects.

    For STRIPE, produces individual leaf specs (one per disk).
    For MIRROR/RAIDZn/DRAIDn, produces a parent spec wrapping the leaf children.
    Returns None when vdevs is empty.
    """
    specs: list[truenas_pylibzfs.libzfs_types.struct_vdev_create_spec] = []
    for vdev in vdevs:
        leaves = [
            truenas_pylibzfs.create_vdev_spec(vdev_type="disk", name=disk_to_path[d])
            for d in vdev.disks
        ]

        vtype = vdev.type

        if vtype == "STRIPE":
            specs.extend(leaves)
        elif isinstance(vdev, ZPoolCreateVdevDRAID):
            specs.append(
                truenas_pylibzfs.create_vdev_spec(
                    vdev_type=vtype.lower(),
                    name=f"{vdev.draid_data_disks}d:{vdev.draid_spare_disks}s",
                    children=leaves,
                )
            )
        else:
            specs.append(
                truenas_pylibzfs.create_vdev_spec(
                    vdev_type=vtype.lower(),
                    children=leaves,
                )
            )

    return specs or None


def create_impl(
    middleware: Middleware,
    job: Job,
    lzh: truenas_pylibzfs.libzfs_types.ZFS,
    data: ZPoolCreate,
) -> None:
    """Format disks and create a ZFS pool.

    Args:
        middleware: Middleware instance for calling other services.
        job: Job object for progress reporting.
        lzh: pylibzfs handle (from tls.lzh).
        data: Validated ZPoolCreate dict.
    """
    _validate(middleware, lzh, data)

    topology = data.topology
    disk_to_path = _format_disks(middleware, job, topology)
    spare_vdevs = None
    if spares := topology.spares:
        spare_vdevs = _build_vdev_specs(
            (ZPoolCreateVdevNonDRAID(type="STRIPE", disks=spares),),
            disk_to_path
        )
    job.set_progress(90, "Creating ZFS pool")
    lzh.create_pool(
        name=data.name,
        storage_vdevs=_build_vdev_specs(topology.data, disk_to_path),
        cache_vdevs=_build_vdev_specs(topology.cache, disk_to_path),
        log_vdevs=_build_vdev_specs(topology.log, disk_to_path),
        special_vdevs=_build_vdev_specs(topology.special, disk_to_path),
        dedup_vdevs=_build_vdev_specs(topology.dedup, disk_to_path),
        spare_vdevs=spare_vdevs,
        properties=data.properties or None,
        filesystem_properties=data.fsoptions or None,
    )
    job.set_progress(100, "ZFS pool created successfully")
