"""Pure helpers for the snapshot rollback implementation.

Everything here takes plain data - names, errnos, the dicts and tuples that
`truenas_pylibzfs` hands back - so it can be unit tested without a live ZFS.
Do not import `truenas_pylibzfs` from this module. Nothing enforces that:
`middlewared.fake_env` fakes the module away in unit runs, so an accidental
import of the implementation module would only fail on a real system. The rule
is a convention, and it is what keeps these tests worth running.
"""

from collections.abc import Collection, Sequence
import dataclasses
import errno
import os
from typing import Any

from .exceptions import ZFSRollbackBlocker, ZFSRollbackBlockerReason

__all__ = ("DestroyFailure", "classify_destroy_failure", "rollback_failure_message")

INTERRUPTED_DESTROY_ERRNOS = frozenset({errno.ENOSPC, errno.EINTR, errno.ECHRNG})
"""Errnos a batched destroy can fail with *after* the sync task started.

The kernel checks every snapshot before destroying any, so a check-phase failure
destroys nothing and comes back with a populated per-snapshot error list. These
errnos instead mean the sync half was aborted (channel-program memory limit, a
signal, a wedged assertion), which comes back with an empty error list and an
unknown number of destroys already committed.
"""


def _strerror(errnum: int) -> str:
    """Describe `errnum`, falling back to its number when it has no message."""
    try:
        return os.strerror(errnum)
    except ValueError:
        return f"errno {errnum}"


@dataclasses.dataclass(slots=True, frozen=True, kw_only=True)
class DestroyFailure:
    """What a failed batched destroy says about the objects that were submitted."""

    code: int
    """Errno the destroy failed with."""
    vanished: tuple[str, ...]
    """Objects the kernel could not find, so they need not be destroyed at all."""
    blockers: tuple[ZFSRollbackBlocker, ...]
    """Objects the kernel refuses to destroy, and why. `names` is always empty: the kernel
    reports an errno, not the holder, so the caller fills the names in if it can."""
    other: tuple[tuple[str, int], ...]
    """Per-object failures that are neither `vanished` nor a known blocker."""
    state_unknown: bool
    """Whether an unknown number of the submitted objects may already have been destroyed."""

    @property
    def reported_per_object(self) -> bool:
        """Whether the kernel named the objects it failed on, which means nothing was destroyed."""
        return bool(self.vanished or self.blockers or self.other)


def classify_destroy_failure(
    *,
    submitted: Collection[str],
    errors: Sequence[Any] | None,
    code: int,
    clones_destroyed: bool,
) -> DestroyFailure:
    """Interpret a failed batched destroy of `submitted`.

    `errors` is `ZFSCoreException.errors`: one `(name, errno)` pair per object the
    kernel's error list named, or a single synthesised pair whose name is not one of
    the submitted objects when that list was empty.
    """
    per_object = [(name, err) for name, err in (errors or ()) if name in submitted]
    if not per_object:
        return DestroyFailure(
            code=code,
            vanished=(),
            blockers=(),
            other=(),
            state_unknown=code in INTERRUPTED_DESTROY_ERRNOS,
        )

    vanished: list[str] = []
    blockers: list[ZFSRollbackBlocker] = []
    other: list[tuple[str, int]] = []
    for name, err in per_object:
        if err == errno.ENOENT:
            # The kernel silently ignores objects that are already gone, so this is
            # defensive only.
            vanished.append(name)
        elif err == errno.EBUSY:
            blockers.append(ZFSRollbackBlocker(snapshot=name, reason=ZFSRollbackBlockerReason.IN_USE, names=()))
        elif err == errno.EEXIST:
            reason = (
                ZFSRollbackBlockerReason.CLONE_DESTROY_FAILED if clones_destroyed else ZFSRollbackBlockerReason.CLONES
            )
            blockers.append(ZFSRollbackBlocker(snapshot=name, reason=reason, names=()))
        else:
            other.append((name, err))

    return DestroyFailure(
        code=code,
        vanished=tuple(vanished),
        blockers=tuple(blockers),
        other=tuple(other),
        state_unknown=False,
    )


def rollback_failure_message(*, path: str, dataset: str, errnum: int) -> str:
    """Explain why the kernel refused to roll `dataset` back to `path`."""
    if errnum == errno.ENOENT:
        return f"Cannot rollback to {path!r}: {dataset!r} no longer exists."
    elif errnum == errno.EEXIST:
        return (
            f"Cannot rollback to {path!r}: something more recent than it still exists. That is either a snapshot "
            "created while the rollback was being prepared, in which case trying again is enough, or a bookmark, "
            "which this operation does not destroy - remove it manually with "
            f"`zfs destroy {dataset}#<bookmark>` and try again."
        )
    elif errnum == errno.ESRCH:
        return f"Cannot rollback to {path!r}: it is no longer among the snapshots of {dataset!r}."
    elif errnum == errno.EBUSY:
        return (
            f"Cannot rollback to {path!r}: {dataset!r} is in use. Something is holding it open - an in-flight "
            "`zfs send`, or a `.zfs/snapshot` automount of one of its snapshots - and the hold has to be gone "
            "before the rollback can proceed."
        )
    elif errnum in (errno.EDQUOT, errno.ENOSPC):
        return (
            f"Cannot rollback to {path!r}: the pool cannot satisfy the `refquota` or `refreservation` of "
            f"{dataset!r} after the rollback ({_strerror(errnum)}). Free space in the pool, or lower those "
            "properties, and try again."
        )
    else:
        return f"Failed to rollback to {path!r}: {_strerror(errnum)}."
