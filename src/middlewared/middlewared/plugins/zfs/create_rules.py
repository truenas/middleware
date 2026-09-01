"""Validation rules for zfs.resource.create.

Rules are small pure functions with a uniform signature. Each one takes
the request model and a CreateContext of resolved values and gathered
facts, raises a single ValidationError on a failed check, and returns
nothing otherwise. Rules never perform I/O. The service calls them
explicitly and in order from its create_impl so the control flow reads
top to bottom in one place. When a rule needs a new fact the service
gathers it and the context grows a field.
"""

import dataclasses
import errno
import os
import pathlib
import typing

import truenas_pylibzfs

from middlewared.service_exception import ValidationError
from middlewared.utils.crypto import generate_token

from .create_impl import ENCRYPTION_PROPERTIES, SHARING_PROPERTIES, ZFS_TYPE_MAP
from .utils import has_internal_path

if typing.TYPE_CHECKING:
    from middlewared.api.current import ZFSResourceCreateArgsData

__all__ = (
    "CreateContext",
    "ancestor_chain",
    "check_denied_properties",
    "check_encryption",
    "check_name_valid",
    "check_path_shape",
    "check_protected_path",
    "check_user_property_names",
    "check_volume_capacity",
    "check_volume_has_volsize",
    "resolve_create_request",
)

SCHEMA = "zfs.resource.create"


@dataclasses.dataclass(slots=True, kw_only=True)
class CreateContext:
    """Resolved values and gathered facts that the rules read."""

    properties: dict[str, str | int]
    """Effective zfs properties after creation defaults are applied."""
    encrypt: dict[str, typing.Any] | None
    """Resolved encryption config when a new encryption root is requested."""
    ancestors: dict[str, typing.Any] = dataclasses.field(default_factory=dict)
    """Existing ancestors of the new resource keyed by name with their
    available space and encryption properties. Populated by the service
    when a rule needs them. A missing ancestor has no entry."""
    # TODO uncomment when the truenas.entitlements API is merged
    # dedup_entitled: bool = False
    # """Whether this system is licensed to use ZFS deduplication."""


def ancestor_chain(path: str) -> list[str]:
    """Return the ancestors of `path` ordered nearest first."""
    return [i.as_posix() for i in pathlib.PurePosixPath(path).parents if i.as_posix() != "."]


def _secret_value(value: typing.Any) -> str | None:
    # an unset Secret field holds Secret(None), not None
    return value.get_secret_value() if value else None


def resolve_create_request(
    data: "ZFSResourceCreateArgsData",
) -> tuple[dict[str, str | int], dict[str, typing.Any] | None]:
    """Apply creation defaults and resolve the requested encryption.

    Returns the effective zfs properties and the resolved encryption
    config. The encryption config is None when no encryption root is
    requested or when the request provides no key material at all. The
    rules judge the request afterwards so nothing here raises.
    """
    properties: dict[str, str | int] = dict(data.properties)
    if data.type == "VOLUME":
        if "volsize" in properties:
            # thick provision unless told otherwise, like `zfs create -V`.
            # NOTE the CLI sets refreservation=auto (volsize plus metadata
            # overhead) but libzfs cannot resolve "auto" through our create
            # path, so reserve the volsize itself
            properties.setdefault("refreservation", properties["volsize"])
    elif "xattr" not in properties:
        # its important to set this as "sa" for performance reasons
        properties["xattr"] = "sa"

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
    """The name must be acceptable to ZFS for the requested type."""
    if not truenas_pylibzfs.name_is_valid(name=data.path, type=ZFS_TYPE_MAP[data.type]):
        raise ValidationError(SCHEMA, f"{data.path!r} is not a valid ZFS resource name.", errno.EINVAL)


def check_denied_properties(data: "ZFSResourceCreateArgsData", ctx: CreateContext) -> None:
    """Properties with dedicated APIs may not ride in generic properties."""
    for prop in ctx.properties:
        if prop.lower() in ENCRYPTION_PROPERTIES:
            raise ValidationError(
                f"{SCHEMA}.properties",
                f"{prop!r} may not be set through generic properties. A resource "
                "inherits its parent's encryption by default. Use the `encryption` "
                "argument to create a new encryption root.",
                errno.EINVAL,
            )
        elif prop.lower() in SHARING_PROPERTIES:
            raise ValidationError(
                f"{SCHEMA}.properties",
                f"{prop!r} may not be set through generic properties. Shares are "
                "managed with the `sharing.nfs` and `sharing.smb` APIs.",
                errno.EINVAL,
            )


# TODO uncomment when the truenas.entitlements API is merged. The service
# gathers the entitlement fact and calls this only when a dedup value
# other than off is requested.
# def check_dedup_entitlement(data: "ZFSResourceCreateArgsData", ctx: CreateContext) -> None:
#     """Enabling deduplication requires a license entitlement."""
#     if not ctx.dedup_entitled:
#         raise ValidationError(
#             f"{SCHEMA}.properties",
#             "This system is not licensed to use ZFS deduplication.",
#             errno.EINVAL,
#         )


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
    """A volume cannot be created without a size."""
    if data.type == "VOLUME" and "volsize" not in ctx.properties:
        raise ValidationError(
            f"{SCHEMA}.properties",
            "'volsize' is required when creating a VOLUME.",
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
        reservation = int(ctx.properties.get("refreservation", 0))
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
