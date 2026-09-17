"""Validation rules for zpool.create.

Rules are small pure functions with a uniform signature. Each one takes
the request model and a CreateContext of resolved values and gathered
facts, raises a ValidationError (or a ValidationErrors when it judges
several vdevs at once) on a failed check, and returns nothing otherwise.
Rules never perform I/O. The service gathers the facts, calls the rules
explicitly and in order from zpool_create.create so the control flow
reads top to bottom in one place, and collects what they raise so the
caller sees every problem in the request at once.
"""

from __future__ import annotations

import dataclasses
import errno
import typing

from middlewared.plugins.pool_.utils import ZPOOL_CACHE_FILE
from middlewared.plugins.zfs_.validation_utils import validate_pool_name
from middlewared.service_exception import ValidationError, ValidationErrors
from middlewared.utils.size import format_size

from .create_impl import MIN_DISKS_PER_VDEV

if typing.TYPE_CHECKING:
    from middlewared.api.current import (
        EntitlementEntry,
        ZpoolCreate,
        ZpoolCreateFilesystemProperties,
        ZpoolCreateProperties,
    )

__all__ = (
    "SCHEMA",
    "CreateContext",
    "check_dedup_entitlement",
    "check_disks_unique",
    "check_force_entitlement",
    "check_min_disks",
    "check_name_valid",
    "check_pool_absent",
    "check_sed_entitlement",
    "check_spare_sizes",
    "collect",
    "dedup_requested",
    "resolve_create_request",
    "topology_disks",
)

SCHEMA = "zpool.create"

Rule = typing.Callable[["ZpoolCreate", "CreateContext"], None]


@dataclasses.dataclass(slots=True, kw_only=True)
class CreateContext:
    """Resolved values and gathered facts that the rules read."""

    properties: ZpoolCreateProperties
    """Effective pool properties after the TrueNAS defaults are applied. A
    field left as None is not sent to ZFS."""
    filesystem_properties: ZpoolCreateFilesystemProperties
    """Effective root filesystem properties after the TrueNAS defaults are
    applied."""
    pool_exists: bool = False
    """Whether a pool of the requested name is already known. Populated by
    the service."""
    disk_sizes: dict[str, int] = dataclasses.field(default_factory=dict)
    """Size in bytes of every disk the topology names. Populated by the
    service once the disks are known to be available."""
    dedup_entitlement: EntitlementEntry | None = None
    """The DEDUP entitlement decision. Populated by the service only when
    the request enables deduplication."""
    sed_entitlement: EntitlementEntry | None = None
    """The SED entitlement decision. Populated by the service only when the
    request asks for an all-SED pool."""
    support_entitlement: EntitlementEntry | None = None
    """The SUPPORT entitlement decision. Populated by the service only when
    the request bypasses topology policy."""


def collect(verrors: ValidationErrors, rule: Rule, data: ZpoolCreate, ctx: CreateContext) -> None:
    """Run one rule and fold what it raises into ``verrors``."""
    try:
        rule(data, ctx)
    except ValidationErrors as e:
        verrors.extend(e)
    except ValidationError as e:
        verrors.add(e.attribute, e.errmsg, e.errno)


def dedup_requested(data: ZpoolCreate) -> bool:
    """Any value other than off (on, verify, a checksum) enables dedup."""
    return str(data.filesystem_properties.dedup or "off").lower() != "off"


def has_draid(data: ZpoolCreate) -> bool:
    return any(vdev.type.startswith("draid") for vdev in data.topology.data)


def resolve_create_request(data: ZpoolCreate) -> tuple[ZpoolCreateProperties, ZpoolCreateFilesystemProperties]:
    """Apply the TrueNAS creation defaults.

    Returns copies of the requested pool and root filesystem properties with
    every default the product relies on filled in where the caller left the
    field null. The rules judge the request afterwards so nothing here raises.
    """
    properties = data.properties.model_copy()
    if properties.ashift is None:
        # https://ixsystems.atlassian.net/browse/NAS-112093
        properties.ashift = 12
    if properties.altroot is None:
        properties.altroot = "/mnt"
    if properties.cachefile is None:
        properties.cachefile = ZPOOL_CACHE_FILE
    if properties.failmode is None:
        properties.failmode = "continue"
    if properties.autoexpand is None:
        properties.autoexpand = "on"
    if properties.dedup_table_quota is None and dedup_requested(data):
        # size the table to the dedup vdevs rather than ZFS's unbounded
        # default, matching pool.create
        properties.dedup_table_quota = "auto"

    fs = data.filesystem_properties.model_copy()
    if fs.atime is None:
        fs.atime = "off"
    if fs.acltype is None:
        fs.acltype = "posix"
    if fs.aclinherit is None:
        fs.aclinherit = "discard"
    if fs.aclmode is None:
        fs.aclmode = "discard"
    if fs.compression is None:
        fs.compression = "lz4"
    if fs.xattr is None:
        # its important to set this as "sa" for performance reasons
        fs.xattr = "sa"
    if fs.mountpoint is None:
        # set explicitly so the pool mounts under altroot; the service
        # inherits it again after creation so the source is not "local"
        fs.mountpoint = f"/{data.name}"
    if fs.recordsize is None and has_draid(data):
        # small blocks perform poorly on dRAID vdevs
        fs.recordsize = "1M"
    return properties, fs


