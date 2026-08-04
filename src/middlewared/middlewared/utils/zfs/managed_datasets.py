"""The datasets middleware maintains for the user, and what callers may do to them.

Those are the boot pools, the per-pool system dataset, the apps datasets and the container dataset.
There is one predicate per caller decision, because the decisions genuinely differ -- hiding a
dataset from a listing is not the same call as refusing to destroy it. Each predicate is a single
line naming the membership it uses and the matching rule it uses; the rules describe themselves.
``hidden_from_snapshot_listing`` is not another rule: it drops a snapshot suffix and then asks
``hidden_from_zfs_listing``, because its callers are handed a name that may be either shape.

The predicates never raise. ``deny_protected_path`` and ``deny_protected_snapshot`` turn
``blocked_from_mutation`` into the standard refusal; callers that accumulate into ``ValidationErrors``
or want to phrase their own message ask the predicate directly.
"""

import errno

from middlewared.service_exception import ValidationError
from middlewared.utils.boot.pool import BOOT_POOL_NAME_VALID

__all__ = (
    "APPS_DS_NAME",
    "CONTAINER_DS_NAME",
    "LEGACY_APPS_DS_NAME",
    "MANAGED_DATASET_NAMES",
    "SYSTEM_DS_NAME",
    "blocked_from_mutation",
    "deny_protected_path",
    "deny_protected_snapshot",
    "excluded_from_replication",
    "excluded_from_zfs_events",
    "hidden_from_dataset_listing",
    "hidden_from_snapshot_listing",
    "hidden_from_zfs_listing",
    "is_boot_pool_path",
)


# ------------------------------------------------------------------ names

SYSTEM_DS_NAME = ".system"

APPS_DS_NAME = "ix-apps"

LEGACY_APPS_DS_NAME = "ix-applications"
"""Name of the per-pool apps dataset used before the current apps implementation. Still managed,
because a system upgraded from an older release still carries one."""

CONTAINER_DS_NAME = ".truenas_containers"

MANAGED_DATASET_NAMES = (
    *BOOT_POOL_NAME_VALID,
    SYSTEM_DS_NAME,
    APPS_DS_NAME,
    LEGACY_APPS_DS_NAME,
    CONTAINER_DS_NAME,
)
"""Every name the predicates can match. No predicate reads this; each names its own membership."""


# ------------------------------------------------------------ memberships

_BOOT_POOLS = frozenset(BOOT_POOL_NAME_VALID)
_SYSTEM = (SYSTEM_DS_NAME,)
_SYSTEM_AND_APPS = (SYSTEM_DS_NAME, APPS_DS_NAME, LEGACY_APPS_DS_NAME)
_SYSTEM_APPS_AND_CONTAINERS = _SYSTEM_AND_APPS + (CONTAINER_DS_NAME,)


# --------------------------------------------------------- matching rules


def is_boot_pool_path(path: str) -> bool:
    """Whether the first component of `path` names a boot pool.

    The bare pool name and everything under it match, while a snapshot of the pool root
    (``boot-pool@snap``) does not, because the suffix lands on the component being compared.
    """
    return path.split("/", 1)[0] in _BOOT_POOLS


def _top_level_child_is(path: str, names: tuple[str, ...]) -> bool:
    """Whether `path` is ``<pool>/<name>`` or below it, for one of `names` compared exactly.

    Anchored one level under the pool root, so ``tank/foo/.system`` does not match, and exact, so
    ``tank/.systembackup`` does not either. A *data* pool root is never matched, because users have
    to be able to lock and destroy their own pools even when one hosts the system dataset; a boot
    pool root is matched by :func:`is_boot_pool_path` instead, which every predicate also asks.

    A snapshot suffix matters exactly when it lands on the compared component:
    ``tank/.system/cores@snap`` matches while ``tank/.system@snap`` does not.
    """
    components = path.split("/")
    return len(components) > 1 and components[1] in names


# ------------------------------------------------------------------ views


