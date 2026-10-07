"""Validation rules for zfs.resource.create."""

from __future__ import annotations

import dataclasses
import errno
import pathlib
import typing

from truenas_pylibzfs import ZFSProperty

from middlewared.service_exception import ValidationError
from middlewared.utils.crypto import generate_token

from .name_utils import last_component_space_padded
from .property_management import PROPERTY_TEMPLATES
from .rules_common import (
    apply_acl_defaults,
    reject_bad_acl_combination,
    reject_dedup_on_special_vdev,
    reject_force_size_on_filesystem,
    reject_insufficient_headroom,
    reject_unentitled_dedup,
)
from .share_presets import SHARE_PRESETS
from .utils import get_encryption_info, pool_is_draid

if typing.TYPE_CHECKING:
    from middlewared.api.current import EntitlementEntry, ZFSResourceCreateArgsData, ZFSResourceCreateProperties
    from middlewared.service import ServiceContext

__all__ = (
    "DEFAULT_VOLBLOCKSIZE",
    "CreateContext",
    "ancestor_chain",
    "apply_draid_recordsize",
    "apply_draid_volblocksize",
    "apply_tier_snap",
    "apply_volume_ssb_pin",
    "check_acl_combination",
    "check_dedup_entitlement",
    "check_dedup_tiering",
    "check_encryption",
    "check_encryption_ancestry",
    "check_force_size",
    "check_names_valid_for_type",
    "check_new_ancestor_names",
    "check_parent_is_filesystem",
    "check_parent_not_readonly",
    "check_parent_unlocked",
    "check_path_shape",
    "check_refreservation_auto",
    "check_share_type",
    "check_volume_capacity",
    "check_volume_has_volsize",
    "resolve_create_request",
)

SCHEMA = "zfs.resource.create"
DEFAULT_VOLBLOCKSIZE = 16384


@dataclasses.dataclass(slots=True, kw_only=True)
class CreateContext:
    """Resolved values and gathered facts that the rules read."""

    properties: ZFSResourceCreateProperties
    """Effective zfs properties after creation defaults are applied. A
    field left as None is not sent to ZFS."""
    encrypt: dict[str, typing.Any] | None
    """Resolved encryption config when a new encryption root is requested."""
    ancestors: dict[str, typing.Any] = dataclasses.field(default_factory=dict)
    """Existing ancestors of the new resource keyed by name with the
    properties the active rules read. Populated by the service. A missing
    ancestor has no entry."""
    tier_enabled: bool = False
    """Whether ZFS tiering is enabled on this system."""
    dedup_entitlement: EntitlementEntry | None = None
    """The DEDUP entitlement decision for this system. Populated by the
    service only when the request enables deduplication."""


def ancestor_chain(path: str) -> list[str]:
    """Return the ancestors of `path` ordered nearest first."""
    return [i.as_posix() for i in pathlib.PurePosixPath(path).parents if i.as_posix() != "."]


def _secret_value(value: typing.Any) -> str | None:
    # an unset Secret field holds Secret(None), not None
    return value.get_secret_value() if value else None


def _nearest_ancestor_entry(data: ZFSResourceCreateArgsData, ctx: CreateContext) -> typing.Any | None:
    """Return the gathered entry of the nearest existing ancestor."""
    for ancestor in ancestor_chain(data.path):
        rv = ctx.ancestors.get(ancestor)
        if rv is not None:
            return rv
    return None


def apply_draid_recordsize(context: ServiceContext, data: ZFSResourceCreateArgsData, ctx: CreateContext) -> None:
    """Default a filesystem on a dRAID pool to a 1M recordsize, since small blocks perform poorly on dRAID vdevs."""
    if pool_is_draid(context, data.path.split("/")[0]):
        ctx.properties.recordsize = 1024 * 1024


def apply_draid_volblocksize(context: ServiceContext, data: ZFSResourceCreateArgsData, ctx: CreateContext) -> None:
    """Default a dRAID volume to a 128K volblocksize and refuse one below 32K; small blocks perform poorly on dRAID
    vdevs."""
    if not pool_is_draid(context, data.path.split("/")[0]):
        return
    if ctx.properties.volblocksize is None:
        ctx.properties.volblocksize = 128 * 1024
    elif ctx.properties.volblocksize < 32768:
        raise ValidationError(
            f"{SCHEMA}.properties.volblocksize",
            "Volume block size must be greater than or equal to 32K for dRAID pools.",
            errno.EINVAL,
        )


