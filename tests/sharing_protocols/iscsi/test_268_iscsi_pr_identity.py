"""
test_268_iscsi_pr_identity.py

Persistent reservation identity on a single node: a registration belongs to
one I_T nexus, and over iSCSI the initiator port of that nexus is the
initiator name *and* the ISID (SPC-5 5.14.1, 7.6.4.5; RFC 7143 4.4.2, 4.4.3).
Two sessions of one initiator name with different ISIDs are therefore
different initiators for every reservation purpose, and logging in again
with the same name and ISID is the same one.

Scenarios S1-S4 and S6 of HA_PR_EXPECTATIONS.md; the expectations come from
the standards, not from what LIO does. The failover scenarios (S8-S15) need
HA hardware and live elsewhere.

Every test gets a fresh LUN (configured_lun), so nothing is unregistered at
the end: the registrations go away with the LUN.
"""

from iscsi_ua_pr_utils import (
    CLIENT_IQN,
    LU_SCOPE,
    TEST_ISID_EN,
    assert_registered,
    drain_ua,
    expect_reservation_conflict,
    expected_access,
    holder_flags,
    io_access,
    isid_en_hex,
    open_nexus,
    pr_check_registered_keys,
    pr_check_reservation,
    pr_clear,
    pr_preempt,
    pr_register_and_move,
    pr_register_ignore_existing,
    pr_register_key,
    pr_register_raw,
    pr_register_spec_i_pt,
    pr_release,
    pr_replace_key,
    pr_reserve,
    pr_unregister_key,
    registrations_for,
)
from middlewared.test.integration.assets.iscsi import lio_supported
from middlewared.test.integration.utils.client import truenas_server
from pyscsi.pyscsi.scsi_cdb_persistentreservein import PR_TYPE
import pytest

# Initiator ports of the same initiator (CLIENT_IQN): same name, different
# ISID.
ISID_A = 1
ISID_B = 2
ISID_C = 3

# A second initiator port of the same initiator, as (qualifier, enterprise
# number): ISID_A's ISID differs from it in the trailing qualifier only, or in
# the leading bytes as well.
OTHER_ISIDS = [
    pytest.param((ISID_B, TEST_ISID_EN), id="isid-differs-in-low-bytes"),
    pytest.param((ISID_B, TEST_ISID_EN + 1), id="isid-differs-in-high-bytes"),
]

KEY_1 = 0xABCD000000000001
KEY_2 = 0xABCD000000000002
KEY_3 = 0xABCD000000000003


@pytest.fixture(scope="module", autouse=True)
def _require_lio():
    """Skip entire module if LIO mode (2) is not accepted by the API."""
    if not lio_supported():
        pytest.skip("LIO mode (2) not accepted by API")


def _nexus(configured_lun, qualifier, en=TEST_ISID_EN):
    return open_nexus(truenas_server.ip, configured_lun.iqn, qualifier=qualifier, en=en)


def _write(session):
    session.conn.write16(0, 1, bytearray(512))


def _read(session):
    session.conn.read16(0, 1)


def test_s1_two_isids_register_independently(configured_lun):
    """S1: same name, different ISIDs, each registers its own key. Both
    registrations are visible, and unregistering one leaves the other."""
    with _nexus(configured_lun, ISID_A) as s1, _nexus(configured_lun, ISID_B) as s2:
        pr_register_key(s1, KEY_1)
        pr_register_key(s2, KEY_2)

        pr_check_registered_keys(s1, {KEY_1, KEY_2})
        regs = assert_registered(s1, [(KEY_1, ISID_A), (KEY_2, ISID_B)])
        assert len({r.rtpi for r in regs}) == 1, regs  # one target port

        pr_unregister_key(s1, KEY_1)
        pr_check_registered_keys(s2, {KEY_2})
        assert_registered(s2, [(KEY_2, ISID_B)])


