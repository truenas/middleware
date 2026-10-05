from __future__ import annotations

import errno
import os
from typing import TYPE_CHECKING, Any

import truenas_pylibzfs
from truenas_pylicensed.features import LicenseFeature

from middlewared.api.current import (
    ZFSResourceCreateArgsData,
    ZFSResourceEntry,
    ZFSResourceQuery,
)
from middlewared.service_exception import CallError, ValidationError

from .create_impl import ZFS_INVALID_INPUT_ERRORS, create_ancestors, create_leaf
from .create_rules import (
    DEFAULT_VOLBLOCKSIZE,
    CreateContext,
    _nearest_ancestor_entry,
    ancestor_chain,
    apply_draid_recordsize,
    apply_draid_volblocksize,
    apply_tier_snap,
    apply_volume_ssb_pin,
    check_acl_combination,
    check_dedup_entitlement,
    check_dedup_tiering,
    check_encryption,
    check_encryption_ancestry,
    check_force_size,
    check_names_valid_for_type,
    check_new_ancestor_names,
    check_parent_is_filesystem,
    check_parent_not_readonly,
    check_parent_unlocked,
    check_path_shape,
    check_refreservation_auto,
    check_share_type,
    check_volume_capacity,
    check_volume_has_volsize,
    resolve_create_request,
)
from .exceptions import ZFSPathAlreadyExistsException, ZFSPathNotFoundException
from .mount_unmount_impl import mount_impl
from .rules_common import (
    SPA_MAXBLOCKSIZE,
    reject_bad_block_size,
    reject_bad_recordsize,
    reject_bad_user_property_names,
    reject_bad_user_property_values,
    reject_ssb_out_of_range,
    reject_tier_managed_ssb,
    reject_volsize_not_multiple,
)
from .share_presets import apply_share_acl, share_acl, share_mountpoint
from .utils import has_internal_path, reject_protected_path

if TYPE_CHECKING:
    from middlewared.service import ServiceContext

SCHEMA = "zfs.resource.create"


def _record_key(context: ServiceContext, path: str, encrypt: dict[str, Any]) -> None:
    # Hex keys are stored so unlock, export and KMIP work; passphrases deliberately are not.
    context.call_sync2(context.s.zfs.resource.encryption.store_key, path, encrypt["key"], encrypt["keyformat"])
    context.middleware.call_hook_sync(
        "dataset.post_create",
        {
            "encrypted": True,
            "name": path,
            "encryption_key": encrypt["key"],
            "key_format": encrypt["keyformat"],
        },
    )


