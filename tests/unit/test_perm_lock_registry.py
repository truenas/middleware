"""
Unit tests for PermLockRegistry in middlewared.plugins.filesystem_.utils.

These tests are pure Python (threading only) and do not require a TrueNAS
system or truenas_os. They use threading.Thread + threading.Event to observe
concurrent behaviour without actually touching any filesystem.
"""

import errno
import threading
import time

import pytest

from middlewared.plugins.filesystem_.utils import PermLockRegistry
from middlewared.service_exception import CallError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_LOCK_TIMEOUT = 5.0  # maximum seconds to wait in test synchronisation


def _run_in_thread(registry, dataset, is_traverse, holding_event, release_event, on_wait=None):
    """
    Acquire registry.lock(dataset, is_traverse) in a background thread.

    Sets `holding_event` once the lock is held, then waits for `release_event`
    before exiting the context (releasing the lock).
    """
    def _target():
        with registry.lock(dataset, is_traverse, on_wait=on_wait):
            holding_event.set()
            release_event.wait(timeout=_LOCK_TIMEOUT)

    t = threading.Thread(target=_target, daemon=True)
    t.start()
    return t


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_exact_same_dataset_serializes():
    """Two exact locks on the same dataset must not overlap."""
    reg = PermLockRegistry()
    holding1 = threading.Event()
    release1 = threading.Event()
    holding2 = threading.Event()
    release2 = threading.Event()

    t1 = _run_in_thread(reg, 'tank/data', False, holding1, release1)
    assert holding1.wait(timeout=_LOCK_TIMEOUT), 'thread 1 did not acquire lock'

    # Start thread 2 — it must block while thread 1 holds the lock.
    t2 = _run_in_thread(reg, 'tank/data', False, holding2, release2)
    # Give thread 2 time to attempt acquisition.
    assert not holding2.wait(timeout=0.3), 'thread 2 should be blocked but is not'

    # Release thread 1 — thread 2 should now proceed.
    release1.set()
    t1.join(timeout=_LOCK_TIMEOUT)
    assert holding2.wait(timeout=_LOCK_TIMEOUT), 'thread 2 did not acquire lock after thread 1 released'

    release2.set()
    t2.join(timeout=_LOCK_TIMEOUT)


def test_exact_different_datasets_concurrent():
    """Two exact locks on different datasets must be held simultaneously."""
    reg = PermLockRegistry()
    holding1 = threading.Event()
    release1 = threading.Event()
    holding2 = threading.Event()
    release2 = threading.Event()

    t1 = _run_in_thread(reg, 'tank/foo', False, holding1, release1)
    t2 = _run_in_thread(reg, 'tank/bar', False, holding2, release2)

    assert holding1.wait(timeout=_LOCK_TIMEOUT), 'thread 1 did not acquire lock'
    assert holding2.wait(timeout=_LOCK_TIMEOUT), 'thread 2 did not acquire lock concurrently'

    release1.set()
    release2.set()
    t1.join(timeout=_LOCK_TIMEOUT)
    t2.join(timeout=_LOCK_TIMEOUT)


def test_traverse_blocks_descendant_exact():
    """A traverse lock on tank/shares must block an exact lock on tank/shares/data."""
    reg = PermLockRegistry()
    holding_trav = threading.Event()
    release_trav = threading.Event()
    holding_exact = threading.Event()
    release_exact = threading.Event()

    t1 = _run_in_thread(reg, 'tank/shares', True, holding_trav, release_trav)
    assert holding_trav.wait(timeout=_LOCK_TIMEOUT)

    t2 = _run_in_thread(reg, 'tank/shares/data', False, holding_exact, release_exact)
    assert not holding_exact.wait(timeout=0.3), 'exact on descendant should be blocked by traverse'

    release_trav.set()
    t1.join(timeout=_LOCK_TIMEOUT)
    assert holding_exact.wait(timeout=_LOCK_TIMEOUT), 'exact on descendant should proceed after traverse released'

    release_exact.set()
    t2.join(timeout=_LOCK_TIMEOUT)