def test_s2_same_isid_reconnect_keeps_registration_and_reservation(configured_lun):
    """S2: a registered holder logs out and logs in again with the same
    name and ISID. It is still registered and still the holder, and its key
    works (SPC-5 5.14.1: registrations survive I_T nexus loss)."""
    with _nexus(configured_lun, ISID_A) as s1:
        pr_register_key(s1, KEY_1)
        pr_reserve(s1, PR_TYPE.WRITE_EXCLUSIVE, KEY_1)

    with _nexus(configured_lun, ISID_A) as s1:
        regs = assert_registered(s1, [(KEY_1, ISID_A)])
        assert regs[0].holder, regs
        pr_check_reservation(s1, {"reservation_key": KEY_1, "type": PR_TYPE.WRITE_EXCLUSIVE, "scope": LU_SCOPE})
        # The key still authorizes PR OUT from this nexus.
        pr_release(s1, PR_TYPE.WRITE_EXCLUSIVE, KEY_1)
        pr_check_reservation(s1)
        assert_registered(s1, [(KEY_1, ISID_A)])


@pytest.mark.parametrize("other", OTHER_ISIDS)
def test_s3_different_isid_is_not_the_registrant(other, configured_lun):
    """S3: the registered holder logs out and the same name logs in with a
    *different* ISID. That is a different initiator port, so it is not
    registered: it gets RESERVATION CONFLICT for ordinary PR OUT, and for
    REGISTER carrying the old key (SPC-5 5.14.7 table 68), but may use
    REGISTER AND IGNORE EXISTING KEY (table 69). The original registration
    is untouched."""
    with _nexus(configured_lun, ISID_A) as s1:
        pr_register_key(s1, KEY_1)
        pr_reserve(s1, PR_TYPE.WRITE_EXCLUSIVE, KEY_1)

    with _nexus(configured_lun, *other) as s2:
        # Informational PR IN works without a registration.
        pr_check_registered_keys(s2, {KEY_1})

        with expect_reservation_conflict(s2):
            pr_release(s2, PR_TYPE.WRITE_EXCLUSIVE, KEY_1)
        with expect_reservation_conflict(s2):
            pr_unregister_key(s2, KEY_1)
        with expect_reservation_conflict(s2):
            pr_register_raw(s2, reservation_key=KEY_1, service_action_key=KEY_2)

        # Nothing above changed anything.
        assert_registered(s2, [(KEY_1, ISID_A)])
        pr_check_reservation(s2, {"reservation_key": KEY_1, "type": PR_TYPE.WRITE_EXCLUSIVE})

        pr_register_ignore_existing(s2, KEY_2)
        regs = assert_registered(s2, [(KEY_1, ISID_A), (KEY_2, *other)])
        assert [r.holder for r in registrations_for(regs, KEY_1)] == [True], regs
        assert [r.holder for r in registrations_for(regs, KEY_2)] == [False], regs


@pytest.mark.parametrize("pr_type", [PR_TYPE.WRITE_EXCLUSIVE, PR_TYPE.EXCLUSIVE_ACCESS], ids=["WE", "EA"])
@pytest.mark.parametrize("isid_b", [pytest.param(None, id="same-isid"), *OTHER_ISIDS])
def test_s4_holder_access_after_reconnect(pr_type, isid_b, configured_lun):
    """S4: the holder of a reservation logs out and reconnects. With the
    same ISID it is still the holder and may read and write. With a
    different ISID it is an unregistered non-holder: writes conflict under
    both types and reads conflict under EXCLUSIVE ACCESS only (SPC-5 tables
    66 and 67). The different ISID is tried in the two forms of OTHER_ISIDS."""
    with _nexus(configured_lun, ISID_A) as s1:
        pr_register_key(s1, KEY_1)
        pr_reserve(s1, pr_type, KEY_1)

    same_isid = isid_b is None
    with _nexus(configured_lun, ISID_A) if same_isid else _nexus(configured_lun, *isid_b) as s:
        if same_isid:
            _write(s)
            _read(s)
        else:
            with expect_reservation_conflict(s):
                _write(s)
            if pr_type == PR_TYPE.EXCLUSIVE_ACCESS:
                with expect_reservation_conflict(s):
                    _read(s)
            else:
                _read(s)


