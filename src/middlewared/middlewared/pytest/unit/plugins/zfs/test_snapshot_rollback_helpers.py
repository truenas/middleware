"""Unit tests for the destroy-failure classification the integration suite cannot reach.

A batched destroy that aborts mid-sync (channel-program memory limit, a signal) is not
reproducible on a live system, so what the classification makes of the kernel's error
list is covered here. Everything observable through the API (conflict refusal, blocker
messages, zvol reservations) is covered by the integration tests instead.
"""

import errno

import pytest

from middlewared.plugins.zfs.exceptions import ZFSRollbackBlockerReason, ZFSRollbackFailedException
from middlewared.plugins.zfs.snapshot_rollback_helpers import classify_destroy_failure

SUBMITTED = ("pool/ds@snap2", "pool/ds@snap3")


def classify(errors, code, clones_destroyed=False, submitted=SUBMITTED):
    return classify_destroy_failure(
        submitted=set(submitted),
        errors=errors,
        code=code,
        clones_destroyed=clones_destroyed,
    )


def test_classify_destroy_failure_busy_is_an_in_use_blocker():
    failure = classify(errors=(("pool/ds@snap2", errno.EBUSY),), code=errno.EBUSY)

    assert failure.code == errno.EBUSY
    assert len(failure.blockers) == 1
    assert failure.blockers[0].snapshot == "pool/ds@snap2"
    assert failure.blockers[0].reason is ZFSRollbackBlockerReason.IN_USE
    assert failure.blockers[0].names == ()
    assert failure.vanished == ()
    assert failure.other == ()
    assert failure.state_unknown is False
    assert failure.reported_per_object is True


@pytest.mark.parametrize(
    "clones_destroyed,expected_reason",
    [
        (False, ZFSRollbackBlockerReason.CLONES),
        (True, ZFSRollbackBlockerReason.CLONE_DESTROY_FAILED),
    ],
)
def test_classify_destroy_failure_eexist_reason_depends_on_clone_handling(clones_destroyed, expected_reason):
    failure = classify(
        errors=(("pool/ds@snap3", errno.EEXIST),),
        code=errno.EEXIST,
        clones_destroyed=clones_destroyed,
    )

    assert [blocker.reason for blocker in failure.blockers] == [expected_reason]
    assert failure.blockers[0].snapshot == "pool/ds@snap3"
    assert failure.blockers[0].names == ()
    assert failure.state_unknown is False


def test_classify_destroy_failure_enoent_objects_have_vanished():
    failure = classify(
        errors=(("pool/ds@snap2", errno.ENOENT), ("pool/ds@snap3", errno.ENOENT)),
        code=errno.ENOENT,
    )

    assert failure.vanished == ("pool/ds@snap2", "pool/ds@snap3")
    assert failure.blockers == ()
    assert failure.other == ()
    assert failure.state_unknown is False
    assert failure.reported_per_object is True


def test_classify_destroy_failure_mixes_vanished_and_blocked():
    failure = classify(
        errors=(("pool/ds@snap2", errno.ENOENT), ("pool/ds@snap3", errno.EBUSY)),
        code=errno.EBUSY,
    )

    assert failure.vanished == ("pool/ds@snap2",)
    assert [blocker.snapshot for blocker in failure.blockers] == ["pool/ds@snap3"]
    assert failure.other == ()
    assert failure.state_unknown is False
    assert failure.reported_per_object is True


def test_classify_destroy_failure_unknown_errno_is_other():
    failure = classify(errors=(("pool/ds@snap2", errno.EPERM),), code=errno.EPERM)

    assert failure.other == (("pool/ds@snap2", errno.EPERM),)
    assert failure.blockers == ()
    assert failure.vanished == ()
    assert failure.state_unknown is False


def test_classify_destroy_failure_synthetic_entry_with_interrupted_errno_is_unknown_state():
    failure = classify(
        errors=(("Operation failed", errno.ENOSPC),),
        code=errno.ENOSPC,
        submitted=("pool/ds@snap2",),
    )

    assert failure.vanished == ()
    assert failure.blockers == ()
    assert failure.other == ()
    assert failure.state_unknown is True
    assert failure.reported_per_object is False


def test_classify_destroy_failure_synthetic_entry_with_check_phase_errno_destroyed_nothing():
    failure = classify(errors=(("Operation failed", errno.EPERM),), code=errno.EPERM)

    assert failure.state_unknown is False
    assert failure.reported_per_object is False


def test_classify_destroy_failure_ignores_a_synthetic_entry_among_real_ones():
    failure = classify(
        errors=(("Operation failed", errno.EBUSY), ("pool/ds@snap3", errno.EBUSY)),
        code=errno.EBUSY,
    )

    assert [blocker.snapshot for blocker in failure.blockers] == ["pool/ds@snap3"]
    assert failure.vanished == ()
    assert failure.other == ()
    assert failure.state_unknown is False
    assert failure.reported_per_object is True


@pytest.mark.parametrize("code", [errno.ENOSPC, errno.EINTR, errno.ECHRNG])
@pytest.mark.parametrize("errors", [None, ()])
def test_classify_destroy_failure_without_an_error_list(errors, code):
    failure = classify(errors=errors, code=code)

    assert failure.state_unknown is True
    assert failure.reported_per_object is False


def test_rollback_failed_exception_names_the_completed_datasets():
    e = ZFSRollbackFailedException("Cannot rollback.", errno.ENOSPC, completed=["pool/a", "pool/b"])

    assert e.errnum == errno.ENOSPC
    assert "partially rolled back" in e.message
    assert "pool/a" in e.message
    assert "pool/b" in e.message
