"""
test_270_iscsi_time2retain.py

What the LIO iSCSI target does with a session that has no connection. A session
whose last connection leaves by a connection-level logout (reason code 1), or
that negotiated ErrorRecoveryLevel 2, is not closed: it waits in Time2Retain
for the initiator to come back. python-scsi cannot send a Logout, so these
tests log in and out with iscsi_raw_initiator.RawInitiator; the session then
shows as TARG_SESS_STATE_FAILED in the node ACL's configfs `info` file.

Three things act on such a session and must close it, because no connection is
left to do it:

  - disabling or deleting the TPG,
  - deleting the node ACL (which waits for every session of the ACL),
  - the same initiator port logging in again (session reinstatement).

Before the fix none of them did. The TPG was freed with the session and its
Time2Retain timer still pointing at it, deleting the ACL never returned, and a
relogin left the old session allocated, which the next ACL delete then hung on.
See LIO_L7_DESIGN-v02.md.

A hang is a failure, not something to wait out: operations that can hang run
with a limit and the test fails when it is hit. A hung kernel thread stays
hung, so the fixture teardown of a failing run may hang too.

The session must be retained for at least a few seconds for a test to act on
it. The target negotiates DefaultTime2Retain down to its TPG parameter (20 by
default); the tests skip, rather than fail, when that is 0, and fail when the
session is gone before they get to it.

The kernel's crash, KASAN and lockdep reports are counted before and after
(kernel_splat_count()); a kernel built without them reports none.

Not covered: a login that joins the session (a new CID with the retained
session's TSIH) at the moment the flags are set. That window is documented in
the fix's commit message, sits between two lock sections, and cannot be hit
from a script.
"""

import contextlib
import random
import threading
from time import monotonic, sleep

from iscsi_raw_initiator import RawInitiator
from iscsi_ua_pr_utils import (
    CLIENT_IQN,
    acl_dir,
    isid_en_context,
    isid_en_hex,
    kernel_splat_count,
    open_nexus,
    remove_acl_mappings,
    run_bounded,
    session_state,
    ssh_bounded,
    tpg_dir,
    wait_for_session_state,
)
from middlewared.test.integration.assets.iscsi import lio_supported
from middlewared.test.integration.utils import call, ssh
from middlewared.test.integration.utils.client import truenas_server
from protocols import iscsi_scsi_connect
import pytest

FAILED = "TARG_SESS_STATE_FAILED"
LOGGED_IN = "TARG_SESS_STATE_LOGGED_IN"

QUALIFIER = 0x70
RETAIN_PROPOSED = 60  # the target negotiates this down to its own parameter

# Limit for an operation that must return. Generous: it is only a hang detector.
HANG_LIMIT = 60

# Iterations of the relogin race. The window is a few instructions wide.
RACE_ITERATIONS = 300


@pytest.fixture(scope="module", autouse=True)
def _require_lio():
    assert lio_supported(), "LIO mode (2) not accepted by API"


class Retained:
    """A session waiting in Time2Retain."""

    def __init__(self, retain, started):
        self.retain = retain
        self._started = started

    def remaining(self):
        return self.retain - (monotonic() - self._started)

    def require_time(self, seconds):
        assert self.remaining() > seconds, (
            f"only {self.remaining():.0f}s of the {self.retain}s Time2Retain left; "
            "the session would expire under the test"
        )


@contextlib.contextmanager
def retained_session(iqn, qualifier=QUALIFIER, proposed=RETAIN_PROPOSED):
    """Log in as CLIENT_IQN with ISID isid_en_hex(qualifier), log out the only
    connection with reason code 1 and yield once the session is waiting in
    Time2Retain, as a Retained."""
    with RawInitiator(
        truenas_server.ip,
        iqn,
        CLIENT_IQN,
        isid_en_hex(qualifier),
        keys={"DefaultTime2Retain": str(proposed)},
    ) as ini:
        ini.login()
        retain = int(ini.negotiated.get("DefaultTime2Retain", proposed))
        assert retain != 0, "DefaultTime2Retain negotiated to 0: the session would not be retained"
        assert ini.logout_connection() == 0, "the target refused the connection-level logout"
        started = monotonic()
    assert wait_for_session_state(iqn, CLIENT_IQN, FAILED, timeout=5), (
        f"the session is not waiting in Time2Retain after the logout: {session_state(iqn, CLIENT_IQN)!r}"
    )
    yield Retained(retain, started)