def hidden_from_zfs_listing(path: str) -> bool:
    """Whether `path` is omitted from ``zfs.resource`` query results by default."""
    return is_boot_pool_path(path) or _top_level_child_is(path, _SYSTEM_AND_APPS)


def hidden_from_snapshot_listing(path: str) -> bool:
    """Whether `path` is omitted from ``zfs.resource.snapshot`` query and count results by default.

    `path` may be a dataset or a ``<dataset>@<snapshot>`` name. Snapshot visibility is a property of
    the dataset in every case -- there is no snapshot that is hidden while its dataset is listed, nor
    the reverse -- so the suffix is dropped and :func:`hidden_from_zfs_listing` answers. Callers
    holding a name that is certainly a dataset may ask either predicate; they agree.
    """
    return hidden_from_zfs_listing(path.split("@", 1)[0])


def hidden_from_dataset_listing(path: str) -> bool:
    """Whether `path` is omitted from ``pool.dataset`` query results by default.

    The container dataset is matched here and nowhere else: it is hidden from the product listing
    but is an ordinary dataset to every other question. One consequence is that
    ``zfs.resource.destroy`` will destroy it on request while ``pool.dataset.delete`` answers ENOENT,
    because the lookup behind that one goes through this very listing.
    """
    return is_boot_pool_path(path) or _top_level_child_is(path, _SYSTEM_APPS_AND_CONTAINERS)


def blocked_from_mutation(path: str) -> bool:
    """Whether `path` may be created, destroyed or changed only by the subsystem that owns it."""
    return is_boot_pool_path(path) or _top_level_child_is(path, _SYSTEM_AND_APPS)


def excluded_from_replication(path: str) -> bool:
    """Whether `path` is withheld from the dataset list offered when configuring replication.

    The apps datasets are deliberately offered: replication is the supported way to back them up.
    """
    return is_boot_pool_path(path) or _top_level_child_is(path, _SYSTEM)


def excluded_from_zfs_events(path: str) -> bool:
    """Whether changes to `path` seen on the ZFS event channel are dropped rather than published as
    middleware events.

    Suppression has to stay a subset of :func:`hidden_from_dataset_listing`, and the unit tests pin
    that as a law over the whole truth table. Dropping the event for a path the product listing
    shows means an out-of-band ``zfs destroy`` publishes no REMOVED event, never clears the
    dataset's encryption key from the database and never runs the ``dataset.post_delete`` hook that
    removes that key from the other HA node -- so a destroyed dataset leaves the UI holding a stale
    entry and its key registered on both nodes and in KMIP. The other direction costs nothing:
    publishing REMOVED for a name the listing never showed is a no-op.

    The membership is narrower than the listing's on purpose. The container dataset is hidden from
    the listing, but destroying one still has to be published so that cleanup runs.
    """
    return is_boot_pool_path(path) or _top_level_child_is(path, _SYSTEM_AND_APPS)


# ----------------------------------------------------------------- guards


def deny_protected_path(schema: str, path: str, bypass: bool = False) -> None:
    """Raise unless `path` may be mutated by this caller. `path` is taken as written.

    `bypass` is set by the subsystem that owns the path, which lifts the refusal.
    """
    _deny(schema, path, path, bypass)


def deny_protected_snapshot(schema: str, path: str, bypass: bool = False) -> None:
    """Raise unless the dataset `path` names or is a snapshot of may be mutated by this caller.

    `path` may be either a dataset or a ``<dataset>@<snapshot>`` name; the decision is about the
    dataset either way, so the snapshot suffix is dropped before asking. Callers that are not about
    to touch a snapshot want :func:`deny_protected_path`, which does not strip --
    ``zfs.resource.destroy`` has to keep telling the caller to use
    ``zfs.resource.snapshot.destroy`` instead.
    """
    _deny(schema, path.split("@", 1)[0], path, bypass)


def _deny(schema: str, path: str, reported: str, bypass: bool) -> None:
    """Refuse `path`, quoting `reported` -- what the caller actually passed."""
    if not bypass and blocked_from_mutation(path):
        raise ValidationError(schema, f"{reported!r} is a protected path.", errno.EACCES)
