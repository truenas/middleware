from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from fenced.fence import ExitCode as FencedExitCodes
from truenas_pylicensed.features import LicenseFeature

from middlewared.api.current import ZpoolCreate, ZpoolEntry, ZpoolQuery
from middlewared.plugins.pool_.utils import UpdateImplArgs
from middlewared.service_exception import CallError, ValidationErrors

from .create_impl import convert_topology_to_vdevs, properties_to_zfs
from .create_rules import (
    SCHEMA,
    CreateContext,
    check_dedup_entitlement,
    check_force_entitlement,
    check_layout,
    check_name_valid,
    check_pool_absent,
    check_sed_entitlement,
    check_spare_sizes,
    collect,
    dedup_requested,
    resolve_create_request,
)
from .exceptions import ZpoolException

if TYPE_CHECKING:
    from middlewared.job import Job
    from middlewared.service import ServiceContext

__all__ = ("create",)


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


def create(context: ServiceContext, job: Job, data: ZpoolCreate) -> ZpoolEntry:
    name = data.name
    properties, filesystem_properties = resolve_create_request(data)
    ctx = CreateContext(properties=properties, filesystem_properties=filesystem_properties)

    verrors = ValidationErrors()
    collect(verrors, check_name_valid, data, ctx)
    # an imported pool of that name, registered or not, or a registered but
    # exported one both take the name
    ctx.pool_exists = bool(
        context.call_sync2(context.s.zpool.query_impl, ZpoolQuery(pool_names=[name]))
        or context.call_sync2(context.s.zpool.query, ZpoolQuery(pool_names=[name]))
    )
    collect(verrors, check_pool_absent, data, ctx)
    collect(verrors, check_layout, data, ctx)

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
    verrors.check()

    disks, vdevs = convert_topology_to_vdevs(data.topology)
    verrors.add_child(
        SCHEMA,
        context.middleware.call_sync("disk.check_disks_availability", list(disks), data.allow_duplicate_serials),
    )
    verrors.check()

    ctx.disk_sizes = {i.name: i.size_bytes for i in context.middleware.call_sync("disk.get_disks") if i.name in disks}
    collect(verrors, check_spare_sizes, data, ctx)
    verrors.check()

    if data.all_sed:
        context.middleware.call_sync("disk.setup_sed_disks_for_pool", list(disks), f"{SCHEMA}.topology", True)

    # WARNING: Fenced MUST NOT start (or reload) until SED provisioning above
    # has completed. Its persistent reservation register/acquire burst racing
    # the TCG Security Send/Receive session corrupts controller state on some
    # SED drive firmware (observed on TCG Ruby 1.0 NVMe). SED setup writes no
    # user data, so fencing is only required before disks are written to
    # (resize, format, zpool create), all of which happen below.
    if context.middleware.call_sync("failover.licensed"):
        _start_fenced(context)

    if osize := context.call_sync2(context.s.system.advanced.config).overprovision:
        if log_disks := {disk: osize for vdev in data.topology.log for disk in vdev.disks}:
            # will log errors if there are any so it won't crash here (this matches CORE behavior)
            context.middleware.call_sync("disk.resize", log_disks, True).wait_sync()

    context.middleware.call_sync("pool.format_disks", job, disks, 0, 30)

    pool_properties = properties_to_zfs(ctx.properties)
    os.makedirs(os.path.dirname(ctx.properties.cachefile or ""), exist_ok=True)

    pool_id: int | None = None
    created = False
    try:
        job.set_progress(90, "Creating ZFS Pool")
        context.call_sync2(
            context.s.zpool.create_impl,
            name,
            vdevs,
            pool_properties,
            properties_to_zfs(ctx.filesystem_properties),
            data.force_topology,
        )
        created = True

        job.set_progress(95, "Setting pool options")
        guid = context.call_sync2(context.s.zpool.query_impl, ZpoolQuery(pool_names=[name]))[0]["guid"]

        # Inherit mountpoint after create because we set mountpoint on creation
        # making it a "local" source.
        context.middleware.call_sync("pool.dataset.update_impl", UpdateImplArgs(name=name, iprops={"mountpoint"}))
        context.call_sync2(context.s.zfs.resource.mount, name)

        pool_id = context.middleware.call_sync(
            "datastore.insert",
            "storage.volume",
            {"name": name, "guid": str(guid), "all_sed": data.all_sed},
            {"prefix": "vol_"},
        )
        context.middleware.call_sync("datastore.insert", "storage.scrub", {"volume": pool_id}, {"prefix": "scrub_"})
    except Exception as e:
        # Something went wrong, roll back and destroy the pool.
        context.logger.debug("Pool %r failed to create with topology %r", name, data.topology.model_dump())
        if created:
            try:
                context.middleware.call_sync("zfs.pool.delete", name)
            except Exception:
                context.logger.warning("Failed to delete pool on zpool.create rollback", exc_info=True)
        if pool_id:
            context.middleware.call_sync("datastore.delete", "storage.volume", pool_id)
        if isinstance(e, ZpoolException):
            raise CallError(str(e), e.errno) from e
        raise

    # There is really no point in waiting for all these services to reload so do
    # them in the background.
    context.middleware.call_sync("pool.restart_services", background=True)

    pool: dict[str, Any] = context.middleware.call_sync("pool.get_instance", pool_id)
    context.middleware.call_hook_sync("pool.post_create", pool=pool)
    context.middleware.call_hook_sync("pool.post_create_or_update", pool=pool)
    context.middleware.send_event("pool.query", "ADDED", id=pool_id, fields=pool)
    context.call_sync2(context.s.zpool.send_change_event, name, "ADDED")
    return context.call_sync2(
        context.s.zpool.query,
        ZpoolQuery(pool_names=[name], topology=True, properties=list(pool_properties)),
    )[0]