def _assert_no_new_splats(before, wait=0):
    """No crash, KASAN or lockdep report since `before`. `wait` first, for a
    report that only comes when a timer that should have been stopped fires."""
    if wait > 0:
        sleep(wait)
    after = kernel_splat_count()
    assert after == before, f"{after - before} new crash, KASAN or lockdep line(s) in the kernel log"


def _set_enable(iqn, value):
    ssh(f"echo {value} > {tpg_dir(iqn)}/enable")


def _remove_acl_bounded(iqn):
    """rmdir of CLIENT_IQN's node ACL, which waits for every session of the
    ACL; returns whether it returned within the limit and with what status."""
    remove_acl_mappings(iqn, CLIENT_IQN)
    return ssh_bounded(f"rmdir {acl_dir(iqn, CLIENT_IQN)}", HANG_LIMIT)


# ---------------------------------------------------------------------------
# A retained session and the three things that must close it
# ---------------------------------------------------------------------------


def test_tpg_disable_closes_a_retained_session(configured_lun):
    iqn = configured_lun.iqn
    before = kernel_splat_count()
    with retained_session(iqn) as r:
        r.require_time(10)
        _set_enable(iqn, 0)
        try:
            closed = wait_for_session_state(iqn, CLIENT_IQN, None, timeout=10)
        finally:
            _set_enable(iqn, 1)
        assert closed, f"the session is still {session_state(iqn, CLIENT_IQN)!r} after the TPG was disabled"
    # The Time2Retain timer, if it was left armed, fires within the retain time.
    _assert_no_new_splats(before, wait=max(0, r.remaining()) + 3)


def test_acl_delete_with_a_retained_session_returns(configured_lun):
    iqn = configured_lun.iqn
    before = kernel_splat_count()
    with retained_session(iqn) as r:
        r.require_time(15)
        finished, rc = _remove_acl_bounded(iqn)
    assert finished, (
        f"removing the node ACL did not return within {HANG_LIMIT}s: it waits for a session that is never closed"
    )
    assert rc == 0, f"removing the node ACL failed with status {rc}"
    _assert_no_new_splats(before)


def test_target_delete_with_a_retained_session(configured_lun):
    """Deleting the target deletes its TPG. Before the fix the TPG was freed with
    the session's Time2Retain timer still armed, and the timer handler took a
    lock inside the freed TPG when it fired, up to the retain time later."""
    before = kernel_splat_count()
    with retained_session(configured_lun.iqn) as r:
        r.require_time(8)
        finished, result = run_bounded(lambda: call("iscsi.target.delete", configured_lun.target_id, True), HANG_LIMIT)
    assert finished, f"deleting the target did not return within {HANG_LIMIT}s"
    if isinstance(result, BaseException):
        raise result
    _assert_no_new_splats(before, wait=max(0, r.remaining()) + 3)


def test_relogin_closes_a_retained_session(configured_lun):
    """The initiator comes back with the same name and ISID while its old
    session waits in Time2Retain. The target reinstates the session: the old
    one must be closed. It is not visible in configfs once the ACL points at
    the new session, so look at what a leaked one does: it blocks the ACL's
    removal."""
    iqn = configured_lun.iqn
    before = kernel_splat_count()
    with retained_session(iqn) as r:
        r.require_time(15)
        with open_nexus(truenas_server.ip, iqn, qualifier=QUALIFIER) as a:
            a.conn.inquiry()  # a command that reports and clears no unit attention
            state = session_state(iqn, CLIENT_IQN)
            assert state == LOGGED_IN, f"after the relogin the session is {state!r}"
    assert wait_for_session_state(iqn, CLIENT_IQN, None, timeout=15), (
        f"the session is still {session_state(iqn, CLIENT_IQN)!r} after the initiator logged out"
    )
    finished, rc = _remove_acl_bounded(iqn)
    assert finished, (
        f"removing the node ACL did not return within {HANG_LIMIT}s: the session replaced by the relogin was not closed"
    )
    assert rc == 0, f"removing the node ACL failed with status {rc}"
    # A leaked session is freed with its TPG: a use after free when the target goes.
    _assert_no_new_splats(before, wait=max(0, r.remaining()) + 3)