@pytest.mark.parametrize("same_key", [False, True], ids=["distinct-keys", "same-key-value"])
def test_s6_registration_changes_do_not_affect_other_nexus(same_key, configured_lun):
    """S6: re-keying or unregistering through one nexus leaves another
    nexus of the same initiator alone, even when both use the same key
    value (SPC-5 5.14.7: a registration has no effect on any other
    registration)."""
    key_a = KEY_1
    key_b = KEY_1 if same_key else KEY_2
    with _nexus(configured_lun, ISID_A) as s1, _nexus(configured_lun, ISID_B) as s2:
        pr_register_key(s1, key_a)
        pr_register_key(s2, key_b)
        assert_registered(s1, [(key_a, ISID_A), (key_b, ISID_B)])

        pr_replace_key(s1, key_a, KEY_3)
        assert_registered(s1, [(KEY_3, ISID_A), (key_b, ISID_B)])

        pr_replace_key(s2, key_b, KEY_2 if same_key else KEY_1)
        assert_registered(s1, [(KEY_3, ISID_A), (KEY_2 if same_key else KEY_1, ISID_B)])

        pr_unregister_key(s1, KEY_3)
        assert_registered(s2, [(KEY_2 if same_key else KEY_1, ISID_B)])


@pytest.mark.parametrize("pr_type", [PR_TYPE.WRITE_EXCLUSIVE, PR_TYPE.EXCLUSIVE_ACCESS], ids=["WE", "EA"])
@pytest.mark.parametrize("other", OTHER_ISIDS)
def test_s4_other_isid_while_holder_online(pr_type, other, configured_lun):
    """S4, with the holder still logged in: a second initiator port of the
    same initiator that has not registered gets the access of an unregistered
    non-holder, however its ISID differs from the holder's (SPC-5 tables 66
    and 67), and the holder keeps its access."""
    with _nexus(configured_lun, ISID_A) as s1, _nexus(configured_lun, *other) as s2:
        pr_register_key(s1, KEY_1)
        pr_reserve(s1, pr_type, KEY_1)
        _write(s1)
        _read(s1)

        with expect_reservation_conflict(s2):
            _write(s2)
        if pr_type == PR_TYPE.EXCLUSIVE_ACCESS:
            with expect_reservation_conflict(s2):
                _read(s2)
        else:
            _read(s2)

        _write(s1)
        _read(s1)


@pytest.mark.parametrize("other", OTHER_ISIDS)
def test_s3_other_isid_login_does_not_take_over_the_registration(other, configured_lun):
    """S3: while the holder is logged in, another initiator port of the same
    initiator logs in and registers its own key. The holder's registration
    and reservation are unchanged, the newcomer is a separate non-holder
    registration, and both outlive the newcomer's session."""
    with _nexus(configured_lun, ISID_A) as s1:
        pr_register_key(s1, KEY_1)
        pr_reserve(s1, PR_TYPE.WRITE_EXCLUSIVE, KEY_1)

        with _nexus(configured_lun, *other) as s2:
            regs = assert_registered(s1, [(KEY_1, ISID_A)])
            assert regs[0].holder, regs

            pr_register_ignore_existing(s2, KEY_2)
            regs = assert_registered(s1, [(KEY_1, ISID_A), (KEY_2, *other)])
            assert [r.holder for r in registrations_for(regs, KEY_1)] == [True], regs
            assert [r.holder for r in registrations_for(regs, KEY_2)] == [False], regs

            _write(s1)
            with expect_reservation_conflict(s2):
                _write(s2)

        regs = assert_registered(s1, [(KEY_1, ISID_A), (KEY_2, *other)])
        assert [r.holder for r in registrations_for(regs, KEY_1)] == [True], regs
        _write(s1)


def _pr_out_from_unregistered(session, action, rtpi):
    if action == "reserve":
        pr_reserve(session, PR_TYPE.WRITE_EXCLUSIVE, KEY_2)
    elif action == "release":
        pr_release(session, PR_TYPE.WRITE_EXCLUSIVE, KEY_2)
    elif action == "clear":
        pr_clear(session, KEY_2)
    elif action == "preempt":
        pr_preempt(session, PR_TYPE.WRITE_EXCLUSIVE, KEY_2, KEY_1)
    elif action == "register-and-move":
        pr_register_and_move(session, KEY_2, KEY_3, CLIENT_IQN, isid_en_hex(ISID_A), rtpi)
    else:
        raise ValueError(action)