def resolve_create_request(
    data: ZFSResourceCreateArgsData,
) -> tuple[ZFSResourceCreateProperties, dict[str, typing.Any] | None]:
    """Apply creation defaults and resolve the requested encryption.

    Returns a copy of the requested properties with the creation
    defaults applied and the resolved encryption config. The encryption
    config is None when no encryption root is requested or when the
    request provides no key material at all. A zero quota or refquota is not
    sent at all since a new resource has no limit by default and ZFS
    refuses a zero for either.
    """
    properties = data.properties.model_copy()
    if properties.quota == 0:
        properties.quota = None
    if properties.refquota == 0:
        properties.refquota = None
    if data.type == "VOLUME":
        if properties.volsize is not None and properties.refreservation is None:
            # thick provision like `zfs create -V`: auto reserves the volsize plus metadata and
            # raidz/draid overhead, and libzfs grows it along with the volsize
            properties.refreservation = "auto"
    else:
        if data.share_type is not None:
            for name, value in SHARE_PRESETS[data.share_type].items():
                if getattr(properties, name) is None:
                    setattr(properties, name, value)
        if properties.xattr is None:
            # its important to set this as "sa" for performance reasons
            properties.xattr = "sa"
        if not data.bypass:
            apply_acl_defaults(properties)

    encrypt = None
    if data.encryption:
        passphrase = _secret_value(data.encryption.passphrase)
        key = _secret_value(data.encryption.key)
        if passphrase is not None:
            encrypt = {
                "keyformat": "passphrase",
                "key": passphrase,
                "pbkdf2iters": data.encryption.pbkdf2iters,
            }
        elif data.encryption.generate_key:
            encrypt = {"keyformat": "hex", "key": generate_token(32)}
        elif key is not None:
            encrypt = {"keyformat": "hex", "key": key}
    return properties, encrypt


def check_path_shape(data: ZFSResourceCreateArgsData) -> None:
    if "/" not in data.path:
        raise ValidationError(
            SCHEMA,
            "Creating a root filesystem (zpool) is not allowed.",
            errno.EINVAL,
        )
    elif "%" in data.path:
        raise ValidationError(SCHEMA, f"{data.path!r} may not contain '%'.", errno.EINVAL)
    elif last_component_space_padded(data.path):
        raise ValidationError(SCHEMA, "Resource names may not begin or end with a space.", errno.EINVAL)


def check_new_ancestor_names(data: ZFSResourceCreateArgsData, ctx: CreateContext) -> None:
    """An ancestor that create_ancestors would create may not begin or end
    with a space. Existing ancestors keep whatever name they have."""
    if not data.create_ancestors:
        return
    for ancestor in ancestor_chain(data.path):
        if "/" in ancestor and ancestor not in ctx.ancestors and last_component_space_padded(ancestor):
            raise ValidationError(
                SCHEMA,
                f"Cannot create {ancestor!r}: resource names may not begin or end with a space.",
                errno.EINVAL,
            )


def check_volume_has_volsize(data: ZFSResourceCreateArgsData, ctx: CreateContext) -> None:
    """A volume cannot be created without a size."""
    if ctx.properties.volsize is None:
        raise ValidationError(
            f"{SCHEMA}.properties.volsize",
            "'volsize' is required when creating a VOLUME.",
            errno.EINVAL,
        )


def check_parent_is_filesystem(data: ZFSResourceCreateArgsData, ctx: CreateContext) -> None:
    """The nearest existing ancestor must be a filesystem.

    Only a filesystem can hold children. The rules that follow read
    filesystem-only properties from that ancestor, so a volume is refused here
    before they run.
    """
    parent = _nearest_ancestor_entry(data, ctx)
    if parent is not None and parent["type"] != "FILESYSTEM":
        raise ValidationError(
            SCHEMA,
            f"{parent['name']!r} is a volume and cannot hold {data.path!r}.",
            errno.EINVAL,
        )


def check_parent_not_readonly(data: ZFSResourceCreateArgsData, ctx: CreateContext) -> None:
    """The nearest existing ancestor must not be readonly.

    ZFS allows creating beneath a readonly parent but the new filesystem
    then fails to mount and a new volume fails on first write. Refuse up
    front with a clear message instead.
    """
    # nothing is mounted inside the readonly parent
    if ctx.properties.readonly == "off" and ctx.properties.mountpoint in ("legacy", "none"):
        return
    for ancestor in ancestor_chain(data.path):
        rv = ctx.ancestors.get(ancestor)
        if rv is None:
            # a missing ancestor is created (or rejected) later
            continue
        if rv["properties"]["readonly"]["raw"] == "on":
            raise ValidationError(
                SCHEMA,
                f"Turn off readonly mode on {ancestor!r} to create {data.path!r}.",
                errno.EINVAL,
            )
        return