def test_exact_does_not_block_unrelated_traverse():
    """A traverse lock on tank/shares must NOT block an exact lock on tank/vms."""
    reg = PermLockRegistry()
    holding_trav = threading.Event()
    release_trav = threading.Event()
    holding_exact = threading.Event()
    release_exact = threading.Event()

    t1 = _run_in_thread(reg, 'tank/shares', True, holding_trav, release_trav)
    assert holding_trav.wait(timeout=_LOCK_TIMEOUT)

    t2 = _run_in_thread(reg, 'tank/vms', False, holding_exact, release_exact)
    assert holding_exact.wait(timeout=_LOCK_TIMEOUT), 'unrelated exact op should not be blocked by traverse'

    release_trav.set()
    release_exact.set()
    t1.join(timeout=_LOCK_TIMEOUT)
    t2.join(timeout=_LOCK_TIMEOUT)


def test_traverse_blocks_descendant_traverse():
    """A traverse lock on tank/shares must block a traverse lock on tank/shares/sub."""
    reg = PermLockRegistry()
    holding1 = threading.Event()
    release1 = threading.Event()
    holding2 = threading.Event()
    release2 = threading.Event()

    t1 = _run_in_thread(reg, 'tank/shares', True, holding1, release1)
    assert holding1.wait(timeout=_LOCK_TIMEOUT)

    t2 = _run_in_thread(reg, 'tank/shares/sub', True, holding2, release2)
    assert not holding2.wait(timeout=0.3), 'descendant traverse should be blocked'

    release1.set()
    t1.join(timeout=_LOCK_TIMEOUT)
    assert holding2.wait(timeout=_LOCK_TIMEOUT), 'descendant traverse should proceed after ancestor released'

    release2.set()
    t2.join(timeout=_LOCK_TIMEOUT)


def test_on_wait_called_while_blocked():
    """The on_wait callback must be invoked at least once while a lock is blocked."""
    reg = PermLockRegistry()
    holding1 = threading.Event()
    release1 = threading.Event()

    t1 = _run_in_thread(reg, 'tank/data', False, holding1, release1)
    assert holding1.wait(timeout=_LOCK_TIMEOUT)

    calls = []
    acquired = threading.Event()

    def _waiter():
        with reg.lock('tank/data', False, on_wait=lambda: calls.append(1)):
            acquired.set()

    t2 = threading.Thread(target=_waiter, daemon=True)
    t2.start()

    # Wait long enough for at least one poll interval to fire.
    time.sleep(1.5)
    assert len(calls) >= 1, 'on_wait was never called while blocked'

    release1.set()
    t1.join(timeout=_LOCK_TIMEOUT)
    assert acquired.wait(timeout=_LOCK_TIMEOUT)
    t2.join(timeout=_LOCK_TIMEOUT)


def test_lock_released_on_exception():
    """An exception inside the lock context must still release the lock."""
    reg = PermLockRegistry()
    released = threading.Event()

    def _raiser():
        try:
            with reg.lock('tank/data', False):
                raise RuntimeError('intentional')
        except RuntimeError:
            pass
        released.set()

    t1 = threading.Thread(target=_raiser, daemon=True)
    t1.start()
    t1.join(timeout=_LOCK_TIMEOUT)
    assert released.is_set()

    # The lock must now be acquirable by a new caller.
    acquired = threading.Event()
    release2 = threading.Event()

    t2 = _run_in_thread(reg, 'tank/data', False, acquired, release2)
    assert acquired.wait(timeout=_LOCK_TIMEOUT), 'lock not released after exception'
    release2.set()
    t2.join(timeout=_LOCK_TIMEOUT)


# ---------------------------------------------------------------------------
# Cap / EBUSY tests
# ---------------------------------------------------------------------------