def create_impl(context: ServiceContext, tls: Any, data: ZFSResourceCreateArgsData) -> dict[str, Any]:
    path = data.path
    check_path_shape(data)
    reject_protected_path(SCHEMA, path, data.bypass)

    properties, encrypt = resolve_create_request(data)
    ctx = CreateContext(properties=properties, encrypt=encrypt)

    check_share_type(data)
    check_force_size(data)
    check_names_valid_for_type(data)
    check_refreservation_auto(data)

    if data.type == "FILESYSTEM" or properties.special_small_blocks is not None or properties.dedup is not None:
        ctx.tier_enabled = context.call_sync2(context.s.zfs.tier.config).enabled

    # any value other than off (on, verify, a checksum) enables dedup.
    # The entitlement is settled before anything is gathered from the
    # pool so an unlicensed request fails without further work.
    dedup_requested = str(properties.dedup or "off").lower() != "off"
    if dedup_requested:
        ctx.dedup_entitlement = context.call_sync2(context.s.truenas.entitlements.check, LicenseFeature.DEDUP)
        check_dedup_entitlement(data, ctx)

    ancestor_props = ["readonly", "mountpoint", "encryption"]
    if data.type == "VOLUME":
        ancestor_props.extend(["available", "special_small_blocks"])
    else:
        ancestor_props.extend(["acltype", "aclmode", "mounted"])
        if ctx.tier_enabled and data.properties.special_small_blocks is None:
            ancestor_props.extend(["special_small_blocks", "recordsize"])
    ctx.ancestors = {
        rv["name"]: rv
        for rv in context.call_sync2(
            context.s.zfs.resource.list_impl,
            ZFSResourceQuery(paths=[path, *ancestor_chain(path)], properties=ancestor_props),
        )
    }
    if ctx.ancestors.pop(path, None) is not None:
        raise ZFSPathAlreadyExistsException(path)
    check_new_ancestor_names(data, ctx)
    check_parent_is_filesystem(data, ctx)

    check_parent_unlocked(data, ctx)
    check_parent_not_readonly(data, ctx)
    reject_bad_user_property_names(f"{SCHEMA}.user_properties", data.user_properties)
    reject_bad_user_property_values(f"{SCHEMA}.user_properties", data.user_properties)
    if data.properties.special_small_blocks is not None:
        if ctx.tier_enabled:
            reject_tier_managed_ssb(f"{SCHEMA}.properties.special_small_blocks")
        else:
            reject_ssb_out_of_range(f"{SCHEMA}.properties.special_small_blocks", data.properties.special_small_blocks)

    if data.type == "VOLUME":
        check_volume_has_volsize(data, ctx)
        if properties.volblocksize is not None:
            reject_bad_block_size(
                f"{SCHEMA}.properties.volblocksize", "volblocksize", properties.volblocksize, SPA_MAXBLOCKSIZE
            )
        apply_draid_volblocksize(context, data, ctx)
        if properties.special_small_blocks is None:
            apply_volume_ssb_pin(data, ctx)
        if properties.volsize is not None:
            reject_volsize_not_multiple(
                f"{SCHEMA}.properties.volsize",
                path,
                properties.volsize,
                properties.volblocksize or DEFAULT_VOLBLOCKSIZE,
            )
        check_volume_capacity(data, ctx)
    else:
        if properties.recordsize is None:
            if not data.bypass:
                apply_draid_recordsize(context, data, ctx)
        else:
            reject_bad_recordsize(
                f"{SCHEMA}.properties.recordsize",
                context,
                path.split("/")[0],
                properties.recordsize,
                draid_floor=not data.bypass,
            )
        if ctx.tier_enabled and properties.special_small_blocks is None and not data.bypass:
            apply_tier_snap(data, ctx)
        if ctx.tier_enabled and dedup_requested:
            check_dedup_tiering(context, data, ctx)
        check_acl_combination(data, ctx)

    check_encryption_ancestry(data, ctx)
    if data.encryption:
        check_encryption(data, ctx)

    parent = _nearest_ancestor_entry(data, ctx)
    inherited = parent["properties"]["mountpoint"]["raw"] if parent else None
    mount_ancestors = inherited not in ("none", "legacy")
    mount_leaf = (
        data.type == "FILESYSTEM"
        and properties.canmount in (None, "on")
        and (properties.mountpoint or inherited) not in ("none", "legacy")
    )
    if (
        mount_leaf
        and not data.bypass
        and properties.mountpoint is None
        and os.path.lexists(mp := share_mountpoint(path, parent) if parent else os.path.join("/mnt", path))
    ):
        raise ValidationError(SCHEMA, f"Path {mp!r} already exists.", errno.EEXIST)

    acl = None
    if data.share_type and parent is not None:
        share_mp = share_mountpoint(path, parent)
        acl = share_acl(context, data.share_type, share_mp, parent)
        if acl is not None and properties.readonly == "on":
            raise ValidationError(
                f"{SCHEMA}.properties.readonly",
                f"share_type {data.share_type!r} writes an ACL to {path!r}, "
                "which a readonly filesystem refuses. Leave 'readonly' unset.",
                errno.EINVAL,
            )

    crypto = None
    if encrypt:
        try:
            crypto = tls.lzh.resource_cryptography_config(
                keyformat=encrypt["keyformat"],
                key=encrypt["key"],
                pbkdf2iters=encrypt.get("pbkdf2iters"),
            )
        except (TypeError, ValueError) as e:
            raise ValidationError(
                f"{SCHEMA}.encryption", f"Invalid encryption configuration: {e}", errno.EINVAL
            ) from None

    props = dict()
    for k, v in properties:
        if v is not None:
            props[k] = v
    try:
        missing = []
        if data.create_ancestors:
            for a in reversed(ancestor_chain(path)):
                if "/" in a and a not in ctx.ancestors:
                    missing.append(a)
        created = create_ancestors(tls, missing, mount_ancestors)
        create_leaf(tls, path, data.type, props, data.user_properties, crypto)
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

    mount_error = None
    if mount_leaf:
        try:
            mount_impl(tls, path, None, False, None, False, False)
        except Exception as e:
            mount_error = e
    if encrypt:
        _record_key(context, path, encrypt)

    requested = False
    for _, v in data.properties:
        if v is not None:
            requested = True
            break
    report_props = list(props) if requested else []
    if encrypt:
        report_props.append("encryption")
    rows = context.call_sync2(
        context.s.zfs.resource.list_impl,
        ZFSResourceQuery(
            paths=[*created, path],
            properties=report_props,
            get_user_properties=bool(data.user_properties),
        ),
    )
    entry = None
    for row in rows:
        if not has_internal_path(row["name"]):
            context.middleware.send_event("zfs.resource.list", "ADDED", id=row["name"], fields=row)
        if row["name"] == path:
            entry = row
    if entry is None:
        raise CallError(f"{path!r} was created but could not be read back.", errno.ENOENT)

    if mount_error is not None:
        raise CallError(f"{path!r} was created but could not be mounted: {mount_error}") from mount_error
    if acl is not None:
        try:
            apply_share_acl(context, share_mp, acl)
        except Exception as e:
            raise CallError(f"{path!r} was created, but its {data.share_type!r} ACL could not be applied: {e}") from e
    return entry


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
