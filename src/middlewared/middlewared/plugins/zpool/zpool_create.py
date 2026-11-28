from __future__ import annotations

import concurrent.futures
import errno
import os
from typing import TYPE_CHECKING, Any, Iterable

from fenced.fence import ExitCode as FencedExitCodes
from truenas_pylicensed.features import LicenseFeature

from middlewared.api.current import ZFSResourceSetArgsData, ZpoolCreate, ZpoolEntry, ZpoolListOptions
from middlewared.plugins.pool_.utils import ZPOOL_CACHE_FILE
from middlewared.service_exception import CallError, ValidationErrors

from .create_impl import DiskToFormat, convert_topology_to_vdevs, properties_to_zfs
from .create_rules import (
    SCHEMA,
    CreateContext,
    check_acl_combination,
    check_dedup_entitlement,
    check_disks_unique,
    check_force_entitlement,
    check_min_disks,
    check_pool_absent,
    check_sed_entitlement,
    check_spare_sizes,
    collect,
    dedup_requested,
    resolve_create_request,
)
from .exceptions import ZpoolCreateRejected, ZpoolException

if TYPE_CHECKING:
    from middlewared.job import Job
    from middlewared.service import ServiceContext
    from middlewared.utils.disks_.disk_class import DiskEntry, FormattedPartition

__all__ = ("create", "finish", "format_disks", "prepare_disks", "register", "release_disks", "rollback")


def _start_fenced(context: ServiceContext) -> None:
    rc = context.middleware.call_sync("failover.fenced.start")
    if not rc:
        return
    if rc == FencedExitCodes.ALREADY_RUNNING.value[0]:
        try:
            context.middleware.call_sync("failover.fenced.signal", {"reload": True})
        except Exception:
            context.logger.error("Unhandled exception reloading fenced", exc_info=True)
        return

    err = "Unexpected error starting fenced"
    for i in filter(lambda x: x.value[0] == rc, FencedExitCodes):
        err = i.value[1]
    raise CallError(err)


def _format_disk(context: ServiceContext, entry: DiskEntry) -> FormattedPartition:
    """Unlock a self-encrypting disk and write its GPT; the disk stays locked against udev."""
    if context.middleware.call_sync("disk.sed_unlock_impl", entry.name, True) is False:
        raise CallError(f"Failed to unlock {entry.name!r}. Check /var/log/middlewared.log")
    return entry.format()


def format_disks(
    context: ServiceContext,
    job: Job,
    disks: dict[str, DiskToFormat],
    base_percentage: int,
    upper_percentage: int,
) -> None:
    """Partition every disk for ZFS and add each partition's path to the device list of the vdev it joins.

    The partition table is written from Python. The wipe job, ``sgdisk`` run and udev wait that
    ``pool.format_disks`` spends on each disk added up to tens of minutes on systems with hundreds of disks.
    Each disk stays locked against udev afterwards, with its partition's link made by hand, until
    :func:`release_disks` hands it back once ZFS holds the partition.
    """
    entries = {entry.name: entry for entry in context.middleware.call_sync("disk.get_disks", list(disks))}
    for disk in disks:
        if disk not in entries:
            raise CallError(f"Unable to retrieve disk details for {disk!r}")
        if entries[disk].dif:
            raise CallError(f"Disk: {disk!r} is incorrectly formatted with Data Integrity Feature (DIF).")

    partitions: dict[str, FormattedPartition] = {}
    step = (upper_percentage - base_percentage) / len(disks)
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
        futures = {executor.submit(_format_disk, context, entries[disk]): disk for disk in disks}
        for done, future in enumerate(concurrent.futures.as_completed(futures), start=1):
            disk = futures[future]
            try:
                partitions[disk] = future.result()
            except Exception as e:
                executor.shutdown(cancel_futures=True)
                for other in futures:
                    if other.done() and not other.cancelled() and other.exception() is None:
                        other.result().release()
                if isinstance(e, CallError):
                    raise
                raise CallError(f"Failed formatting disk {disk!r}: {e}") from e
            job.set_progress(base_percentage + step * done, f"Formatting disks ({done}/{len(disks)})")

    for disk, config in disks.items():
        config["formatted"] = partitions[disk]
        config["vdev"].append(partitions[disk].path)


