from __future__ import annotations

from collections.abc import Awaitable, Callable

from truenas_pylicensed.features import LicenseFeature

from middlewared.api.current import QueryOptions, ZFSResourceQuery
from middlewared.service import ServiceContext
from middlewared.utils.entitlements import DerivedEntitlement
from middlewared.utils.smb import SearchProtocol


async def _apps(context: ServiceContext) -> bool:
    return bool((await context.call2(context.s.docker.config)).pool)


async def _catalog_enterprise_train(context: ServiceContext) -> bool:
    return "enterprise" in (await context.call2(context.s.catalog.config)).preferred_trains


async def _containers(context: ServiceContext) -> bool:
    return bool(await context.call2(context.s.container.query, [], QueryOptions(count=True)))


async def _dedup(context: ServiceContext) -> bool:
    for resource in await context.call2(
        context.s.zfs.resource.query_impl,
        ZFSResourceQuery(properties=["dedup"], get_children=True),
    ):
        dedup = (resource["properties"] or {}).get("dedup") or {}
        # A dataset part-way through a `zfs receive` reports no value at all, which is not evidence
        # that anybody asked for deduplication.
        if dedup.get("raw") not in (None, "off"):
            return True

    return False


async def _directory_services_auth(context: ServiceContext) -> bool:
    return bool((await context.middleware.call("system.general.config"))["ds_auth"])


async def _fibrechannel(context: ServiceContext) -> bool:
    return bool(await context.middleware.call("iscsi.target.query", [["mode", "!=", "ISCSI"]], {"count": True}))


async def _ha(context: ServiceContext) -> bool:
    return bool(await context.middleware.call("system.is_ha_capable"))


async def _kmip(context: ServiceContext) -> bool:
    return bool((await context.call2(context.s.kmip.config)).server)


async def _mission_critical(context: ServiceContext) -> bool:
    return (await context.call2(context.s.update.config_safe)).profile == "MISSION_CRITICAL"


async def _network_fec(context: ServiceContext) -> bool:
    return any(
        interface.get("fec_mode") not in (None, "OFF")
        for interface in await context.middleware.call("interface.query", [["type", "=", "PHYSICAL"]])
    )


async def _nfs_snapshot(context: ServiceContext) -> bool:
    return bool(await context.middleware.call("sharing.nfs.query", [["expose_snapshots", "=", True]], {"count": True}))


async def _nvmeof_spdk(context: ServiceContext) -> bool:
    return (await context.middleware.call("nvmet.global.config"))["kernel"] is False


async def _proactive_support(context: ServiceContext) -> bool:
    config = await context.call2(context.s.support.config)
    return bool(config.enabled and config.email)


async def _rdma(context: ServiceContext) -> bool:
    if (await context.middleware.call("nvmet.global.config"))["rdma"]:
        return True

    if (await context.middleware.call("iscsi.global.config"))["iser"]:
        return True

    if await context.middleware.call("nvmet.port.query", [["addr_trtype", "=", "RDMA"]], {"count": True}):
        return True

    # `nfs.config` masks the stored flag with `rdma.capable_protocols`, which is an entitlement check.
    nfs = await context.middleware.call("datastore.query", "services.nfs", [], {"get": True, "prefix": "nfs_srv_"})
    return bool(nfs["rdma"])


async def _s3_audit(context: ServiceContext) -> bool:
    config = await context.call2(context.s.s3.config)
    if config.default_audit or config.default_audit_overflow != "DROP":
        return True

    return bool(
        await context.call2(
            context.s.sharing.s3.query,
            [["OR", [["audit", "!=", None], ["audit_overflow", "!=", None]]]],
            QueryOptions(count=True),
        )
    )


async def _s3_versioning(context: ServiceContext) -> bool:
    return bool(
        await context.call2(context.s.sharing.s3.query, [["versioning", "!=", "OFF"]], QueryOptions(count=True))
    )


async def _sed(context: ServiceContext) -> bool:
    if await context.call2(context.s.system.advanced.sed_global_password_is_set):
        return True

    # A KMIP-managed disk holds its password on the KMIP server, so it matches on `kmip_uid` alone.
    # Both fields are stripped from a disk unless `passwords` is asked for, and the filter then
    # cannot match at all.
    return bool(
        await context.middleware.call(
            "disk.query",
            [["OR", [["passwd", "!=", ""], ["kmip_uid", "!=", None]]]],
            {"count": True, "extra": {"passwords": True}},
        )
    )


async def _smb_veeam(context: ServiceContext) -> bool:
    return bool(
        await context.middleware.call(
            "sharing.smb.query", [["purpose", "=", "VEEAM_REPOSITORY_SHARE"]], {"count": True}
        )
    )


async def _stig(context: ServiceContext) -> bool:
    config = await context.call2(context.s.system.security.config)
    return bool(
        config.enable_fips
        or config.enable_gpos_stig
        or config.min_password_age
        or config.max_password_age
        or config.password_complexity_ruleset
        or config.min_password_length
        or config.password_history_length
    )


async def _truesearch(context: ServiceContext) -> bool:
    if SearchProtocol.SPOTLIGHT in (await context.middleware.call("smb.config"))["search_protocols"]:
        return True

    return bool((await context.call2(context.s.webshare.config)).search)


async def _vms(context: ServiceContext) -> bool:
    return bool(await context.call2(context.s.vm.query, [], QueryOptions(count=True)))


async def _webshare(context: ServiceContext) -> bool:
    return bool(await context.call2(context.s.sharing.webshare.query, [], QueryOptions(count=True)))


async def _zfstier(context: ServiceContext) -> bool:
    return bool((await context.call2(context.s.zfs.tier.config)).enabled)


PROBES: dict[str, Callable[[ServiceContext], Awaitable[bool]] | None] = {
    LicenseFeature.APPS: _apps,
    LicenseFeature.CATALOG_ENTERPRISE_TRAIN: _catalog_enterprise_train,
    LicenseFeature.CONTAINERS: _containers,
    LicenseFeature.DEDUP: _dedup,
    LicenseFeature.DIRECTORY_SERVICES_AUTH: _directory_services_auth,
    LicenseFeature.FIBRECHANNEL: _fibrechannel,
    LicenseFeature.HA: _ha,
    LicenseFeature.KMIP: _kmip,
    LicenseFeature.MISSION_CRITICAL: _mission_critical,
    LicenseFeature.NETWORK_FEC: _network_fec,
    LicenseFeature.NFS_SNAPSHOT: _nfs_snapshot,
    LicenseFeature.NVMEOF_SPDK: _nvmeof_spdk,
    LicenseFeature.RDMA: _rdma,
    LicenseFeature.S3_AUDIT: _s3_audit,
    LicenseFeature.S3_VERSIONING: _s3_versioning,
    LicenseFeature.SED: _sed,
    # The entitlement is written straight into `smb.conf`; no stored setting records it.
    LicenseFeature.SMB_FASTPATH: None,
    LicenseFeature.SMB_VEEAM: _smb_veeam,
    LicenseFeature.STIG: _stig,
    # Gates ticket submission and an alert, neither of which leaves a configuration field behind.
    LicenseFeature.SUPPORT: None,
    LicenseFeature.TRUESEARCH: _truesearch,
    LicenseFeature.VMS: _vms,
    LicenseFeature.WEBSHARE: _webshare,
    LicenseFeature.ZFSTIER: _zfstier,
    DerivedEntitlement.PROACTIVE_SUPPORT: _proactive_support,
}