@pytest.mark.parametrize("action", ["reserve", "release", "clear", "preempt", "register-and-move"])
@pytest.mark.parametrize("reserved", [False, True], ids=["no-reservation", "reservation-held"])
def test_unregistered_nexus_pr_out_gets_reservation_conflict(action, reserved, configured_lun):
    """Any PR OUT service action other than REGISTER and REGISTER AND IGNORE
    EXISTING KEY from an unregistered I_T nexus is completed with RESERVATION
    CONFLICT, whether or not a reservation exists (SPC-5 5.14.7; table 71 for
    REGISTER AND MOVE), and changes nothing."""
    with _nexus(configured_lun, ISID_A) as s1, _nexus(configured_lun, ISID_B) as s2:
        pr_register_key(s1, KEY_1)
        if reserved:
            pr_reserve(s1, PR_TYPE.WRITE_EXCLUSIVE, KEY_1)
        rtpi = assert_registered(s1, [(KEY_1, ISID_A)])[0].rtpi

        with expect_reservation_conflict(s2):
            _pr_out_from_unregistered(s2, action, rtpi)

        assert_registered(s1, [(KEY_1, ISID_A)])
        if reserved:
            pr_check_reservation(s1, {"reservation_key": KEY_1, "type": PR_TYPE.WRITE_EXCLUSIVE, "scope": LU_SCOPE})
        else:
            pr_check_reservation(s1)


# ---------------------------------------------------------------------------
# A nexus registered by another nexus while it is logged in
#
# SPEC_I_PT=1 and REGISTER AND MOVE register an initiator port other than the
# one issuing the command. When that port is already logged in, it is
# registered from then on without logging in again. The difference shows only
# where the target must decide whether a non-holder is registered: I/O under a
# registrants-only or all-registrants reservation, and PREEMPT or CLEAR while
# another nexus holds the reservation (SPC-5 tables 66, 67 and 70).
# ---------------------------------------------------------------------------

REGISTRANTS_TYPES = [
    pytest.param(PR_TYPE.WRITE_EXCLUSIVE_REGISTRANTS_ONLY, id="WE-RR"),
    pytest.param(PR_TYPE.EXCLUSIVE_ACCESS_REGISTRANTS_ONLY, id="EA-RR"),
    pytest.param(PR_TYPE.WRITE_EXCLUSIVE_ALL_REGISTRANTS, id="WE-AR"),
    pytest.param(PR_TYPE.EXCLUSIVE_ACCESS_ALL_REGISTRANTS, id="EA-AR"),
]


@pytest.mark.parametrize("pr_type", REGISTRANTS_TYPES)
def test_spec_i_pt_registers_a_logged_in_nexus(pr_type, configured_lun):
    """REGISTER with SPEC_I_PT=1 names another initiator port of the same
    initiator that is already logged in. Under a registrants-only or
    all-registrants reservation held by the registering nexus, the named
    nexus has the access of a registered nexus, and a third initiator port
    of the same initiator that nobody registered does not (SPC-5 5.14.7,
    tables 66 and 67)."""
    with (
        _nexus(configured_lun, ISID_A) as s1,
        _nexus(configured_lun, ISID_B) as s2,
        _nexus(configured_lun, ISID_C) as s3,
    ):
        pr_register_spec_i_pt(s1, KEY_1, [(CLIENT_IQN, isid_en_hex(ISID_B))])
        assert_registered(s1, [(KEY_1, ISID_A), (KEY_1, ISID_B)])

        pr_reserve(s1, pr_type, KEY_1)
        assert io_access(s2) == expected_access(pr_type, "registered")
        assert io_access(s3) == expected_access(pr_type, "unregistered")


