from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from fenced.fence import ExitCode as FencedExitCodes
from truenas_pylicensed.features import LicenseFeature

from middlewared.api.current import ZpoolCreate, ZpoolEntry, ZpoolQuery
from middlewared.plugins.pool_.utils import ZPOOL_CACHE_FILE, UpdateImplArgs
from middlewared.service_exception import CallError, ValidationErrors

from .create_impl import convert_topology_to_vdevs, properties_to_zfs
from .create_rules import (
    SCHEMA,
    CreateContext,
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

__all__ = ("create", "finish", "prepare_disks", "register", "rollback")


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


def prepare_disks(
    context: ServiceContext,
    job: Job,
    disks: dict[str, Any],
    log_disks: list[str],
    all_sed: bool,
    schema: str,
    base_percentage: int = 0,
    upper_percentage: int = 30,
) -> None:
    """Take the disks a new pool will be built on, in the only safe order.

    ``disks`` is the map ``convert_topology_to_vdevs`` produced; ``pool.format_disks``
    fills each vdev's device list in place with the formatted ``/dev/<gptid>``
    paths. Shared by ``pool.create`` and ``zpool.create``.
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

    context.middleware.call_sync("pool.format_disks", job, disks, base_percentage, upper_percentage)
    os.makedirs(os.path.dirname(ZPOOL_CACHE_FILE), exist_ok=True)


def register(context: ServiceContext, name: str, all_sed: bool) -> int:
    """Make a freshly created pool a TrueNAS pool and return its database id.

    Inherits the mountpoint again (creation sets it, which makes the source
    "local"), mounts the root, and adds the ``storage.volume`` and default
    ``storage.scrub`` rows. Shared by ``pool.create`` and ``zpool.create``.
    """
    guid = context.call_sync2(context.s.zpool.query_impl, ZpoolQuery(pool_names=[name]))[0]["guid"]
    context.middleware.call_sync("pool.dataset.update_impl", UpdateImplArgs(name=name, iprops={"mountpoint"}))
    context.call_sync2(context.s.zfs.resource.mount, name)
    pool_id: int = context.middleware.call_sync(
        "datastore.insert",
        "storage.volume",
        {"name": name, "guid": str(guid), "all_sed": all_sed},
        {"prefix": "vol_"},
    )
    context.middleware.call_sync("datastore.insert", "storage.scrub", {"volume": pool_id}, {"prefix": "scrub_"})
    return pool_id


def rollback(context: ServiceContext, name: str, destroy: bool, pool_id: int | None) -> None:
    """Undo a failed creation: destroy the pool if it got created, drop its row if it got one."""
    if destroy:
        try:
            context.middleware.call_sync("zfs.pool.delete", name)
        except Exception:
            context.logger.warning(
                "%s: failed to destroy the pool while rolling back its creation", name, exc_info=True
            )
    if pool_id:
        context.middleware.call_sync("datastore.delete", "storage.volume", pool_id)


def finish(context: ServiceContext, name: str, pool_id: int) -> dict[str, Any]:
    """Run the post-creation hooks and events and return the ``pool.query`` entry."""
    # There is really no point in waiting for all these services to reload so do
    # them in the background.
    context.middleware.call_sync("pool.restart_services", background=True)

    pool: dict[str, Any] = context.middleware.call_sync("pool.get_instance", pool_id)
    context.middleware.call_hook_sync("pool.post_create", pool=pool)
    context.middleware.call_hook_sync("pool.post_create_or_update", pool=pool)
    context.middleware.send_event("pool.query", "ADDED", id=pool_id, fields=pool)
    context.call_sync2(context.s.zpool.send_change_event, name, "ADDED")
    return pool


def create(context: ServiceContext, job: Job, data: ZpoolCreate) -> ZpoolEntry:
    name = data.name
    properties, filesystem_properties = resolve_create_request(data)
    ctx = CreateContext(properties=properties, filesystem_properties=filesystem_properties)

    verrors = ValidationErrors()
    collect(verrors, check_disks_unique, data, ctx)
    collect(verrors, check_min_disks, data, ctx)

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
        context.call_sync2(context.s.zpool.query_impl, ZpoolQuery(pool_names=[name]))
        or context.call_sync2(context.s.zpool.query, ZpoolQuery(pool_names=[name]))
    )
    collect(verrors, check_pool_absent, data, ctx)
    verrors.add_child(
        SCHEMA,
        context.middleware.call_sync("disk.check_disks_availability", list(disks), data.allow_duplicate_serials),
    )
    verrors.check()

    ctx.disk_sizes = {i.name: i.size_bytes for i in context.middleware.call_sync("disk.get_disks") if i.name in disks}
    collect(verrors, check_spare_sizes, data, ctx)
    verrors.check()

    log_disks = [disk for vdev in data.topology.log for disk in vdev.disks]
    prepare_disks(context, job, disks, log_disks, data.all_sed, SCHEMA)

    pool_id: int | None = None
    created = False
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
        job.set_progress(95, "Setting pool options")
        pool_id = register(context, name, data.all_sed)
    except Exception as e:
        context.logger.debug("Pool %r failed to create with topology %r", name, data.topology.model_dump())
        rollback(context, name, created, pool_id)
        if isinstance(e, ZpoolException):
            raise CallError(str(e), e.errno) from e
        raise

    finish(context, name, pool_id)
    return context.call_sync2(
        context.s.zpool.query,
        ZpoolQuery(pool_names=[name], topology=True, properties=list(pool_properties)),
    )[0]
