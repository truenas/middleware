from __future__ import annotations

import errno
from typing import TYPE_CHECKING, Any

import truenas_pylibzfs
from truenas_pylicensed.features import LicenseFeature

from middlewared.api.current import (
    ZFSResourceCreateArgsData,
    ZFSResourceEntry,
    ZFSResourceQuery,
)
from middlewared.service_exception import CallError, ValidationError

from .create_impl import ZFS_INVALID_INPUT_ERRORS
from .create_impl import create_impl as _raw_create
from .create_rules import (
    CreateContext,
    ancestor_chain,
    apply_draid_recordsize,
    apply_draid_volblocksize,
    apply_tier_snap,
    apply_volume_ssb_pin,
    check_acl_combination,
    check_dedup_entitlement,
    check_dedup_tiering,
    check_encryption,
    check_name_valid,
    check_parent_is_filesystem,
    check_parent_not_readonly,
    check_path_shape,
    check_tier_managed_ssb,
    check_user_property_names,
    check_volume_capacity,
    check_volume_has_volsize,
    resolve_create_request,
)
from .exceptions import ZFSPathAlreadyExistsException, ZFSPathNotFoundException
from .utils import reject_protected_path

if TYPE_CHECKING:
    from middlewared.service import ServiceContext

SCHEMA = "zfs.resource.create"


def create_impl(context: ServiceContext, tls: Any, data: ZFSResourceCreateArgsData) -> dict[str, Any]:
    path = data.path
    properties, encrypt = resolve_create_request(data)
    ctx = CreateContext(properties=properties, encrypt=encrypt)

    check_path_shape(data, ctx)
    reject_protected_path(SCHEMA, data.path, data.bypass)
    check_name_valid(data, ctx)
    check_user_property_names(data, ctx)

    ctx.tier_enabled = context.call_sync2(context.s.zfs.tier.config).enabled

    # any value other than off (on, verify, a checksum) enables dedup.
    # The entitlement is settled before anything is gathered from the
    # pool so an unlicensed request fails without further work.
    dedup_requested = str(properties.dedup or "off").lower() != "off"
    if dedup_requested:
        ctx.dedup_entitlement = context.call_sync2(context.s.truenas.entitlements.check, LicenseFeature.DEDUP)
        check_dedup_entitlement(data, ctx)

    # one query serves the readonly, tier, acl, capacity and encryption
    # rules. Only the properties the rules below will read are requested.
    ancestor_props = ["readonly"]
    if data.type == "VOLUME":
        ancestor_props.extend(["available", "special_small_blocks"])
    else:
        if properties.acltype is not None or properties.aclmode is not None:
            ancestor_props.extend(["acltype", "aclmode"])
        if ctx.tier_enabled and data.properties.special_small_blocks is None:
            ancestor_props.extend(["special_small_blocks", "recordsize"])
    if data.encryption:
        ancestor_props.append("encryption")
    ctx.ancestors = {
        rv["name"]: rv
        for rv in context.call_sync2(
            context.s.zfs.resource.query_impl,
            ZFSResourceQuery(paths=ancestor_chain(path), properties=ancestor_props),
        )
    }

    check_parent_is_filesystem(data, ctx)
    check_parent_not_readonly(data, ctx)
    if ctx.tier_enabled:
        check_tier_managed_ssb(data, ctx)

    if data.type == "VOLUME":
        check_volume_has_volsize(data, ctx)
        apply_draid_volblocksize(context, data, ctx)
        if properties.special_small_blocks is None:
            apply_volume_ssb_pin(data, ctx)
        check_volume_capacity(data, ctx)
    else:
        if properties.recordsize is None:
            apply_draid_recordsize(context, data, ctx)
        if ctx.tier_enabled and properties.special_small_blocks is None:
            apply_tier_snap(data, ctx)
        if ctx.tier_enabled and dedup_requested:
            check_dedup_tiering(context, data, ctx)
        if properties.acltype is not None or properties.aclmode is not None:
            check_acl_combination(data, ctx)

    if data.encryption:
        check_encryption(data, ctx)

    props = dict()
    for k, v in properties:
        if v is not None:
            props[k] = v
    try:
        _raw_create(tls, path, data.type, props, data.user_properties, data.create_ancestors, encrypt)
    except truenas_pylibzfs.ZFSException as e:
        if e.code in ZFS_INVALID_INPUT_ERRORS:
            raise ValidationError(SCHEMA, str(e), errno.EINVAL)
        elif e.code == truenas_pylibzfs.ZFSError.EZFS_CRYPTOFAILED:
            raise CallError(
                f"Failed to create {path!r}: the parent's encryption key is not "
                "loaded. Unlock the parent dataset and try again.",
                errno.EACCES,
            )
        raise CallError(f"Failed to create {path!r}: {e}")

    if encrypt:
        # Hex keys are stored by the system (passphrases deliberately are
        # not) so unlock/export/KMIP flows work; the post_create hook syncs
        # key material to the standby controller on HA systems. The
        # storage_encrypteddataset table remains the system of record for
        # dataset keys.
        context.middleware.call_sync(
            "pool.dataset.insert_or_update_encrypted_record",
            {"name": path, "encryption_key": encrypt["key"], "key_format": encrypt["keyformat"]},
        )
        context.middleware.call_hook_sync(
            "dataset.post_create",
            {
                "encrypted": True,
                "name": path,
                "encryption_key": encrypt["key"],
                "key_format": encrypt["keyformat"],
            },
        )

    requested = False
    for _, v in data.properties:
        if v is not None:
            requested = True
            break
    report_props = list(props) if requested else []
    if encrypt:
        report_props.append("encryption")
    return context.call_sync2(
        context.s.zfs.resource.query_impl,
        ZFSResourceQuery(
            paths=[path],
            properties=report_props,
            get_user_properties=bool(data.user_properties),
        ),
    )[0]


def create(context: ServiceContext, data: ZFSResourceCreateArgsData) -> ZFSResourceEntry:
    try:
        return ZFSResourceEntry(**context.call_sync2(context.s.zfs.resource.create_impl, data))
    except ZFSPathAlreadyExistsException as e:
        raise ValidationError(SCHEMA, e.message, errno.EEXIST)
    except ZFSPathNotFoundException as e:
        missing = e.path
        if "/" not in missing:
            msg = f"Pool {missing!r} does not exist."
        elif data.create_ancestors:
            msg = f"Parent dataset {missing!r} does not exist."
        else:
            msg = f"Parent dataset {missing!r} does not exist. Set create_ancestors to create it."
        raise ValidationError(SCHEMA, msg, errno.ENOENT)
    except ValueError as e:
        raise ValidationError(SCHEMA, str(e), errno.EINVAL)