def release_disks(context: ServiceContext, disks: dict[str, DiskToFormat]) -> None:
    """Hand the formatted disks back to udev, once ZFS holds their partitions or creating the pool failed.

    udev then processes the partitions' events, replacing the links the format step made with its own
    in place. Never raises, since it runs on the failure path too.
    """
    for config in disks.values():
        if (formatted := config.pop("formatted", None)) is not None:
            formatted.release()
    try:
        context.middleware.call_sync("device.settle_udev_events")
    except Exception:
        context.logger.warning("Failed waiting for udev after releasing the formatted disks", exc_info=True)


def prepare_disks(
    context: ServiceContext,
    job: Job,
    disks: dict[str, DiskToFormat],
    log_disks: list[str],
    all_sed: bool,
    schema: str,
    base_percentage: int = 0,
    upper_percentage: int = 30,
) -> None:
    """Take the disks a new pool will be built on, in the only safe order.

    Shared by ``pool.create`` and ``zpool.create``.
    """
    if all_sed:
        context.middleware.call_sync("disk.setup_sed_disks_for_pool", list(disks), f"{schema}.topology", True)

    # WARNING: Fenced MUST NOT start (or reload) until SED provisioning above
    # has completed. Its persistent reservation register/acquire burst racing
    # the TCG Security Send/Receive session corrupts controller state on some
    # SED drive firmware (observed on TCG Ruby 1.0 NVMe). SED setup writes no
    # user data, so fencing is only required before disks are written to
    # (resize, format, zpool create), all of which happen below.
    if context.middleware.call_sync("failover.licensed"):
        _start_fenced(context)

    if log_disks and (osize := context.call_sync2(context.s.system.advanced.config).overprovision):
        # will log errors if there are any so it won't crash here (this matches CORE behavior)
        context.middleware.call_sync("disk.resize", {disk: osize for disk in log_disks}, True).wait_sync()

    os.makedirs(os.path.dirname(ZPOOL_CACHE_FILE), exist_ok=True)
    format_disks(context, job, disks, base_percentage, upper_percentage)


def register(context: ServiceContext, name: str, all_sed: bool) -> int:
    """Make a freshly created pool a TrueNAS pool and return its database id.

    Inherits the mountpoint again (creation sets it, which makes the source
    "local"), mounts the root, and adds the ``storage.volume`` and default
    ``storage.scrub`` rows. Shared by ``pool.create`` and ``zpool.create``.
    """
    # The disk records learn the new partitions and the pool only now that udev has processed them.
    context.middleware.call_sync("disk.sync_all").wait_sync(raise_error=True)
    guid = context.call_sync2(context.s.zpool.list_impl, ZpoolListOptions(pool_names=[name]))[0]["guid"]
    context.call_sync2(
        context.s.zfs.resource.set_impl,
        ZFSResourceSetArgsData(path=name, inherit=["mountpoint"], bypass=True),
    )
    context.call_sync2(context.s.zfs.resource.mount, name)
    pool_id: int = context.middleware.call_sync(
        "datastore.insert",
        "storage.volume",
        {"name": name, "guid": guid, "all_sed": all_sed},
        {"prefix": "vol_"},
    )
    context.middleware.call_sync("datastore.insert", "storage.scrub", {"volume": pool_id}, {"prefix": "scrub_"})
    return pool_id


def rollback(context: ServiceContext, name: str, destroy: bool, pool_id: int | None) -> None:
    """Undo a failed creation: destroy the pool if it got created, drop its row if it got one."""
    if destroy:
        try:
            # The root dataset may be mounted and busy by now; force unmounts it anyway.
            context.call_sync2(context.s.zpool.destroy_impl, name, True)
        except Exception:
            context.logger.warning(
                "%s: failed to destroy the pool while rolling back its creation", name, exc_info=True
            )
    if pool_id:
        context.middleware.call_sync("datastore.delete", "storage.volume", pool_id)


def finish(
    context: ServiceContext, name: str, pool_id: int, properties: Iterable[str] = ()
) -> tuple[dict[str, Any], ZpoolEntry | None]:
    """Run the post-creation hooks and events.

    Returns the ``pool.query`` entry and the ``zpool.list`` entry the ADDED
    event carried, read with ``properties`` included so a caller that wants
    them does not open the pool again.
    """
    # There is really no point in waiting for all these services to reload so do
    # them in the background.
    context.middleware.call_sync("pool.restart_services", background=True)

    pool: dict[str, Any] = context.middleware.call_sync("pool.get_instance", pool_id)
    context.middleware.call_hook_sync("pool.post_create", pool=pool)
    context.middleware.call_hook_sync("pool.post_create_or_update", pool=pool)
    context.middleware.send_event("pool.query", "ADDED", id=pool_id, fields=pool)
    entry = context.call_sync2(context.s.zpool.send_change_event, name, "ADDED", properties)
    return pool, entry


