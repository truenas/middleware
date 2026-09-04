"""Validation rules for zfs.resource.create.

Rules are small pure functions with a uniform signature. Each one takes
the request model and a CreateContext of resolved values and gathered
facts, raises a single ValidationError on a failed check, and returns
nothing otherwise. Rules never perform I/O. The service calls them
explicitly and in order from its create_impl so the control flow reads
top to bottom in one place. When a rule needs a new fact the service
gathers it and the context grows a field. The draid and dedup tiering
functions also take the service since they must inspect the pool
themselves.
"""

import dataclasses
import errno
import os
import pathlib
import typing

import truenas_pylibzfs

from middlewared.service_exception import ValidationError
from middlewared.utils.crypto import generate_token

from .create_impl import ZFS_TYPE_MAP
from .utils import has_internal_path

if typing.TYPE_CHECKING:
    from middlewared.api.current import ZFSResourceCreateArgsData, ZFSResourceCreateProperties

__all__ = (
    "CreateContext",
    "ancestor_chain",
    "apply_draid_recordsize",
    "apply_draid_volblocksize",
    "apply_tier_snap",
    "apply_volume_ssb_pin",
    "check_acl_combination",
    "check_dedup_tiering",
    "check_encryption",
    "check_name_valid",
    "check_parent_not_readonly",
    "check_path_shape",
    "check_protected_path",
    "check_tier_managed_ssb",
    "check_user_property_names",
    "check_volume_capacity",
    "check_volume_has_volsize",
    "resolve_create_request",
)

SCHEMA = "zfs.resource.create"

_POSIX_OR_OFF_ACLTYPES = frozenset({"posix", "posixacl", "off", "noacl"})
"""The native acltype values (aliases included) that are not nfsv4."""


@dataclasses.dataclass(slots=True, kw_only=True)
class CreateContext:
    """Resolved values and gathered facts that the rules read."""

    properties: "ZFSResourceCreateProperties"
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
    # TODO uncomment when the truenas.entitlements API is merged
    # dedup_entitled: bool = False
    # """Whether this system is licensed to use ZFS deduplication."""


def ancestor_chain(path: str) -> list[str]:
    """Return the ancestors of `path` ordered nearest first."""
    return [i.as_posix() for i in pathlib.PurePosixPath(path).parents if i.as_posix() != "."]


def _secret_value(value: typing.Any) -> str | None:
    # an unset Secret field holds Secret(None), not None
    return value.get_secret_value() if value else None


def _size_bytes(value: str | int) -> int | None:
    """Parse a zfs block size value into bytes. Returns None when the
    value is not understood so the library can judge it instead."""
    if isinstance(value, int):
        return value
    value = value.strip().upper().removesuffix("B")
    multiplier = 1
    if value and value[-1] in ("K", "M"):
        multiplier = 1024 if value[-1] == "K" else 1024 * 1024
        value = value[:-1]
    try:
        return int(value) * multiplier
    except ValueError:
        return None


def _nearest_ancestor_entry(data: "ZFSResourceCreateArgsData", ctx: CreateContext) -> typing.Any | None:
    """Return the gathered entry of the nearest existing ancestor."""
    for ancestor in ancestor_chain(data.path):
        rv = ctx.ancestors.get(ancestor)
        if rv is not None:
            return rv
    return None


def _pool_has_special_vdev(service: typing.Any, pool_name: str) -> bool:
    """Return whether the pool has a SPECIAL allocation class vdev."""
    if pool := service.middleware.call_sync(
        "zpool.query_impl", {"pool_names": [pool_name], "properties": ["class_special_size"]}
    ):
        size = ((pool[0].get("properties") or {}).get("class_special_size") or {}).get("value")
        return isinstance(size, int) and size > 0
    return False


def pool_is_draid(service: typing.Any, pool_name: str) -> bool:
    """Return whether the pool stores data on dRAID vdevs."""
    if pool := service.middleware.call_sync("zpool.query_impl", {"pool_names": [pool_name], "topology": True}):
        for group in pool[0]["topology"]["data"] + pool[0]["topology"].get("special", []):
            if group["vdev_type"].startswith("draid"):
                return True
    return False


def apply_draid_recordsize(service: typing.Any, data: "ZFSResourceCreateArgsData", ctx: CreateContext) -> None:
    """Default a filesystem on a dRAID pool to a 1M recordsize.

    Small blocks perform poorly on dRAID vdevs. Matches the default
    pool.dataset applies.

    The service calls this only for filesystems without an explicit
    recordsize.
    """
    if pool_is_draid(service, data.path.split("/")[0]):
        ctx.properties.recordsize = "1M"


