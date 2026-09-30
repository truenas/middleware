"""Checks shared by the zfs.resource.create and zfs.resource.set rules.

Every `reject_*` function takes the attribute to report on, followed by the values it judges, and raises a single
`ValidationError`, so each caller resolves "effective" its own way and reports on its own schema.
"""

from __future__ import annotations

import errno
import re
import typing

from middlewared.service_exception import ValidationError

from .property_choices import DRAID_MINIMUM_RECORDSIZE
from .resource_info import ZFS_MAX_RECORDSIZE
from .utils import pool_is_draid

if typing.TYPE_CHECKING:
    from collections.abc import Collection, Iterable, Mapping

    from middlewared.api.current import EntitlementEntry, ZFSResourceCreateProperties
    from middlewared.service import ServiceContext

__all__ = (
    "SPA_MAXBLOCKSIZE",
    "apply_acl_defaults",
    "pool_has_special_vdev_sync",
    "reject_bad_acl_combination",
    "reject_bad_block_size",
    "reject_bad_recordsize",
    "reject_bad_user_property_names",
    "reject_bad_user_property_values",
    "reject_dedup_on_special_vdev",
    "reject_insufficient_headroom",
    "reject_ssb_out_of_range",
    "reject_tier_managed_ssb",
    "reject_unentitled_dedup",
    "reject_volsize_not_multiple",
)

SPA_MAXBLOCKSIZE = 1 << 24

POSIX_OR_OFF_ACLTYPES = frozenset({"posix", "posixacl", "off", "noacl", "disabled"})
"""The native acltype values (aliases included) that are not nfsv4."""

USER_PROPERTY_NAME = re.compile(r"[a-z0-9:._-]+")
USER_PROPERTY_NAME_MAX = 256
USER_PROPERTY_VALUE_MAX = 8192


def apply_acl_defaults(properties: ZFSResourceCreateProperties, leave: Collection[str] = ()) -> None:
    """Fill in the acl properties an explicit acltype couples with."""
    acltype = str(properties.acltype or "").lower()
    if acltype == "nfsv4":
        # inherited ACL entries must pass through or chmod strips them
        if properties.aclinherit is None and "aclinherit" not in leave:
            properties.aclinherit = "passthrough"
    elif acltype in POSIX_OR_OFF_ACLTYPES:
        # a non discard aclmode can prevent the ZFS_ACL_TRIVIAL flag from
        # being set which results in spurious permission errors
        if properties.aclmode is None and "aclmode" not in leave:
            properties.aclmode = "discard"
        if properties.aclinherit is None and "aclinherit" not in leave:
            properties.aclinherit = "discard"


def pool_has_special_vdev_sync(context: ServiceContext, pool_name: str) -> bool:
    """Return whether the pool has a SPECIAL allocation class vdev."""
    if pool := context.middleware.call_sync(
        "zpool.query_impl", {"pool_names": [pool_name], "properties": ["class_special_size"]}
    ):
        size = ((pool[0].get("properties") or {}).get("class_special_size") or {}).get("value")
        return isinstance(size, int) and size > 0
    return False


def reject_bad_user_property_names(attribute: str, names: Iterable[str]) -> None:
    """User property names must follow the grammar ZFS itself enforces."""
    for name in names:
        if ":" not in name:
            reason = "must contain a colon"
        elif not USER_PROPERTY_NAME.fullmatch(name):
            reason = "may only contain lowercase letters, digits, ':', '.', '_' and '-'"
        elif len(name) >= USER_PROPERTY_NAME_MAX:
            reason = f"must be shorter than {USER_PROPERTY_NAME_MAX} characters"
        else:
            continue
        raise ValidationError(attribute, f"{name!r} is not a valid user property name ({reason}).", errno.EINVAL)


def reject_bad_user_property_values(attribute: str, values: Mapping[str, str]) -> None:
    """User property values must fit in ZFS."""
    for name, value in values.items():
        if len(value.encode()) >= USER_PROPERTY_VALUE_MAX:
            raise ValidationError(
                attribute,
                f"The value of {name!r} must be shorter than {USER_PROPERTY_VALUE_MAX} bytes.",
                errno.EINVAL,
            )


def reject_tier_managed_ssb(attribute: str) -> None:
    """The tier manager owns special_small_blocks while tiering is enabled."""
    raise ValidationError(
        attribute,
        "ZFS tiering is enabled. Use `zfs.tier.dataset_set_tier` to manage 'special_small_blocks'.",
        errno.EINVAL,
    )


