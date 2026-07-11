from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from middlewared.service import CallError
from middlewared.utils import run
from middlewared.utils.boot.models import BootFormatOptions, BootUpdateInitramfsOptions
from middlewared.utils.boot.pool import get_boot_pool_name
from middlewared.utils.disks import valid_zfs_partition_uuids

from .disks import get_disks_cache, get_state_dict
from .format import format_disk, install_loader, legacy_schema

if TYPE_CHECKING:
    from middlewared.api.current import BootAttachOptions
    from middlewared.job import Job
    from middlewared.service import ServiceContext


async def check_update_ashift_property(context: ServiceContext) -> None:
    boot_pool = get_boot_pool_name()
    zfs_pool = await context.middleware.call("zpool.query_impl", {"pool_names": [boot_pool], "properties": ["ashift"]})
    if zfs_pool and zfs_pool[0]["properties"]["ashift"]["source"] == "DEFAULT":
        await context.middleware.call("zfs.pool.update", boot_pool, {"properties": {"ashift": {"value": "12"}}})


async def attach(context: ServiceContext, job: Job, dev: str, options: BootAttachOptions) -> None:
    boot_pool = get_boot_pool_name()
    await check_update_ashift_property(context)
    disks = list(await get_disks_cache(context))
    if len(disks) > 1:
        raise CallError("3-way mirror not supported")

    size = None
    if not options.expand:
        # Lets try to find out the size of the current ZFS or FreeBSD-ZFS (upgraded TrueNAS CORE installation)
        # partition so the new partition is not bigger, preventing size mismatch if one of them fail later on.
        zfs_part = await context.middleware.call(
            "disk.get_partition_with_uuids",
            disks[0],
            list(valid_zfs_partition_uuids()),
        )
        if zfs_part:
            size = zfs_part["size"]

    schema = await legacy_schema(context, disks[0])
    await format_disk(context, dev, BootFormatOptions(size=size, legacy_schema=schema))

    pool = (await context.middleware.call("zpool.query_impl", {"pool_names": [boot_pool], "topology": True}))[0]
    boot_vdev = pool["topology"]["data"][0]
    zfs_dev_part = await context.middleware.call("disk.get_partition", dev)
    extend_pool_job = await context.middleware.call(
        "zfs.pool.extend",
        boot_pool,
        None,
        [{"target": boot_vdev["guid"], "type": "DISK", "path": f"/dev/{zfs_dev_part['name']}"}],
    )

    await install_loader(context, dev)

    await job.wrap(extend_pool_job)

    # If the user is upgrading his disks, let's set expand to True to make sure that we
    # register the new disks capacity which increase the size of the pool
    await context.middleware.call("zfs.pool.online", boot_pool, zfs_dev_part["name"], True)
    await context.call2(context.s.boot.update_initramfs, BootUpdateInitramfsOptions())


async def detach(context: ServiceContext, dev: str) -> None:
    await check_update_ashift_property(context)
    await context.middleware.call("zfs.pool.detach", get_boot_pool_name(), dev, {"clear_label": True})
    await context.call2(context.s.boot.update_initramfs, BootUpdateInitramfsOptions())


async def replace(context: ServiceContext, job: Job, label: str, dev: str) -> None:
    boot_pool = get_boot_pool_name()
    await check_update_ashift_property(context)
    disks = list(await get_disks_cache(context))

    schema = await legacy_schema(context, disks[0])

    job.set_progress(0, f"Formatting {dev}")
    await format_disk(context, dev, BootFormatOptions(legacy_schema=schema))

    job.set_progress(0, f"Replacing {label} with {dev}")
    zfs_dev_part = await context.middleware.call("disk.get_partition", dev)
    await context.middleware.call("zfs.pool.replace", boot_pool, label, zfs_dev_part["name"])

    # We need to wait for pool resilver after replacing a device, otherwise grub might
    # fail with `unknown filesystem` error
    while True:
        state = await get_state_dict(context)
        if state["scan"] and state["scan"]["function"] == "RESILVER" and state["scan"]["state"] == "SCANNING":
            left = int(state["scan"]["total_secs_left"]) if state["scan"]["total_secs_left"] else "unknown"
            job.set_progress(int(state["scan"]["percentage"]), f"Resilvering boot pool, {left} seconds left")
            await asyncio.sleep(5)
        else:
            break

    job.set_progress(100, "Installing boot loader")
    await install_loader(context, dev)
    await context.call2(context.s.boot.update_initramfs, BootUpdateInitramfsOptions())


async def scrub(context: ServiceContext, job: Job) -> None:
    subjob = await context.middleware.call("pool.scrub.scrub", get_boot_pool_name())
    await job.wrap(subjob)


async def set_scrub_interval(context: ServiceContext, interval: int) -> int:
    await context.middleware.call(
        "datastore.update",
        "system.advanced",
        (await context.call2(context.s.system.advanced.config)).id,
        {"adv_boot_scrub": interval},
    )
    return interval


async def expand(context: ServiceContext) -> None:
    await check_update_ashift_property(context)
    boot_pool = get_boot_pool_name()
    for device in await context.middleware.call("zfs.pool.get_devices", boot_pool):
        try:
            await expand_device(context, device)
        except CallError as e:
            context.logger.error("Error trying to expand boot pool partition %r: %r", device, e)
        except Exception:
            context.logger.error("Error trying to expand boot pool partition %r", device, exc_info=True)


async def expand_device(context: ServiceContext, device: str) -> None:
    disk = await context.middleware.call("disk.get_disk_from_partition", device)

    partitions = await context.middleware.call("disk.list_partitions", disk)
    if len(partitions) != 3:
        raise CallError(f"Expected 3 partitions, found {len(partitions)}")

    if partitions[-1]["name"] != device:
        raise CallError(f"{device} is not the last partition")

    if partitions[-1]["partition_number"] != 3:
        raise CallError(f"{device} is not 3rd partition")

    if partitions[-1]["start_sector"] != partitions[-2]["end_sector"] + 1:
        raise CallError(f"{device} does not immediately follow the 2nd partition")

    disk_size = await context.middleware.call("disk.get_dev_size", disk)
    if partitions[-1]["end"] > disk_size / 1.1:
        return

    context.logger.info(
        "Resizing boot pool partition %r from %r (disk_size = %r)", device, partitions[-1]["end"], disk_size
    )
    await run("sgdisk", "-d", "3", f"/dev/{disk}", encoding="utf-8", errors="ignore")
    await run("sgdisk", "-N", "3", f"/dev/{disk}", encoding="utf-8", errors="ignore")
    await run("partprobe", encoding="utf-8", errors="ignore")
    await run("zpool", "online", "-e", "boot-pool", device, encoding="utf-8", errors="ignore")
