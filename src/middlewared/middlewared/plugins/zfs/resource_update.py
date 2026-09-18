from __future__ import annotations

import errno
from typing import TYPE_CHECKING, Any

import truenas_pylibzfs
from truenas_pylicensed.features import LicenseFeature

from middlewared.api.current import ZFSResourceEntry, ZFSResourceQuery
from middlewared.service_exception import CallError, ValidationError

from .create_impl import ZFS_INVALID_INPUT_ERRORS
from .update_rules import (
    UpdateContext,
    check_acl_combination,
    check_dedup_entitlement,
    check_dedup_tiering,
    check_has_work,
    check_inherit_names,
    check_path_shape,
    check_resource_exists,
    check_set_inherit_conflict,
    check_tier_managed_ssb,
    check_user_property_names,
    check_volsize_not_shrunk,
    resolve_update_request,
)
from .utils import reject_protected_path

if TYPE_CHECKING:
    from collections.abc import Iterable

    from middlewared.api.current import ZFSResourceUpdateArgsData
    from middlewared.service import ServiceContext

SCHEMA = "zfs.resource.update"


def update_impl(
    tls: Any,
    path: str,
    properties: dict[str, Any] | None = None,
    user_properties: dict[str, str] | None = None,
    inherit: Iterable[str] | None = None,
) -> None:
    ds = tls.lzh.open_resource(name=path)
    if properties:
        ds.set_properties(properties=properties)
    if user_properties:
        ds.set_user_properties(user_properties=user_properties)
    for name in inherit or ():
        ds.inherit_property(property=name)


def update(context: ServiceContext, data: ZFSResourceUpdateArgsData) -> ZFSResourceEntry:
    path = data.path
    properties, inherit = resolve_update_request(data)
    ctx = UpdateContext(properties=properties, inherit=inherit)

    check_path_shape(data, ctx)
    reject_protected_path(SCHEMA, path)
    check_has_work(data, ctx)
    check_set_inherit_conflict(data, ctx)
    check_inherit_names(data, ctx)
    check_user_property_names(data, ctx)

    ctx.tier_enabled = context.call_sync2(context.s.zfs.tier.config).enabled
    if ctx.tier_enabled:
        check_tier_managed_ssb(data, ctx)

    # any value other than off (on, verify, a checksum) enables dedup.
    # The entitlement is settled before the resource is read so an
    # unlicensed request fails without further work.
    dedup_requested = str(properties.dedup or "off").lower() != "off"
    if dedup_requested:
        ctx.dedup_entitlement = context.call_sync2(context.s.truenas.entitlements.check, LicenseFeature.DEDUP)
        check_dedup_entitlement(data, ctx)

    # one read serves existence, the type and every rule below. Only the
    # properties those rules read are requested.
    acl_requested = properties.acltype is not None or properties.aclmode is not None
    wanted = []
    if properties.volsize is not None:
        wanted.append("volsize")
    if acl_requested:
        wanted.extend(["acltype", "aclmode"])
    if dedup_requested and ctx.tier_enabled and properties.special_small_blocks is None:
        wanted.append("special_small_blocks")
    rows = context.call_sync2(
        context.s.zfs.resource.query_impl,
        ZFSResourceQuery(paths=[path], properties=wanted or None),
    )
    ctx.current = rows[0] if rows else None
    check_resource_exists(data, ctx)
    # narrow the optional type for mypy. check_resource_exists raised otherwise
    assert ctx.current is not None

    if ctx.current["type"] == "VOLUME":
        if properties.volsize is not None:
            check_volsize_not_shrunk(data, ctx)
    else:
        if acl_requested:
            check_acl_combination(data, ctx)
        if dedup_requested and ctx.tier_enabled:
            check_dedup_tiering(context, data, ctx)

    props = properties.model_dump(exclude_none=True)
    try:
        context.call_sync2(
            context.s.zfs.resource.update_impl,
            path,
            properties=props,
            user_properties=data.user_properties,
            inherit=sorted(inherit),
        )
    except truenas_pylibzfs.ZFSException as e:
        if e.code == truenas_pylibzfs.ZFSError.EZFS_NOENT:
            raise ValidationError(SCHEMA, f"{path!r} does not exist.", errno.ENOENT)
        elif e.code in ZFS_INVALID_INPUT_ERRORS:
            raise ValidationError(SCHEMA, str(e), errno.EINVAL)
        raise CallError(f"Failed to update {path!r}: {e}")
    except ValueError as e:
        raise ValidationError(SCHEMA, str(e), errno.EINVAL)

    touched_user = bool(data.user_properties) or any(":" in name for name in inherit)
    return ZFSResourceEntry(
        **context.call_sync2(
            context.s.zfs.resource.query_impl,
            ZFSResourceQuery(
                paths=[path],
                properties=list(props) + [name for name in sorted(inherit) if ":" not in name],
                get_user_properties=touched_user,
            ),
        )[0]
    )