def test_cap_raises_ebusy_when_at_limit():
    """A third lock attempt on a registry with max_concurrent=2 must raise CallError(EBUSY)."""
    reg = PermLockRegistry(max_concurrent=2)
    holding1, release1 = threading.Event(), threading.Event()
    holding2, release2 = threading.Event(), threading.Event()

    t1 = _run_in_thread(reg, 'tank/ds1', False, holding1, release1)
    t2 = _run_in_thread(reg, 'tank/ds2', False, holding2, release2)
    assert holding1.wait(timeout=_LOCK_TIMEOUT)
    assert holding2.wait(timeout=_LOCK_TIMEOUT)

    with pytest.raises(CallError) as exc_info:
        with reg.lock('tank/ds3', False):
            pass
    assert exc_info.value.errno == errno.EBUSY

    release1.set()
    release2.set()
    t1.join(timeout=_LOCK_TIMEOUT)
    t2.join(timeout=_LOCK_TIMEOUT)


def test_cap_allows_after_release():
    """Once a slot is freed the next attempt must succeed rather than get EBUSY."""
    reg = PermLockRegistry(max_concurrent=2)
    holding1, release1 = threading.Event(), threading.Event()
    holding2, release2 = threading.Event(), threading.Event()

    t1 = _run_in_thread(reg, 'tank/ds1', False, holding1, release1)
    t2 = _run_in_thread(reg, 'tank/ds2', False, holding2, release2)
    assert holding1.wait(timeout=_LOCK_TIMEOUT)
    assert holding2.wait(timeout=_LOCK_TIMEOUT)

    # Release one slot.
    release1.set()
    t1.join(timeout=_LOCK_TIMEOUT)

    # Now a third lock on a different dataset must succeed.
    acquired = threading.Event()
    release3 = threading.Event()
    t3 = _run_in_thread(reg, 'tank/ds3', False, acquired, release3)
    assert acquired.wait(timeout=_LOCK_TIMEOUT), 'should succeed after a slot was freed'

    release2.set()
    release3.set()
    t2.join(timeout=_LOCK_TIMEOUT)
    t3.join(timeout=_LOCK_TIMEOUT)


def test_cap_does_not_affect_already_waiting_job():
    """
    A job admitted to the wait loop (not yet at cap) must not be rejected
    if the cap fills up while it is blocked on a dataset conflict.
    """
    reg = PermLockRegistry(max_concurrent=2)

    # t1 holds ds1 — t2 will conflict with it and start waiting.
    holding1, release1 = threading.Event(), threading.Event()
    t1 = _run_in_thread(reg, 'tank/ds1', False, holding1, release1)
    assert holding1.wait(timeout=_LOCK_TIMEOUT)

    # t2 targets the same dataset — it enters the conflict wait loop (cap is 1/2, not full).
    holding2, release2 = threading.Event(), threading.Event()
    t2 = _run_in_thread(reg, 'tank/ds1', False, holding2, release2)
    # Give t2 time to enter the wait loop.
    time.sleep(0.2)

    # t3 fills the remaining cap slot with a non-conflicting dataset.
    holding3, release3 = threading.Event(), threading.Event()
    t3 = _run_in_thread(reg, 'tank/ds2', False, holding3, release3)
    assert holding3.wait(timeout=_LOCK_TIMEOUT)
    # Cap is now full (ds1 + ds2 active). t2 is still waiting on ds1 conflict.

    # Release t1 — t2 should now acquire the lock despite the cap being full when it woke.
    release1.set()
    t1.join(timeout=_LOCK_TIMEOUT)
    assert holding2.wait(timeout=_LOCK_TIMEOUT), \
        'waiting job should not be rejected by EBUSY after the cap filled while it waited'

    release2.set()
    release3.set()
    t2.join(timeout=_LOCK_TIMEOUT)
    t3.join(timeout=_LOCK_TIMEOUT)


# ---------------------------------------------------------------------------
# _conflicts() unit tests — one per matrix cell plus prefix-safety cases
# ---------------------------------------------------------------------------