def apply_tier_snap(data: ZFSResourceCreateArgsData, ctx: CreateContext) -> None:
    """Pin a new filesystem to its parent's effective tier.

    That is 16M when the parent places data on the special vdev
    (PERFORMANCE) and 0 otherwise (REGULAR). This keeps the tier manager
    the owner of placement instead of floating inheritance.
    """
    parent = _nearest_ancestor_entry(data, ctx)
    if parent is None:
        return
    parent_ssb = parent["properties"]["special_small_blocks"]["value"] or 0
    parent_rs = parent["properties"]["recordsize"]["value"] or 0
    performance = parent_rs > 0 and parent_ssb >= parent_rs
    ctx.properties.special_small_blocks = 16 * 1024 * 1024 if performance else 0


def apply_volume_ssb_pin(data: ZFSResourceCreateArgsData, ctx: CreateContext) -> None:
    """Pin special_small_blocks to 0 for a volume below the threshold.

    A volume whose blocks are smaller than the parent's threshold would
    land entirely on the special vdev so it is pinned to 0 regardless of
    tiering.
    """
    parent = _nearest_ancestor_entry(data, ctx)
    if parent is None:
        return
    parent_ssb = parent["properties"]["special_small_blocks"]["value"] or 0
    volblocksize = ctx.properties.volblocksize or DEFAULT_VOLBLOCKSIZE
    if parent_ssb and volblocksize < parent_ssb:
        ctx.properties.special_small_blocks = 0


def check_dedup_entitlement(data: ZFSResourceCreateArgsData, ctx: CreateContext) -> None:
    """Deduplication may only be enabled on a system entitled to it."""
    assert ctx.dedup_entitlement is not None

    reject_unentitled_dedup(f"{SCHEMA}.properties.dedup", ctx.dedup_entitlement)


def check_dedup_tiering(context: ServiceContext, data: ZFSResourceCreateArgsData, ctx: CreateContext) -> None:
    """Deduplication may not be enabled on a PERFORMANCE tier filesystem.

    The effective special_small_blocks is the requested value or the one
    inherited from the nearest existing ancestor.
    """
    ssb = ctx.properties.special_small_blocks
    if ssb is None:
        parent = _nearest_ancestor_entry(data, ctx)
        ssb = (parent["properties"]["special_small_blocks"]["value"] or 0) if parent else 0
    reject_dedup_on_special_vdev(f"{SCHEMA}.properties.dedup", context, data.path.split("/")[0], ssb)


def _effective_value(name: str, data: ZFSResourceCreateArgsData, ctx: CreateContext) -> str | None:
    """Return the lowercased effective value of a property. That is the
    requested value or the value inherited from the nearest existing
    ancestor."""
    value = getattr(ctx.properties, name)
    if value is None:
        for ancestor in ancestor_chain(data.path):
            rv = ctx.ancestors.get(ancestor)
            if rv is not None:
                value = rv["properties"][name]["raw"]
                break
    return str(value).lower() if value is not None else None


def check_acl_combination(data: ZFSResourceCreateArgsData, ctx: CreateContext) -> None:
    """The requested acl properties must form a usable combination.

    The effective acltype and aclmode are the requested value or the
    value inherited from the nearest existing ancestor.
    """
    acltype, aclmode = _effective_value("acltype", data, ctx), _effective_value("aclmode", data, ctx)
    if ctx.properties.acltype is not None or ctx.properties.aclmode is not None:
        sent = "aclmode" if data.properties.aclmode is not None else "acltype"
        reject_bad_acl_combination(f"{SCHEMA}.properties.{sent}", acltype, aclmode)
    elif not data.bypass and acltype == "nfsv4":
        reject_bad_acl_combination(f"{SCHEMA}.properties.aclmode", acltype, aclmode)


def check_volume_capacity(data: ZFSResourceCreateArgsData, ctx: CreateContext) -> None:
    """A volume's volsize may not exceed 80% of the `available` space of the
    nearest existing ancestor, whether the volume is thick or sparse.
    `force_size` skips the check and leaves the limit to ZFS.
    """
    if ctx.properties.volsize is None or data.force_size:
        return
    if not data.create_ancestors and ancestor_chain(data.path)[0] not in ctx.ancestors:
        # creation reports the missing parent, which is the more useful error
        return
    parent = _nearest_ancestor_entry(data, ctx)
    if parent is None:
        return
    reject_insufficient_headroom(
        f"{SCHEMA}.properties.volsize", ctx.properties.volsize, parent["properties"]["available"]["value"]
    )


