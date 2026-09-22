"""Validation rules for zfs.resource.create.

Rules are small pure functions with a uniform signature. Each one takes
the request model, a CreateContext of resolved values and gathered facts
and the ValidationErrors to append a failed check to. Only
check_path_shape raises, since every later step assumes a pool/name
path. Rules never perform I/O. The service calls them explicitly and in order
from its create_impl so the control flow reads top to bottom in one
place. When a rule needs a new fact the service gathers it and the
context grows a field. The draid and dedup tiering functions also take a
ServiceContext since they must inspect the pool themselves.

The checks that set shares with create live in rules_common.
"""

from __future__ import annotations

import dataclasses
import errno
import os
import pathlib
import typing

import truenas_pylibzfs

from middlewared.service_exception import ValidationError
from middlewared.utils.crypto import generate_token

from .create_impl import ZFS_TYPE_MAP
from .rules_common import (
    apply_acl_defaults,
    reject_bad_acl_combination,
    reject_dedup_on_special_vdev,
    reject_insufficient_headroom,
    reject_unentitled_dedup,
)
from .utils import pool_is_draid

if typing.TYPE_CHECKING:
    from middlewared.api.current import EntitlementEntry, ZFSResourceCreateArgsData, ZFSResourceCreateProperties
    from middlewared.service import ServiceContext
    from middlewared.service_exception import ValidationErrors

__all__ = (
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
    "check_name_valid",
    "check_parent_is_filesystem",
    "check_parent_not_readonly",
    "check_path_shape",
    "check_volume_capacity",
    "check_volume_has_volsize",
    "resolve_create_request",
)

SCHEMA = "zfs.resource.create"


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
    """Default a filesystem on a dRAID pool to a 1M recordsize.

    Small blocks perform poorly on dRAID vdevs. Matches the default
    pool.dataset applies.

    The service calls this only for filesystems without an explicit
    recordsize.
    """
    if pool_is_draid(context, data.path.split("/")[0]):
        ctx.properties.recordsize = 1024 * 1024