def apply_draid_volblocksize(service: typing.Any, data: "ZFSResourceCreateArgsData", ctx: CreateContext) -> None:
    """Apply the dRAID volume block size default and floor.

    Small blocks perform poorly on dRAID vdevs. A volume defaults to a
    128K volblocksize and an explicitly requested volblocksize must be
    at least 32K. These match the defaults pool.dataset applies.

    The service calls this only for volumes.
    """
    if not pool_is_draid(service, data.path.split("/")[0]):
        return
    if ctx.properties.volblocksize is None:
        ctx.properties.volblocksize = "128K"
    elif (parsed := _size_bytes(ctx.properties.volblocksize)) is not None and parsed < 32768:
        raise ValidationError(
            f"{SCHEMA}.properties",
            "Volume block size must be greater than or equal to 32K for dRAID pools.",
            errno.EINVAL,
        )


def resolve_create_request(
    data: "ZFSResourceCreateArgsData",
) -> tuple["ZFSResourceCreateProperties", dict[str, typing.Any] | None]:
    """Apply creation defaults and resolve the requested encryption.

    Returns a copy of the requested properties with the creation
    defaults applied and the resolved encryption config. The encryption
    config is None when no encryption root is requested or when the
    request provides no key material at all. The rules judge the request
    afterwards so nothing here raises.
    """
    properties = data.properties.model_copy()
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
        acltype = str(properties.acltype or "").lower()
        if acltype == "nfsv4":
            # inherited ACL entries must pass through or chmod strips them
            if properties.aclinherit is None:
                properties.aclinherit = "passthrough"
        elif acltype in _POSIX_OR_OFF_ACLTYPES:
            # a non discard aclmode can prevent the ZFS_ACL_TRIVIAL flag from
            # being set which results in spurious permission errors
            if properties.aclmode is None:
                properties.aclmode = "discard"
            if properties.aclinherit is None:
                properties.aclinherit = "discard"

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


def check_path_shape(data: "ZFSResourceCreateArgsData", ctx: CreateContext) -> None:
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


def check_protected_path(data: "ZFSResourceCreateArgsData", ctx: CreateContext) -> None:
    """Internal paths may only be touched by internal callers."""
    # NOTE `bypass` is a value only exposed to internal
    # callers and not to our public API
    if not data.bypass and has_internal_path(data.path):
        raise ValidationError(SCHEMA, f"{data.path!r} is a protected path.", errno.EACCES)


def check_name_valid(data: "ZFSResourceCreateArgsData", ctx: CreateContext) -> None:
    """The name must be acceptable to ZFS for the requested type and may
    not end with a space."""
    if not truenas_pylibzfs.name_is_valid(name=data.path, type=ZFS_TYPE_MAP[data.type]):
        raise ValidationError(SCHEMA, f"{data.path!r} is not a valid ZFS resource name.", errno.EINVAL)
    elif data.path.endswith(" "):
        # ZFS itself accepts a trailing space but it is a classic footgun
        raise ValidationError(SCHEMA, "Trailing spaces are not permitted in resource names.", errno.EINVAL)


def check_user_property_names(data: "ZFSResourceCreateArgsData", ctx: CreateContext) -> None:
    """User property names must contain a colon."""
    for key in data.user_properties:
        if ":" not in key:
            raise ValidationError(
                f"{SCHEMA}.user_properties",
                f"{key!r} is not a valid user property name (must contain a colon).",
                errno.EINVAL,
            )


def check_volume_has_volsize(data: "ZFSResourceCreateArgsData", ctx: CreateContext) -> None:
    """A volume cannot be created without a size.

    The service calls this only for volumes.
    """
    if ctx.properties.volsize is None:
        raise ValidationError(
            f"{SCHEMA}.properties",
            "'volsize' is required when creating a VOLUME.",
            errno.EINVAL,
        )


def check_parent_not_readonly(data: "ZFSResourceCreateArgsData", ctx: CreateContext) -> None:
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
            raise ValidationError(
                SCHEMA,
                f"Turn off readonly mode on {ancestor!r} to create {data.path!r}.",
                errno.EINVAL,
            )
        return


def check_tier_managed_ssb(data: "ZFSResourceCreateArgsData", ctx: CreateContext) -> None:
    """The tier manager owns special_small_blocks while tiering is enabled.

    The service calls this only when tiering is enabled.
    """
    if data.properties.special_small_blocks is not None:
        raise ValidationError(
            f"{SCHEMA}.properties",
            "ZFS tiering is enabled. Use `zfs.tier.dataset_set_tier` to manage 'special_small_blocks'.",
            errno.EINVAL,
        )


def apply_tier_snap(data: "ZFSResourceCreateArgsData", ctx: CreateContext) -> None:
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


def apply_volume_ssb_pin(data: "ZFSResourceCreateArgsData", ctx: CreateContext) -> None:
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
    volblocksize = _size_bytes(ctx.properties.volblocksize or 16384) or 16384
    if parent_ssb and volblocksize < parent_ssb:
        ctx.properties.special_small_blocks = 0