@pytest.mark.parametrize('active_ds, active_trav, incoming_ds, incoming_trav, expect', [
    # ── same dataset: always a conflict ────────────────────────────────────
    ('tank/x', False, 'tank/x', False, True),   # exact vs active exact(same)
    ('tank/x', True,  'tank/x', False, True),   # exact vs active traverse(same)
    ('tank/x', False, 'tank/x', True,  True),   # traverse vs active exact(same)
    ('tank/x', True,  'tank/x', True,  True),   # traverse vs active traverse(same)

    # ── exact active on X, incoming targets child ───────────────────────────
    # exact on a child does not conflict with a non-traversing parent lock
    ('tank/x', False, 'tank/x/child', False, False),
    # traverse on a child does not conflict with a non-traversing parent lock
    ('tank/x', False, 'tank/x/child', True,  False),

    # ── traverse active on X, incoming targets child ────────────────────────
    # exact on child conflicts with traversing parent (parent will descend into child)
    ('tank/x', True,  'tank/x/child', False, True),
    # traverse on child also conflicts with traversing parent
    ('tank/x', True,  'tank/x/child', True,  True),

    # ── exact active on a child, incoming traverse targets parent ───────────
    # traverse(parent) MUST conflict with exact(child) — this is the cell the
    # docstring previously mislabelled as N; the code was always correct.
    ('tank/x/child', False, 'tank/x', True, True),

    # ── traverse active on a child, incoming traverse targets parent ─────────
    ('tank/x/child', True,  'tank/x', True, True),

    # ── sibling datasets: never conflict ────────────────────────────────────
    ('tank/a', False, 'tank/b', False, False),
    ('tank/a', True,  'tank/b', False, False),
    ('tank/a', False, 'tank/b', True,  False),
    ('tank/a', True,  'tank/b', True,  False),

    # ── prefix-safety: 'tank/xa' must not match the 'tank/x' prefix ─────────
    # The code uses startswith(active_ds + '/') so 'tank/xa' != child of 'tank/x'.
    ('tank/x',  False, 'tank/xa', False, False),
    ('tank/x',  True,  'tank/xa', False, False),
    ('tank/x',  False, 'tank/xa', True,  False),
    ('tank/xa', True,  'tank/x',  True,  False),
])
def test_conflicts_matrix(active_ds, active_trav, incoming_ds, incoming_trav, expect):
    """
    _conflicts() must return the value shown in the PermLockRegistry docstring
    conflict matrix for every combination of active and incoming lock type.
    """
    reg = PermLockRegistry()
    reg._active[active_ds] = active_trav
    assert reg._conflicts(incoming_ds, incoming_trav) is expect


# ---------------------------------------------------------------------------
# Threading tests for conflict cases not already covered above
# ---------------------------------------------------------------------------


def test_traverse_parent_blocks_when_exact_child_active():
    """
    A traverse lock on a parent dataset must be blocked when an exact lock on
    a child dataset is already held.  This corresponds to the matrix cell
    traverse(parent) | Active: exact(child) which was previously misdocumented
    as N; the locking code has always been correct.
    """
    reg = PermLockRegistry()
    holding_child = threading.Event()
    release_child = threading.Event()
    holding_trav = threading.Event()
    release_trav = threading.Event()

    t1 = _run_in_thread(reg, 'tank/shares/data', False, holding_child, release_child)
    assert holding_child.wait(timeout=_LOCK_TIMEOUT), 'exact child lock not acquired'

    t2 = _run_in_thread(reg, 'tank/shares', True, holding_trav, release_trav)
    assert not holding_trav.wait(timeout=0.3), \
        'traverse on parent should be blocked by exact lock on child'

    release_child.set()
    t1.join(timeout=_LOCK_TIMEOUT)
    assert holding_trav.wait(timeout=_LOCK_TIMEOUT), \
        'traverse on parent should proceed after child exact lock is released'

    release_trav.set()
    t2.join(timeout=_LOCK_TIMEOUT)