def check_name_valid(data: ZpoolCreate, ctx: CreateContext) -> None:
    """The name must be acceptable to ZFS and not reserved by TrueNAS."""
    if not validate_pool_name(data.name):
        raise ValidationError(f"{SCHEMA}.name", "Invalid pool name", errno.EINVAL)


def check_pool_absent(data: ZpoolCreate, ctx: CreateContext) -> None:
    """The name must not belong to an imported or registered pool."""
    if ctx.pool_exists:
        raise ValidationError(f"{SCHEMA}.name", "A pool with this name already exists.", errno.EEXIST)


def topology_disks(data: ZpoolCreate) -> list[tuple[str, str]]:
    """Every disk the topology names, as ``(disk, location)`` pairs in request order."""
    found = []
    for root in ("data", "log", "special", "dedup"):
        for i, vdev in enumerate(getattr(data.topology, root)):
            for disk in vdev.disks:
                found.append((disk, f"{root}.{i}"))
    for root in ("cache", "spares"):
        for disk in getattr(data.topology, root):
            found.append((disk, root))
    return found


def check_disks_unique(data: ZpoolCreate, ctx: CreateContext) -> None:
    """A disk may appear once in the whole topology.

    The topology is flattened into one device list per vdev before the disks
    are formatted, so a disk named twice would silently vanish from the first
    vdev and only fail inside the binding after the wipe.
    """
    seen: dict[str, str] = {}
    verrors = ValidationErrors()
    for disk, location in topology_disks(data):
        if disk in seen:
            verrors.add(
                f"{SCHEMA}.topology.{location}",
                f"Disk {disk!r} is already used by {seen[disk]}.",
                errno.EINVAL,
            )
        else:
            seen[disk] = location
    verrors.check()


def check_min_disks(data: ZpoolCreate, ctx: CreateContext) -> None:
    """Every vdev has at least the number of disks TrueNAS requires for its type.

    These minimums are product policy, stricter than what ZFS accepts (a
    two-disk RAIDZ1 is legal), so they hold whether or not the topology policy
    is bypassed. Everything else about the layout (the vdev types each root
    accepts, the dRAID configuration, the width caps and the redundancy floor)
    is judged by the binding's dry run once these pass, so the message the
    caller sees is the binding's own.
    """
    verrors = ValidationErrors()
    for root in ("data", "log", "special", "dedup"):
        for i, vdev in enumerate(getattr(data.topology, root)):
            mindisks = MIN_DISKS_PER_VDEV[vdev.type]
            if len(vdev.disks) < mindisks:
                verrors.add(
                    f"{SCHEMA}.topology.{root}.{i}.disks",
                    f"You need at least {mindisks} disk(s) for this vdev type.",
                    errno.EINVAL,
                )
    verrors.check()


def check_spare_sizes(data: ZpoolCreate, ctx: CreateContext) -> None:
    """A hot spare must be able to replace the smallest data disk.

    The service calls this only after the disks are known to be available,
    with their sizes gathered into the context.
    """
    data_sizes = [ctx.disk_sizes[d] for vdev in data.topology.data for d in vdev.disks if d in ctx.disk_sizes]
    if not data_sizes:
        return
    min_data_size = min(data_sizes)
    verrors = ValidationErrors()
    for spare in data.topology.spares:
        spare_size = ctx.disk_sizes.get(spare, 0)
        if spare_size < min_data_size:
            verrors.add(
                f"{SCHEMA}.topology.spares",
                f"Spare {spare} ({format_size(spare_size)}) is smaller than the smallest data disk "
                f"({format_size(min_data_size)})",
                errno.EINVAL,
            )
    verrors.check()


def check_dedup_entitlement(data: ZpoolCreate, ctx: CreateContext) -> None:
    """Deduplication may only be enabled on a system entitled to it.

    The entitlement engine decides and supplies the message. Matches the gate
    pool.create and zfs.resource.create apply.

    The service calls this only for requests with a dedup value other than off
    and after the entitlement has been gathered.
    """
    assert ctx.dedup_entitlement is not None
    if not ctx.dedup_entitlement.entitled:
        raise ValidationError(f"{SCHEMA}.filesystem_properties.dedup", ctx.dedup_entitlement.message, errno.EPERM)


def check_sed_entitlement(data: ZpoolCreate, ctx: CreateContext) -> None:
    """An all-SED pool may only be created on a system entitled to SED.

    The service calls this only for requests with ``all_sed`` set and after the
    entitlement has been gathered.
    """
    assert ctx.sed_entitlement is not None
    if not ctx.sed_entitlement.entitled:
        raise ValidationError(f"{SCHEMA}.all_sed", ctx.sed_entitlement.message, errno.EPERM)


def check_force_entitlement(data: ZpoolCreate, ctx: CreateContext) -> None:
    """Bypassing the topology policy is a footgun and is not permitted on
    systems with a support entitlement, which are expected to use supported
    topologies.

    The service calls this only for requests with ``force_topology`` set and
    after the entitlement has been gathered.
    """
    assert ctx.support_entitlement is not None
    if ctx.support_entitlement.entitled:
        raise ValidationError(
            f"{SCHEMA}.force_topology",
            "Bypassing pool topology validation is not permitted on systems with a support entitlement.",
            errno.EPERM,
        )