def check_dedup_tiering(service: typing.Any, data: "ZFSResourceCreateArgsData", ctx: CreateContext) -> None:
    """Deduplication may not be enabled on a PERFORMANCE tier filesystem.

    With tiering enabled a filesystem whose effective special_small_blocks
    is above zero has its data placed on the special vdev and such data
    may not be deduplicated. The pool topology is only inspected once the
    cheaper conditions have passed.

    The service calls this only for filesystems that request a dedup
    value other than off while tiering is enabled and after the tier
    placement has been applied.
    """
    ssb = ctx.properties.special_small_blocks
    if ssb is None:
        parent = _nearest_ancestor_entry(data, ctx)
        ssb = (parent["properties"]["special_small_blocks"]["value"] or 0) if parent else 0
    else:
        ssb = _size_bytes(ssb) or 0
    if not ssb:
        return
    if not _pool_has_special_vdev(service, data.path.split("/")[0]):
        return
    raise ValidationError(
        f"{SCHEMA}.properties",
        "ZFS deduplication is incompatible with tiering and cannot be enabled on a "
        "dataset assigned to the PERFORMANCE tier (its data is placed on the SPECIAL "
        "vdev). Switch it to the REGULAR tier first.",
        errno.EINVAL,
    )


def _effective_value(name: str, data: "ZFSResourceCreateArgsData", ctx: CreateContext) -> str | None:
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


def check_acl_combination(data: "ZFSResourceCreateArgsData", ctx: CreateContext) -> None:
    """The requested acl properties must form a usable combination.

    The effective acltype and aclmode (the requested value or the value
    inherited from the nearest existing ancestor) are checked together.
    A posix or off acltype requires a discard aclmode and a discard
    aclmode strips nfsv4 acls on chmod.

    The service calls this only for filesystems that request acltype or
    aclmode and after the ancestor entries have been gathered.
    """
    acltype = _effective_value("acltype", data, ctx)
    aclmode = _effective_value("aclmode", data, ctx)
    if acltype in _POSIX_OR_OFF_ACLTYPES and aclmode != "discard":
        raise ValidationError(
            f"{SCHEMA}.properties",
            "'aclmode' must be discard when the effective 'acltype' is posix or off.",
            errno.EINVAL,
        )
    elif acltype == "nfsv4" and aclmode == "discard":
        raise ValidationError(
            f"{SCHEMA}.properties",
            "A discard 'aclmode' may not be used with the nfsv4 'acltype'.",
            errno.EINVAL,
        )


def check_volume_capacity(data: "ZFSResourceCreateArgsData", ctx: CreateContext) -> None:
    """A volume reservation may not consume more than 80% of the available space.

    The effective refreservation (the volsize for a thick volume) is
    compared against the available space of the nearest existing
    ancestor. Sparse volumes reserve nothing so they are exempt, which
    makes oversubscription a deliberate request rather than a force
    flag. The check is skipped when the reservation is not expressed in
    bytes since the library validates values itself.

    The service calls this only for volumes and after the ancestor
    entries have been gathered.
    """
    try:
        reservation = int(ctx.properties.refreservation or 0)
    except ValueError:
        # a word value like none means the volume is sparse and reserves nothing
        return

    for ancestor in ancestor_chain(data.path):
        rv = ctx.ancestors.get(ancestor)
        if rv is None:
            # a missing ancestor is created (or rejected) later
            continue
        if reservation > rv["properties"]["available"]["value"] * 0.8:
            raise ValidationError(
                f"{SCHEMA}.properties",
                "The requested refreservation would consume more than 80% of the "
                f"available space on {ancestor!r}. Reduce volsize or create a sparse "
                "volume by setting refreservation to none.",
                errno.EINVAL,
            )
        return


def check_encryption(data: "ZFSResourceCreateArgsData", ctx: CreateContext) -> None:
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
    if len(provided) != 1:
        raise ValidationError(
            f"{SCHEMA}.encryption",
            "Exactly one of `key`, `passphrase`, or `generate_key` must be provided.",
            errno.EINVAL,
        )

    # the resolved encryption config exists once exactly one source of
    # key material was provided
    assert ctx.encrypt is not None

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
            raise ValidationError(
                f"{SCHEMA}.encryption",
                "Creating an encryption root beneath an unencrypted dataset "
                f"that is itself inside encrypted dataset {ancestor!r} is not "
                "allowed.",
                errno.EINVAL,
            )
        if ctx.encrypt["keyformat"] == "hex" and rv["properties"]["keyformat"]["raw"] == "passphrase":
            raise ValidationError(
                f"{SCHEMA}.encryption.key",
                f"{ancestor!r} is encrypted with a passphrase; a key-encrypted "
                "child cannot be created beneath it because it could not be "
                "unlocked while its parent is locked. Use a passphrase instead.",
                errno.EINVAL,
            )
        break