def apply_draid_volblocksize(
    context: ServiceContext, data: ZFSResourceCreateArgsData, ctx: CreateContext, verrors: ValidationErrors
) -> None:
    """Apply the dRAID volume block size default and floor.

    Small blocks perform poorly on dRAID vdevs. A volume defaults to a
    128K volblocksize and an explicitly requested volblocksize must be
    at least 32K. These match the defaults pool.dataset applies.

    The service calls this only for volumes.
    """
    if not pool_is_draid(context, data.path.split("/")[0]):
        return
    if ctx.properties.volblocksize is None:
        ctx.properties.volblocksize = 128 * 1024
    elif ctx.properties.volblocksize < 32768:
        verrors.add(
            f"{SCHEMA}.properties",
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
    request provides no key material at all. The rules judge the request
    afterwards so nothing here raises. A zero quota or refquota is not
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
            # thick provision unless told otherwise, like `zfs create -V`.
            # NOTE the CLI sets refreservation=auto (volsize plus metadata
            # overhead) but libzfs cannot resolve "auto" through our create
            # path, so reserve the volsize itself
            properties.refreservation = properties.volsize
    else:
        if properties.xattr is None:
            # its important to set this as "sa" for performance reasons
            properties.xattr = "sa"
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


def check_path_shape(data: ZFSResourceCreateArgsData, ctx: CreateContext) -> None:
    """The path must be a relative pool/resource path and not a snapshot."""
    if os.path.isabs(data.path):
        raise ValidationError(
            SCHEMA,
            "Absolute path is invalid. Must be in form of <pool>/<resource>.",
            errno.EINVAL,
        )
    elif data.path.endswith("/"):
        raise ValidationError(SCHEMA, "Path must not end with a forward-slash.", errno.EINVAL)
    elif "@" in data.path:
        raise ValidationError(
            SCHEMA,
            "Use `zfs.resource.snapshot.create` to create snapshots.",
        )
    elif "/" not in data.path:
        raise ValidationError(
            SCHEMA,
            "Creating a root filesystem (zpool) is not allowed.",
            errno.EINVAL,
        )


def check_name_valid(data: ZFSResourceCreateArgsData, ctx: CreateContext, verrors: ValidationErrors) -> None:
    """The name must be acceptable to ZFS for the requested type and may
    not end with a space."""
    if not truenas_pylibzfs.name_is_valid(name=data.path, type=ZFS_TYPE_MAP[data.type]):
        verrors.add(SCHEMA, f"{data.path!r} is not a valid ZFS resource name.", errno.EINVAL)
    elif data.path.endswith(" "):
        # ZFS itself accepts a trailing space but it is a classic footgun
        verrors.add(SCHEMA, "Trailing spaces are not permitted in resource names.", errno.EINVAL)


def check_volume_has_volsize(data: ZFSResourceCreateArgsData, ctx: CreateContext, verrors: ValidationErrors) -> None:
    """A volume cannot be created without a size.

    The service calls this only for volumes.
    """
    if ctx.properties.volsize is None:
        verrors.add(
            f"{SCHEMA}.properties",
            "'volsize' is required when creating a VOLUME.",
            errno.EINVAL,
        )


def check_parent_is_filesystem(data: ZFSResourceCreateArgsData, ctx: CreateContext, verrors: ValidationErrors) -> None:
    """The nearest existing ancestor must be a filesystem.

    Only a filesystem can hold children. The rules that follow read
    filesystem-only properties from that ancestor, so a volume is refused here
    before they run.

    The service calls this after the ancestor entries have been gathered.
    """
    parent = _nearest_ancestor_entry(data, ctx)
    if parent is not None and parent["type"] != "FILESYSTEM":
        verrors.add(
            SCHEMA,
            f"{parent['name']!r} is a volume and cannot hold {data.path!r}.",
            errno.EINVAL,
        )


def check_parent_not_readonly(data: ZFSResourceCreateArgsData, ctx: CreateContext, verrors: ValidationErrors) -> None:
    """The nearest existing ancestor must not be readonly.

    ZFS allows creating beneath a readonly parent but the new filesystem
    then fails to mount and a new volume fails on first write. Refuse up
    front with a clear message instead.

    The service calls this after the ancestor entries have been gathered.
    """
    for ancestor in ancestor_chain(data.path):
        rv = ctx.ancestors.get(ancestor)
        if rv is None:
            # a missing ancestor is created (or rejected) later
            continue
        if rv["properties"]["readonly"]["raw"] == "on":
            verrors.add(
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

    The service calls this only for filesystems that do not request
    special_small_blocks while tiering is enabled and after the ancestor
    entries have been gathered.
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

    The service calls this only for volumes that do not request
    special_small_blocks and after the ancestor entries have been
    gathered.
    """
    parent = _nearest_ancestor_entry(data, ctx)
    if parent is None:
        return
    parent_ssb = parent["properties"]["special_small_blocks"]["value"] or 0
    volblocksize = ctx.properties.volblocksize or 16384
    if parent_ssb and volblocksize < parent_ssb:
        ctx.properties.special_small_blocks = 0


def check_dedup_entitlement(data: ZFSResourceCreateArgsData, ctx: CreateContext, verrors: ValidationErrors) -> None:
    """Deduplication may only be enabled on a system entitled to it.

    The service calls this only for requests with a dedup value other
    than off and after the entitlement has been gathered.
    """
    # narrow the optional type for mypy. The service only calls this
    # after gathering the entitlement
    assert ctx.dedup_entitlement is not None

    reject_unentitled_dedup(verrors, f"{SCHEMA}.properties", ctx.dedup_entitlement)


def check_dedup_tiering(
    context: ServiceContext, data: ZFSResourceCreateArgsData, ctx: CreateContext, verrors: ValidationErrors
) -> None:
    """Deduplication may not be enabled on a PERFORMANCE tier filesystem.

    The effective special_small_blocks is the requested value or the one
    inherited from the nearest existing ancestor.

    The service calls this only for filesystems that request a dedup
    value other than off while tiering is enabled and after the tier
    placement has been applied.
    """
    ssb = ctx.properties.special_small_blocks
    if ssb is None:
        parent = _nearest_ancestor_entry(data, ctx)
        ssb = (parent["properties"]["special_small_blocks"]["value"] or 0) if parent else 0
    reject_dedup_on_special_vdev(verrors, f"{SCHEMA}.properties", context, data.path.split("/")[0], ssb)


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


def check_acl_combination(data: ZFSResourceCreateArgsData, ctx: CreateContext, verrors: ValidationErrors) -> None:
    """The requested acl properties must form a usable combination.

    The effective acltype and aclmode are the requested value or the
    value inherited from the nearest existing ancestor.

    The service calls this only for filesystems that request acltype or
    aclmode and after the ancestor entries have been gathered.
    """
    reject_bad_acl_combination(
        verrors,
        f"{SCHEMA}.properties",
        _effective_value("acltype", data, ctx),
        _effective_value("aclmode", data, ctx),
    )


def check_volume_capacity(data: ZFSResourceCreateArgsData, ctx: CreateContext, verrors: ValidationErrors) -> None:
    """A volume reservation may not consume more than 80% of the space
    available to it.

    The effective refreservation (the volsize for a thick volume) is
    measured against the space the nearest existing ancestor leaves to a
    new child, which excludes the unused part of that ancestor's own
    refreservation. Sparse volumes reserve nothing so they are exempt,
    which makes oversubscription a deliberate request rather than a force
    flag.

    The service calls this only for volumes and after the ancestor
    entries have been gathered.
    """
    if ctx.properties.volsize is None:
        return
    parent = _nearest_ancestor_entry(data, ctx)
    if parent is None:
        return
    reject_insufficient_headroom(
        verrors,
        f"{SCHEMA}.properties.refreservation",
        data.path,
        ctx.properties.refreservation or 0,
        0,
        parent["properties"]["available"]["value"] - parent["properties"]["usedbyrefreservation"]["value"],
        volume=True,
    )


def check_encryption(data: ZFSResourceCreateArgsData, ctx: CreateContext, verrors: ValidationErrors) -> None:
    """Validate a request to create a new encryption root.

    Exactly one source of key material must be provided. The existing
    ancestors are then walked nearest first since only the nearest
    encrypted ancestor (if any) matters. An encryption root may not be
    created beneath an unencrypted dataset that itself sits inside an
    encrypted one and a key encrypted root may not be created beneath a
    passphrase encrypted parent since it could not be unlocked while its
    parent is locked.

    The service calls this only when `data.encryption` is set and after
    the ancestor entries have been gathered.
    """
    # narrow the optional type for mypy. The service only calls this
    # when an encryption root is requested
    assert data.encryption is not None

    if ctx.properties.encryption is not None:
        # the internal-only property opts out of the parent's encryption. It
        # cannot be combined with a request for a new encryption root
        verrors.add(
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
        verrors.add(
            f"{SCHEMA}.encryption",
            "Exactly one of `key`, `passphrase`, or `generate_key` must be provided.",
            errno.EINVAL,
        )
        return

    seen_unencrypted = False
    for ancestor in ancestor_chain(data.path):
        rv = ctx.ancestors.get(ancestor)
        if rv is None:
            # a missing ancestor is created (or rejected) later
            continue
        if rv["properties"]["encryption"]["raw"] == "off":
            seen_unencrypted = True
            continue
        if seen_unencrypted:
            verrors.add(
                f"{SCHEMA}.encryption",
                "Creating an encryption root beneath an unencrypted dataset "
                f"that is itself inside encrypted dataset {ancestor!r} is not "
                "allowed.",
                errno.EINVAL,
            )
            break
        if ctx.encrypt["keyformat"] == "hex" and rv["properties"]["keyformat"]["raw"] == "passphrase":
            verrors.add(
                f"{SCHEMA}.encryption.key",
                f"{ancestor!r} is encrypted with a passphrase; a key-encrypted "
                "child cannot be created beneath it because it could not be "
                "unlocked while its parent is locked. Use a passphrase instead.",
                errno.EINVAL,
            )
        break
