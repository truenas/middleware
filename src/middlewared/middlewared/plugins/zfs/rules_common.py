"""Checks shared by the zfs.resource.create and zfs.resource.set rules.

Every `reject_*` function takes the `ValidationErrors` to append to and the attribute to report on, followed by the
values it judges, so each caller resolves "effective" its own way and reports on its own schema. None of them raises.
"""

from __future__ import annotations

import errno
import re
import typing

if typing.TYPE_CHECKING:
    from collections.abc import Collection, Iterable, Mapping

    from middlewared.api.current import EntitlementEntry, ZFSResourceCreateProperties
    from middlewared.service import ServiceContext
    from middlewared.service_exception import ValidationErrors

__all__ = (
    "apply_acl_defaults",
    "pool_has_special_vdev_sync",
    "reject_bad_acl_combination",
    "reject_bad_user_property_names",
    "reject_bad_user_property_values",
    "reject_dedup_on_special_vdev",
    "reject_insufficient_headroom",
    "reject_tier_managed_ssb",
    "reject_unentitled_dedup",
)

_POSIX_OR_OFF_ACLTYPES = frozenset({"posix", "posixacl", "off", "noacl"})
"""The native acltype values (aliases included) that are not nfsv4."""

_USER_PROPERTY_NAME = re.compile(r"[a-z0-9:._-]+")
_USER_PROPERTY_NAME_MAX = 256
_USER_PROPERTY_VALUE_MAX = 8192


def apply_acl_defaults(properties: ZFSResourceCreateProperties, leave: Collection[str] = ()) -> None:
    """Fill in the acl properties an explicit acltype couples with."""
    acltype = str(properties.acltype or "").lower()
    if acltype == "nfsv4":
        # inherited ACL entries must pass through or chmod strips them
        if properties.aclinherit is None and "aclinherit" not in leave:
            properties.aclinherit = "passthrough"
    elif acltype in _POSIX_OR_OFF_ACLTYPES:
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


def reject_bad_user_property_names(verrors: ValidationErrors, attribute: str, names: Iterable[str]) -> None:
    """User property names must follow the grammar ZFS itself enforces."""
    for name in names:
        if ":" not in name:
            reason = "must contain a colon"
        elif not _USER_PROPERTY_NAME.fullmatch(name):
            reason = "may only contain lowercase letters, digits, ':', '.', '_' and '-'"
        elif len(name) >= _USER_PROPERTY_NAME_MAX:
            reason = f"must be shorter than {_USER_PROPERTY_NAME_MAX} characters"
        else:
            continue
        verrors.add(attribute, f"{name!r} is not a valid user property name ({reason}).", errno.EINVAL)


def reject_bad_user_property_values(verrors: ValidationErrors, attribute: str, values: Mapping[str, str]) -> None:
    """User property values must fit in ZFS and stay on one line."""
    for name, value in values.items():
        if len(value.encode()) >= _USER_PROPERTY_VALUE_MAX:
            verrors.add(
                attribute,
                f"The value of {name!r} must be shorter than {_USER_PROPERTY_VALUE_MAX} bytes.",
                errno.EINVAL,
            )
        elif "\n" in value or "\r" in value:
            verrors.add(attribute, f"The value of {name!r} may not contain a line break.", errno.EINVAL)


def reject_tier_managed_ssb(verrors: ValidationErrors, attribute: str) -> None:
    """The tier manager owns special_small_blocks while tiering is enabled.

    Callers apply this only when tiering is enabled and the request touches special_small_blocks.
    """
    verrors.add(
        attribute,
        "ZFS tiering is enabled. Use `zfs.tier.dataset_set_tier` to manage 'special_small_blocks'.",
        errno.EINVAL,
    )


def reject_unentitled_dedup(verrors: ValidationErrors, attribute: str, entitlement: EntitlementEntry) -> None:
    """Deduplication may only be enabled on a system entitled to it.

    Licensed systems must carry the DEDUP feature; unlicensed iX hardware is blocked; Community Edition may use it
    freely. The entitlement engine decides and supplies the message. Matches the gate pool.dataset applies.
    """
    if not entitlement.entitled:
        verrors.add(attribute, entitlement.message, errno.EINVAL)


def reject_dedup_on_special_vdev(
    verrors: ValidationErrors, attribute: str, context: ServiceContext, pool_name: str, ssb: int
) -> None:
    """Deduplication may not be enabled on a PERFORMANCE tier filesystem.

    With tiering enabled a filesystem whose effective special_small_blocks (`ssb`, in bytes) is above zero has its
    data placed on the special vdev and such data may not be deduplicated. The pool topology is only inspected once
    the cheaper condition has passed.
    """
    if not ssb or not pool_has_special_vdev_sync(context, pool_name):
        return
    verrors.add(
        attribute,
        "ZFS deduplication is incompatible with tiering and cannot be enabled on a "
        "dataset assigned to the PERFORMANCE tier (its data is placed on the SPECIAL "
        "vdev). Switch it to the REGULAR tier first.",
        errno.EINVAL,
    )


def reject_bad_acl_combination(
    verrors: ValidationErrors, attribute: str, acltype: str | None, aclmode: str | None
) -> None:
    """A discard aclmode strips nfsv4 acls on chmod."""
    if acltype in _POSIX_OR_OFF_ACLTYPES and aclmode != "discard":
        verrors.add(attribute, "'aclmode' must be discard when the effective 'acltype' is posix or off.", errno.EINVAL)
    elif acltype == "nfsv4" and aclmode == "discard":
        verrors.add(attribute, "A discard 'aclmode' may not be used with the nfsv4 'acltype'.", errno.EINVAL)


def reject_insufficient_headroom(
    verrors: ValidationErrors,
    attribute: str,
    path: str,
    requested: int,
    current: int,
    base: int,
    *,
    volume: bool,
) -> None:
    """A reservation may not grow by more than 80% of the space available to it.

    `base` is the space the kernel measures a new reservation against: `available - usedbyrefreservation` of the
    resource itself, or of the nearest existing ancestor for a resource that does not exist yet. All figures are
    bytes.
    """
    base = max(base, 0)
    delta = requested - current
    if delta > 0.8 * base:
        advice = "Lower refreservation or set it to none"
        if volume:
            advice += " for a sparse volume"
        verrors.add(
            attribute,
            f"Reserving another {delta} would consume more than 80% of the {base} available to {path!r}. {advice}.",
            errno.EINVAL,
        )