def test_tpg_disable_while_the_retain_timer_expires(configured_lun):
    """DefaultTime2Retain of 1s, and the TPG disabled about when the timer
    fires: the session is closed by the timer's work item or by the disable,
    and the disable waits for the former. Either way it is gone, once."""
    iqn = configured_lun.iqn
    before = kernel_splat_count()
    with RawInitiator(
        truenas_server.ip, iqn, CLIENT_IQN, isid_en_hex(QUALIFIER), keys={"DefaultTime2Retain": "1"}
    ) as ini:
        ini.login()
        assert int(ini.negotiated.get("DefaultTime2Retain", 1)) != 0, (
            "DefaultTime2Retain negotiated to 0: the session would not be retained"
        )
        assert ini.logout_connection() == 0
    _set_enable(iqn, 0)
    try:
        closed = wait_for_session_state(iqn, CLIENT_IQN, None, timeout=15)
    finally:
        _set_enable(iqn, 1)
    assert closed, f"the session is still {session_state(iqn, CLIENT_IQN)!r}"
    _assert_no_new_splats(before, wait=3)


# ---------------------------------------------------------------------------
# The same operations with a live session: the path that was already right,
# and must stay so.
# ---------------------------------------------------------------------------


@contextlib.contextmanager
def _live_session(iqn):
    """A python-scsi session the test does not close itself: the target is about
    to, and closing a connection it already closed may raise."""
    cm = open_nexus(truenas_server.ip, iqn, qualifier=QUALIFIER)
    session = cm.__enter__()
    try:
        session.conn.inquiry()
        assert session_state(iqn, CLIENT_IQN) == LOGGED_IN
        yield session
    finally:
        with contextlib.suppress(Exception):
            cm.__exit__(None, None, None)


def test_tpg_disable_closes_a_live_session(configured_lun):
    iqn = configured_lun.iqn
    before = kernel_splat_count()
    with _live_session(iqn):
        _set_enable(iqn, 0)
        try:
            closed = wait_for_session_state(iqn, CLIENT_IQN, None, timeout=15)
        finally:
            _set_enable(iqn, 1)
        assert closed, f"the session is still {session_state(iqn, CLIENT_IQN)!r} after the TPG was disabled"
    _assert_no_new_splats(before, wait=3)


def test_acl_delete_with_a_live_session_returns(configured_lun):
    iqn = configured_lun.iqn
    before = kernel_splat_count()
    with _live_session(iqn):
        finished, rc = _remove_acl_bounded(iqn)
    assert finished, f"removing the node ACL did not return within {HANG_LIMIT}s"
    assert rc == 0, f"removing the node ACL failed with status {rc}"
    _assert_no_new_splats(before, wait=3)


# ---------------------------------------------------------------------------
# Relogin racing the old connection's teardown
# ---------------------------------------------------------------------------


def test_relogin_racing_the_old_connection_closing(configured_lun):
    """An ordinary same-ISID relogin while the old connection is being torn
    down, which is the usual reason an initiator logs in again. The login marks
    the old session for reinstatement and the old connection's close may
    already be closing it; exactly one of them must close it. python-scsi sends
    no Logout, so the old connection is dropped with a TCP close, at a random
    point of the new login. Each round ends with one working session; a double
    close is a use after free or a hang, reported by KASAN or by a later step
    never completing."""
    iqn = configured_lun.iqn
    host = truenas_server.ip
    params = isid_en_context(QUALIFIER)
    before = kernel_splat_count()
    failures = []

    for i in range(RACE_ITERATIONS):
        first = iscsi_scsi_connect(host, iqn, 0, context_params=params)
        go = threading.Event()

        def drop_first():
            go.wait()
            sleep(random.uniform(0, 0.004))
            with contextlib.suppress(Exception):
                first.device.close()

        dropper = threading.Thread(target=drop_first)
        dropper.start()
        second = None
        try:
            go.set()
            second = iscsi_scsi_connect(host, iqn, 0, context_params=params)
            second.inquiry()
        except Exception as e:  # noqa: BLE001
            failures.append((i, repr(e)))
        finally:
            dropper.join()
            if second is not None:
                with contextlib.suppress(Exception):
                    second.device.close()
    assert not failures, f"{len(failures)} of {RACE_ITERATIONS} rounds failed; first: {failures[:3]}"

    assert wait_for_session_state(iqn, CLIENT_IQN, None, timeout=30), (
        f"a session is left after the last round: {session_state(iqn, CLIENT_IQN)!r}"
    )
    # A session closed twice, or not at all, shows up when its ACL goes.
    finished, rc = _remove_acl_bounded(iqn)
    assert finished, f"removing the node ACL did not return within {HANG_LIMIT}s"
    assert rc == 0, f"removing the node ACL failed with status {rc}"
    _assert_no_new_splats(before, wait=3)