def check_encryption(data: ZFSResourceCreateArgsData, ctx: CreateContext) -> None:
    """Validate a request to create a new encryption root.

    Exactly one source of key material must be provided. A key encrypted
    root may not be created beneath a passphrase encrypted parent since it
    could not be unlocked while its parent is locked.
    """
    assert data.encryption is not None

    if ctx.properties.encryption is not None:
        # the internal-only property opts out of the parent's encryption. It
        # cannot be combined with a request for a new encryption root
        raise ValidationError(
            f"{SCHEMA}.encryption",
            "An encryption root cannot be requested together with the 'encryption' property.",
            errno.EINVAL,
        )

    provided = [
        name
        for name, value in (
            ("key", _secret_value(data.encryption.key)),
            ("passphrase", _secret_value(data.encryption.passphrase)),
        )
        if value is not None
    ]
    if data.encryption.generate_key:
        provided.append("generate_key")
    if len(provided) != 1 or ctx.encrypt is None:
        raise ValidationError(
            f"{SCHEMA}.encryption",
            "Exactly one of `key`, `passphrase`, or `generate_key` must be provided.",
            errno.EINVAL,
        )

    parent = _nearest_ancestor_entry(data, ctx)
    if (
        parent is not None
        and parent["properties"]["encryption"]["raw"] != "off"
        and ctx.encrypt["keyformat"] == "hex"
        and parent["properties"]["keyformat"]["raw"] == "passphrase"
    ):
        raise ValidationError(
            f"{SCHEMA}.encryption.key",
            f"{parent['name']!r} is encrypted with a passphrase; a key-encrypted "
            "child cannot be created beneath it because it could not be "
            "unlocked while its parent is locked. Use a passphrase instead.",
            errno.EINVAL,
        )


def check_encryption_ancestry(data: ZFSResourceCreateArgsData, ctx: CreateContext) -> None:
    unencrypted = None
    for ancestor in ancestor_chain(data.path):
        rv = ctx.ancestors.get(ancestor)
        if rv is None:
            continue
        if rv["properties"]["encryption"]["raw"] == "off":
            unencrypted = unencrypted or ancestor
            continue
        if unencrypted is None:
            return
        if data.encryption:
            raise ValidationError(
                f"{SCHEMA}.encryption",
                "Creating an encryption root beneath an unencrypted dataset "
                f"that is itself inside encrypted dataset {ancestor!r} is not "
                "allowed.",
                errno.EINVAL,
            )
        elif not data.bypass and ctx.properties.encryption != "off":
            raise ValidationError(
                SCHEMA,
                f"Cannot create {data.path!r} beneath unencrypted dataset {unencrypted!r}, "
                f"which is itself inside encrypted dataset {ancestor!r}.",
                errno.EINVAL,
            )
        return


def check_parent_unlocked(data: ZFSResourceCreateArgsData, ctx: CreateContext) -> None:
    if ctx.properties.encryption == "off":
        return
    parent = _nearest_ancestor_entry(data, ctx)
    if parent is not None and get_encryption_info(parent["properties"]).locked:
        raise ValidationError(SCHEMA, f"{parent['name']!r} is locked. Unlock it to create {data.path!r}.", errno.EACCES)


def check_names_valid_for_type(data: ZFSResourceCreateArgsData) -> None:
    valid = PROPERTY_TEMPLATES.vol if data.type == "VOLUME" else PROPERTY_TEMPLATES.fs
    for name, value in data.properties:
        if value is not None and ZFSProperty[name.upper()] not in valid:
            raise ValidationError(
                f"{SCHEMA}.properties.{name}", f"{name!r} is not valid for a {data.type}.", errno.EINVAL
            )


def check_refreservation_auto(data: ZFSResourceCreateArgsData) -> None:
    """ZFS only accepts refreservation=auto on a volume."""
    if data.type == "FILESYSTEM" and data.properties.refreservation == "auto":
        raise ValidationError(f"{SCHEMA}.properties.refreservation", "'auto' is only valid on volumes.", errno.EINVAL)


def check_force_size(data: ZFSResourceCreateArgsData) -> None:
    if data.force_size and data.type == "FILESYSTEM":
        reject_force_size_on_filesystem(f"{SCHEMA}.force_size")


def check_share_type(data: ZFSResourceCreateArgsData) -> None:
    st = data.share_type
    if st is None:
        return
    if data.type == "VOLUME":
        raise ValidationError(f"{SCHEMA}.share_type", "share_type applies only to a FILESYSTEM.", errno.EINVAL)
    for name, value in SHARE_PRESETS[st].items():
        sent = getattr(data.properties, name)
        if sent is not None and sent != value:
            raise ValidationError(
                f"{SCHEMA}.properties.{name}",
                f"share_type {st!r} sets {name!r} to {value!r}; leave it unset or send {value!r}.",
                errno.EINVAL,
            )