def create(context: ServiceContext, job: Job, data: ZpoolCreate) -> ZpoolEntry:
    name = data.name
    properties, filesystem_properties = resolve_create_request(data)
    ctx = CreateContext(properties=properties, filesystem_properties=filesystem_properties)

    # The two structural product rules first, on their own, so a vdev short of
    # disks is reported once rather than by both TrueNAS and the binding.
    verrors = ValidationErrors()
    collect(verrors, check_disks_unique, data, ctx)
    collect(verrors, check_min_disks, data, ctx)
    collect(verrors, check_acl_combination, data, ctx)
    verrors.check()

    # The entitlements are settled before any disk is looked at so an
    # unlicensed request fails without further work.
    if dedup_requested(data):
        ctx.dedup_entitlement = context.call_sync2(context.s.truenas.entitlements.check, LicenseFeature.DEDUP)
        collect(verrors, check_dedup_entitlement, data, ctx)
    if data.all_sed:
        ctx.sed_entitlement = context.call_sync2(context.s.truenas.entitlements.check, LicenseFeature.SED)
        collect(verrors, check_sed_entitlement, data, ctx)
    if data.force_topology:
        ctx.support_entitlement = context.call_sync2(context.s.truenas.entitlements.check, LicenseFeature.SUPPORT)
        collect(verrors, check_force_entitlement, data, ctx)

    # The binding judges the rest of the layout, the pool name and the
    # properties on the disk names alone, so a request it would refuse is
    # caught here rather than after the disks have been formatted for it.
    # It runs before the name is looked up, since the lookup needs a valid one.
    disks, vdevs = convert_topology_to_vdevs(data.topology)
    pool_properties = properties_to_zfs(ctx.properties)
    fs_properties = properties_to_zfs(ctx.filesystem_properties)
    try:
        context.call_sync2(
            context.s.zpool.validate_impl,
            name,
            vdevs,
            pool_properties,
            fs_properties,
            data.force_topology,
        )
    except ZpoolCreateRejected as e:
        verrors.add(f"{SCHEMA}.{e.location}" if e.location else SCHEMA, e.message, e.errno)
    verrors.check()

    # an imported pool of that name, registered or not, or a registered but
    # exported one both take the name
    ctx.pool_exists = bool(
        context.call_sync2(context.s.zpool.list_impl, ZpoolListOptions(pool_names=[name]))
        or context.middleware.call_sync("datastore.query", "storage.volume", [["name", "=", name]], {"prefix": "vol_"})
    )
    collect(verrors, check_pool_absent, data, ctx)
    verrors.add_child(
        SCHEMA,
        context.middleware.call_sync("disk.check_disks_availability", list(disks), data.allow_duplicate_serials),
    )
    verrors.check()

    ctx.disk_sizes = {i.name: i.size_bytes for i in context.middleware.call_sync("disk.get_disks", list(disks))}
    collect(verrors, check_spare_sizes, data, ctx)
    verrors.check()

    log_disks: list[str] = []
    for vdev in data.topology.log:
        log_disks.extend(vdev.disks)
    prepare_disks(context, job, disks, log_disks, data.all_sed, SCHEMA)

    pool_id: int | None = None
    created = False
    try:
        try:
            job.set_progress(90, "Creating ZFS Pool")
            context.call_sync2(
                context.s.zpool.create_impl,
                name,
                vdevs,
                pool_properties,
                fs_properties,
                data.force_topology,
            )
            created = True
        finally:
            release_disks(context, disks)
        job.set_progress(95, "Setting pool options")
        pool_id = register(context, name, data.all_sed)
    except Exception as e:
        context.logger.debug("Pool %r failed to create with topology %r", name, data.topology.model_dump())
        rollback(context, name, created, pool_id)
        if isinstance(e, ZpoolException):
            raise CallError(str(e), e.errno) from e
        raise

    _, entry = finish(context, name, pool_id, pool_properties)
    if entry is None:
        raise CallError(f"{name!r} was created but is no longer registered", errno.ENOENT)
    return entry