@pytest.mark.parametrize("action", ["preempt", "clear"])
def test_spec_i_pt_registered_nexus_may_preempt_or_clear(action, configured_lun):
    """A nexus registered through SPEC_I_PT=1 by another, while logged in, is
    a registered non-holder: with a WRITE EXCLUSIVE reservation held by the
    registering nexus, its PREEMPT and CLEAR are accepted (SPC-5 table 70),
    not completed with RESERVATION CONFLICT."""
    with _nexus(configured_lun, ISID_A) as s1, _nexus(configured_lun, ISID_B) as s2:
        pr_register_spec_i_pt(s1, KEY_1, [(CLIENT_IQN, isid_en_hex(ISID_B))])
        pr_replace_key(s2, KEY_1, KEY_2)
        assert_registered(s1, [(KEY_1, ISID_A), (KEY_2, ISID_B)])
        pr_reserve(s1, PR_TYPE.WRITE_EXCLUSIVE, KEY_1)

        if action == "preempt":
            pr_preempt(s2, PR_TYPE.WRITE_EXCLUSIVE, KEY_2, KEY_1)
            regs = assert_registered(s2, [(KEY_2, ISID_B)])
            assert regs[0].holder, regs
        else:
            pr_clear(s2, KEY_2)
            assert_registered(s2, [])
            pr_check_reservation(s2)


def test_register_and_move_to_a_logged_in_nexus(configured_lun):
    """REGISTER AND MOVE to another initiator port of the same initiator that
    is already logged in registers it and makes it the holder, with the type
    of the reservation it moved (SPC-5 5.14.8). It stays registered after it
    releases: once the original nexus reserves WRITE EXCLUSIVE - REGISTRANTS
    ONLY, it may write as a registered non-holder, and a third initiator
    port that nobody registered may not."""
    moved_type = PR_TYPE.WRITE_EXCLUSIVE
    pr_type = PR_TYPE.WRITE_EXCLUSIVE_REGISTRANTS_ONLY
    with (
        _nexus(configured_lun, ISID_A) as s1,
        _nexus(configured_lun, ISID_B) as s2,
        _nexus(configured_lun, ISID_C) as s3,
    ):
        pr_register_key(s1, KEY_1)
        pr_reserve(s1, moved_type, KEY_1)
        rtpi = assert_registered(s1, [(KEY_1, ISID_A)])[0].rtpi

        pr_register_and_move(s1, KEY_1, KEY_2, CLIENT_IQN, isid_en_hex(ISID_B), rtpi, pr_type=moved_type)
        regs = assert_registered(s1, [(KEY_1, ISID_A), (KEY_2, ISID_B)])
        assert holder_flags(regs) == {KEY_1: False, KEY_2: True}, regs
        assert io_access(s2) == expected_access(moved_type, "holder")

        pr_release(s2, moved_type, KEY_2)
        drain_ua(s1)
        pr_reserve(s1, pr_type, KEY_1)
        assert io_access(s2) == expected_access(pr_type, "registered")
        assert io_access(s3) == expected_access(pr_type, "unregistered")


def test_register_and_move_with_unreg_unregisters_the_source(configured_lun):
    """REGISTER AND MOVE with the UNREG bit set moves the reservation as
    without it, then unregisters the I_T nexus it was received on (SPC-5
    5.14.8). The destination is the only registrant and the holder; the
    source is no longer registered, so its PR OUT gets RESERVATION CONFLICT
    and it has the access of an unregistered nexus."""
    pr_type = PR_TYPE.WRITE_EXCLUSIVE
    with _nexus(configured_lun, ISID_A) as s1, _nexus(configured_lun, ISID_B) as s2:
        pr_register_key(s1, KEY_1)
        pr_reserve(s1, pr_type, KEY_1)
        rtpi = assert_registered(s1, [(KEY_1, ISID_A)])[0].rtpi

        pr_register_and_move(s1, KEY_1, KEY_2, CLIENT_IQN, isid_en_hex(ISID_B), rtpi, pr_type=pr_type, unreg=True)
        regs = assert_registered(s2, [(KEY_2, ISID_B)])
        assert holder_flags(regs) == {KEY_2: True}, regs
        pr_check_reservation(s2, {"reservation_key": KEY_2, "type": pr_type, "scope": LU_SCOPE})
        assert io_access(s2) == expected_access(pr_type, "holder")
        assert io_access(s1) == expected_access(pr_type, "unregistered")
        with expect_reservation_conflict(s1):
            pr_release(s1, pr_type, KEY_1)