def reject_unentitled_dedup(attribute: str, entitlement: EntitlementEntry) -> None:
    """Deduplication may only be enabled on a system entitled to it; the entitlement supplies the refusal message."""
    if not entitlement.entitled:
        raise ValidationError(attribute, entitlement.message, errno.EINVAL)


def reject_dedup_on_special_vdev(attribute: str, context: ServiceContext, pool_name: str, ssb: int) -> None:
    """Deduplication may not be enabled on a PERFORMANCE tier filesystem.

    With tiering enabled a filesystem whose effective special_small_blocks (`ssb`, in bytes) is above zero has its
    data placed on the special vdev and such data may not be deduplicated.
    """
    if not ssb or not pool_has_special_vdev_sync(context, pool_name):
        return
    raise ValidationError(
        attribute,
        "ZFS deduplication is incompatible with tiering and cannot be enabled on a "
        "dataset assigned to the PERFORMANCE tier (its data is placed on the SPECIAL "
        "vdev). Switch it to the REGULAR tier first.",
        errno.EINVAL,
    )


def reject_bad_acl_combination(attribute: str, acltype: str | None, aclmode: str | None) -> None:
    """A discard aclmode strips nfsv4 acls on chmod."""
    if acltype in POSIX_OR_OFF_ACLTYPES and aclmode != "discard":
        raise ValidationError(
            attribute, "'aclmode' must be discard when the effective 'acltype' is posix or off.", errno.EINVAL
        )
    elif acltype == "nfsv4" and aclmode == "discard":
        raise ValidationError(attribute, "A discard 'aclmode' may not be used with the nfsv4 'acltype'.", errno.EINVAL)


def reject_insufficient_headroom(
    attribute: str,
    path: str,
    requested: int,
    current: int,
    base: int,
    *,
    forced: bool = False,
) -> None:
    """A volume reservation may not grow by more than 80% of the space available to it, or by more than all of it
    when `forced`.

    `base` is the space the reservation is measured against. All figures are bytes.
    """
    base = max(base, 0)
    delta = requested - current
    if forced and delta > base:
        raise ValidationError(
            attribute,
            f"Reserving another {delta} would exceed the {base} available to {path!r}. "
            "Lower refreservation or set it to none for a sparse volume.",
            errno.EINVAL,
        )
    elif not forced and delta > 0.8 * base:
        raise ValidationError(
            attribute,
            f"Reserving another {delta} would consume more than 80% of the {base} available to {path!r}. "
            "Lower refreservation, set it to none for a sparse volume, or set force_size.",
            errno.EINVAL,
        )


def reject_bad_block_size(attribute: str, name: str, size: int, maximum: int) -> None:
    if size < 512 or size > maximum or size & (size - 1):
        raise ValidationError(attribute, f"{name!r} must be a power of two from 512 to {maximum} bytes.", errno.EINVAL)


def reject_bad_recordsize(
    attribute: str,
    context: ServiceContext,
    pool_name: str,
    recordsize: int,
    draid_floor: bool = True,
) -> None:
    with open(ZFS_MAX_RECORDSIZE) as f:
        maximum = min(SPA_MAXBLOCKSIZE, int(f.read().strip()))
    reject_bad_block_size(attribute, "recordsize", recordsize, maximum)
    if draid_floor and recordsize < DRAID_MINIMUM_RECORDSIZE and pool_is_draid(context, pool_name):
        raise ValidationError(
            attribute,
            f"'recordsize' must be at least {DRAID_MINIMUM_RECORDSIZE} bytes on a dRAID pool.",
            errno.EINVAL,
        )


def reject_volsize_not_multiple(attribute: str, path: str, volsize: int, volblocksize: int) -> None:
    if volsize % volblocksize:
        raise ValidationError(
            attribute,
            f"'volsize' must be a multiple of the volblocksize of {path!r} ({volblocksize}).",
            errno.EINVAL,
        )


def reject_ssb_out_of_range(attribute: str, ssb: int) -> None:
    if not 0 <= ssb <= SPA_MAXBLOCKSIZE:
        raise ValidationError(
            attribute,
            f"'special_small_blocks' must be between 0 and {SPA_MAXBLOCKSIZE} bytes.",
            errno.EINVAL,
        )
