"""
test_267_iscsi_ua_pr_per_nexus.py

Exercises the LIO per-I_T-nexus UA/ALUA/PR fixes (see
UA_PER_NEXUS_REDESIGN.md): real multipath iSCSI sessions sharing one
initiator identity must each get independent UA/PR notification, instead
of one session's state leaking to/from another.

Runs on plain non-HA/non-ALUA systems too, except where noted (ALUA
implicit transition, and the HA-gated class at the bottom).

See UA_PR_TEST_SUITE_PLAN.md for the full design.
"""

from assets.websocket.iscsi import alua_enabled
from auto_config import ha
from iscsi_ua_pr_utils import (
    LABEL_B_IQN,
    LU_SCOPE,
    TOPO_DIFF_IDENTITY,
    TOPO_MIXED,
    TOPO_SAME_IDENTITY,
    SessionHandle,
    add_zvol_lun,
    assert_no_ua,
    assert_ua,
    assert_uas,
    cause_alua_transition_ua,
    cause_reservation_conflict,
    collect_lun_uas,
    collect_uas,
    default_pr_key,
    drain_ua,
    keep_alive,
    node_b_toggles_drop_sessions,
    open_topology,
    pr_check_registered_keys,
    pr_check_reservation,
    pr_clear,
    pr_preempt,
    pr_read_full_status,
    pr_reservation,
    pr_reserve,
    pr_unregister_key,
    register_all,
    registered_sessions,
    resize_zvol,
    resize_zvol_path,
    wait_for_alua_settle,
)
from middlewared.test.integration.assets.iscsi import lio_supported
from middlewared.test.integration.utils.client import truenas_server
from protocols import iscsi_scsi_connection
from pyscsi.pyscsi.scsi_cdb_persistentreservein import PR_TYPE
import pytest


@pytest.fixture(scope="module", autouse=True)
def _require_lio():
    """Skip entire module if LIO mode (2) is not accepted by the API."""
    if not lio_supported():
        pytest.skip("LIO mode (2) not accepted by API")


# ---------------------------------------------------------------------------
# Session identity topologies (see UA_PR_TEST_SUITE_PLAN.md, "Axis
# breakdown for 'exhaustive' coverage")
# ---------------------------------------------------------------------------

TOPOLOGIES = [
    pytest.param(TOPO_SAME_IDENTITY, id="same-identity"),
    pytest.param(TOPO_DIFF_IDENTITY, id="diff-identity"),
    pytest.param(TOPO_MIXED, id="mixed"),
]

# (topology, actor_idx) -- the mixed topology gets two actor choices:
# actor from the IQN-A pair (exclusion discrimination) and the IQN-B
# singleton (fan-out completeness).
PR_TOPOLOGIES = [
    pytest.param(TOPO_SAME_IDENTITY, 0, id="same-identity"),
    pytest.param(TOPO_DIFF_IDENTITY, 0, id="diff-identity"),
    pytest.param(TOPO_MIXED, 0, id="mixed-actor-in-pair"),
    pytest.param(TOPO_MIXED, 2, id="mixed-actor-singleton"),
]


# ---------------------------------------------------------------------------
# Trigger 1: LUN resize (UA fan-out)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("topology", TOPOLOGIES)
def test_resize_notifies_all_sessions(topology, configured_lun):
    with open_topology(topology, configured_lun.iqn) as sessions:
        for s in sessions:
            drain_ua(s)
        resize_zvol(configured_lun, configured_lun.size_mb * 2)
        for s in sessions:
            assert_ua(s, 0x2A, 0x09)  # CAPACITY DATA HAS CHANGED


@pytest.mark.parametrize("topology", TOPOLOGIES)
def test_lun_mapping_change_notifies_existing_sessions(topology, configured_lun):
    """Adding or removing a LUN mapping for a nacl notifies every other
    already-mapped LUN's connected sessions under that nacl with
    REPORTED LUNS DATA HAS CHANGED (target_luns_data_has_changed(),
    target_core_device.c:322) -- a call site with no other coverage in
    this suite (UA_RAISE_CALL_SITE_AUDIT.md). Exercises both directions:
    add_zvol_lun()'s enter (LUN added) and exit (LUN removed again)."""
    with open_topology(topology, configured_lun.iqn) as sessions:
        for s in sessions:
            drain_ua(s)
        with add_zvol_lun(configured_lun, lun_id=1):
            for s in sessions:
                assert_ua(s, 0x3F, 0x0E)  # REPORTED LUNS DATA HAS CHANGED
            for s in sessions:
                drain_ua(s)
        for s in sessions:
            assert_ua(s, 0x3F, 0x0E)  # again, on removal


@pytest.mark.parametrize("topology", TOPOLOGIES)
def test_lun_mapped_after_login_notifies_existing_sessions(topology, configured_lun):
    """A LUN mapped to the ACL after a session logged in must deliver unit
    attentions to that session too. Each session gets its per-LUN UA queue
    for a LUN either at login or, for a LUN mapped later, when the LUN is
    mapped (target_setup_deve_sess_entries()); without the latter, a
    capacity change on the new LUN reached only sessions that logged in
    after it was mapped.

    The sessions are opened on LUN 0 before LUN 1 exists and then address
    LUN 1 over the same I_T nexus. A session opened on LUN 1 after the
    mapping is the control: if it gets no UA either, the resize did not
    raise one and the failure is not about the existing sessions."""
    with open_topology(topology, configured_lun.iqn) as sessions:
        for s in sessions:
            drain_ua(s)
        with add_zvol_lun(configured_lun, lun_id=1, size_mb=20) as zvol:
            with open_topology(("A",), configured_lun.iqn, lun=1) as (control,):
                for s in sessions:
                    collect_lun_uas(s, 1)
                drain_ua(control)

                resize_zvol_path(zvol, 40)

                uas = collect_lun_uas(control, 1)
                assert "0x2A09" in uas, f"control session, opened on LUN 1: {uas}"
                for s in sessions:
                    uas = collect_lun_uas(s, 1)
                    assert "0x2A09" in uas, f"session {s.label}{s.index}, logged in before LUN 1 was mapped: {uas}"


# ---------------------------------------------------------------------------
# Trigger 2: ALUA implicit state transition -- HA hardware only
# (lio_alua_configured skips on non-HA)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("topology", TOPOLOGIES)
def test_alua_implicit_transition_notifies_all_sessions(topology, lio_alua_configured):
    with open_topology(topology, lio_alua_configured.iqn) as sessions:
        for s in sessions:
            drain_ua(s)
        cause_alua_transition_ua(lio_alua_configured)
        for s in sessions:
            assert_ua(s, 0x2A, 0x06)  # ASYMMETRIC ACCESS STATE CHANGED


@pytest.mark.skipif(not ha, reason="ALUA group attach requires HA hardware")
@pytest.mark.parametrize("topology", TOPOLOGIES)
def test_alua_enable_notifies_all_sessions(topology, configured_lun):
    """Enabling ALUA reassigns the LUN's target-port group from
    default_tg_pt_gp to a real one (target_swap_tg_pt_gp() ->
    __target_attach_tg_pt_gp()), raising INQUIRY DATA HAS CHANGED on
    every already-connected session -- a call site
    (UA_RAISE_CALL_SITE_AUDIT.md's target_core_alua.c:1801) with no
    other coverage in this suite. Uses plain configured_lun, not
    lio_alua_configured, and enables ALUA inside the test body after
    sessions are already connected: lio_alua_configured enables it
    during fixture setup, before any session (and thus any deve entry
    to notify) exists, so it can't observe this event."""
    if node_b_toggles_drop_sessions():
        pytest.skip("toggling ALUA with node B ACTIVE renumbers its TPG and drops the sessions")
    with open_topology(topology, configured_lun.iqn) as sessions:
        for s in sessions:
            drain_ua(s)
        with alua_enabled():
            wait_for_alua_settle()
            for s in sessions:
                assert_ua(s, 0x3F, 0x03)  # INQUIRY DATA HAS CHANGED


# ---------------------------------------------------------------------------
# Trigger 3: PR RELEASE / CLEAR / PREEMPT
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("topology,actor_idx", PR_TOPOLOGIES)
@pytest.mark.parametrize(
    "pr_type,expect_ua",
    [
        (PR_TYPE.WRITE_EXCLUSIVE_REGISTRANTS_ONLY, True),
        (PR_TYPE.EXCLUSIVE_ACCESS, False),
    ],
    ids=["regonly-triggers", "exclusive-no-ua"],
)
def test_pr_release_ua_fanout(topology, actor_idx, pr_type, expect_ua, configured_lun):
    with open_topology(topology, configured_lun.iqn) as sessions:
        with registered_sessions(sessions):
            pr_check_registered_keys(sessions[0], [s.key for s in sessions])
            actor = sessions[actor_idx]
            others = [s for i, s in enumerate(sessions) if i != actor_idx]
            with pr_reservation(actor, pr_type, actor.key, other_sessions=others, check_releaser=True):
                pr_check_reservation(actor, {"reservation_key": actor.key, "scope": LU_SCOPE, "type": pr_type})
                for s in sessions:
                    drain_ua(s)
            # pr_reservation()'s __exit__ asserted no UA on the actor, then
            # the fanout (RESERVATIONS RELEASED if expect_ua, else nothing)
            # on every session in `others`.
            pr_check_reservation(actor)


@pytest.mark.parametrize("topology,actor_idx", PR_TOPOLOGIES)
@pytest.mark.parametrize(
    "pr_type,expect_ua",
    [
        (PR_TYPE.WRITE_EXCLUSIVE_REGISTRANTS_ONLY, True),
        (PR_TYPE.EXCLUSIVE_ACCESS, False),
    ],
    ids=["regonly-triggers", "exclusive-no-ua"],
)
def test_pr_implicit_release_via_unregister_ua_fanout(topology, actor_idx, pr_type, expect_ua, configured_lun):
    """Unregistering (REGISTER with sa_res_key=0) while holding the
    reservation implicitly releases it -- a different call site
    (core_scsi3_emulate_pro_register()'s unregister path,
    target_core_pr.c:2378) than explicit RELEASE
    (test_pr_release_ua_fanout above, :2802), but the same SPC-5
    5.14.11.3 registrants-only notification rule. Closes
    UA_RAISE_CALL_SITE_AUDIT.md's coverage gap for :2378's common
    (non-ALL_TG_PT) case."""
    with open_topology(topology, configured_lun.iqn) as sessions:
        register_all(sessions)
        actor = sessions[actor_idx]
        others = [s for i, s in enumerate(sessions) if i != actor_idx]
        pr_reserve(actor, pr_type, actor.key)
        for s in sessions:
            drain_ua(s)
        pr_unregister_key(actor, actor.key)

        assert_no_ua(actor)
        for s in others:
            if expect_ua:
                assert_ua(s, 0x2A, 0x04)  # RESERVATIONS RELEASED
            else:
                assert_no_ua(s)
        pr_check_registered_keys(others[0], [s.key for s in others])


@pytest.mark.parametrize("topology,actor_idx", PR_TOPOLOGIES)
def test_pr_clear_ua_fanout(topology, actor_idx, configured_lun):
    with open_topology(topology, configured_lun.iqn) as sessions:
        # CLEAR wipes every registration server-side, so we can't rely on
        # pr_registration()'s auto-unregister teardown afterward (same
        # SPC-5 5.14.11.2.3 hygiene gap noted in test_261_iscsi_cmd.py's
        # _pr_registration()) -- register directly instead.
        register_all(sessions)
        actor = sessions[actor_idx]
        for s in sessions:
            drain_ua(s)
        pr_clear(actor, actor.key)
        assert_no_ua(actor)
        for i, s in enumerate(sessions):
            if i != actor_idx:
                assert_ua(s, 0x2A, 0x03)  # RESERVATIONS PREEMPTED
        for s in sessions:
            pr_check_registered_keys(s, [])


@pytest.mark.parametrize("topology,actor_idx", PR_TOPOLOGIES)
@pytest.mark.parametrize("type_scope_changed", [False, True], ids=["plain", "type-scope-changed"])
def test_pr_preempt_ua_fanout(topology, actor_idx, type_scope_changed, configured_lun):
    with open_topology(topology, configured_lun.iqn) as sessions:
        # PREEMPT wipes the victim's registration server-side -- same
        # reason as test_pr_clear_ua_fanout above.
        register_all(sessions)
        actor = sessions[actor_idx]
        holder = sessions[(actor_idx + 1) % len(sessions)]
        new_type = PR_TYPE.EXCLUSIVE_ACCESS if type_scope_changed else PR_TYPE.WRITE_EXCLUSIVE

        pr_reserve(holder, PR_TYPE.WRITE_EXCLUSIVE, holder.key)
        for s in sessions:
            drain_ua(s)
        pr_preempt(actor, new_type, actor.key, holder.key)

        # Sessions that must see no UA are checked before any session that
        # must see one: with a per-ACL queue, draining a same-identity
        # session first would make the no-UA check pass vacuously.
        assert_no_ua(actor)
        bystanders = [s for s in sessions if s not in (actor, holder)]
        if not type_scope_changed:
            for s in bystanders:
                assert_no_ua(s)
        assert_ua(holder, 0x2A, 0x05)  # REGISTRATIONS PREEMPTED
        if type_scope_changed:
            for s in bystanders:
                assert_ua(s, 0x2A, 0x04)  # RESERVATIONS RELEASED

        full = pr_read_full_status(actor)
        keys = {d["reservation_key"] for d in full["full_status"]}
        assert holder.key not in keys, full
        assert actor.key in keys, full


@pytest.mark.parametrize("topology,actor_idx", PR_TOPOLOGIES)
def test_pr_preempt_no_reservation_ua_fanout(topology, actor_idx, configured_lun):
    """PREEMPT targeting a specific registration's key while no
    reservation is held at all (e.g. clearing a dead client's
    registration) -- a real, distinct PR use that takes
    core_scsi3_pro_preempt()'s "no existing/non-matching holder" branch,
    not the "SA key matches holder" branch test_pr_preempt_ua_fanout
    above exercises. Same fan-out requirement applies: only the victim
    whose registration actually matched the key should be notified, not
    a sibling sharing its identity."""
    with open_topology(topology, configured_lun.iqn) as sessions:
        register_all(sessions)
        actor = sessions[actor_idx]
        victim = sessions[(actor_idx + 1) % len(sessions)]
        for s in sessions:
            drain_ua(s)
        pr_preempt(actor, PR_TYPE.WRITE_EXCLUSIVE, actor.key, victim.key)

        # No-UA sessions first; see test_pr_preempt_ua_fanout.
        assert_no_ua(actor)
        for s in sessions:
            if s not in (actor, victim):
                assert_no_ua(s)
        assert_ua(victim, 0x2A, 0x05)  # REGISTRATIONS PREEMPTED

        full = pr_read_full_status(actor)
        keys = {d["reservation_key"] for d in full["full_status"]}
        assert victim.key not in keys, full
        assert actor.key in keys, full


def test_pr_preempt_allreg_zero_key_ua_fanout(configured_lun):
    """PREEMPT with a zero SA reservation key against an existing
    ALL_REGISTRANTS-type reservation -- core_scsi3_pro_preempt()'s
    "no existing/non-matching holder" branch, all_reg sub-case, zero-key
    path: removes every other registration and establishes a new
    reservation for the actor. Unlike the targeted (non-zero-key)
    variant below, this can't distinguish correct per-nexus notification
    from the old nacl-wide broadcast bug -- with a zero key, every other
    registrant is removed regardless of identity, so there's no
    untouched sibling to leak the notification to. Covered anyway for
    the call site's other behavior (new-reservation establishment) this
    sub-case alone performs."""
    with open_topology(TOPO_MIXED, configured_lun.iqn) as sessions:
        register_all(sessions)
        victim, establisher, actor = sessions
        pr_reserve(establisher, PR_TYPE.WRITE_EXCLUSIVE_ALL_REGISTRANTS, establisher.key)
        for s in sessions:
            drain_ua(s)
        pr_preempt(actor, PR_TYPE.WRITE_EXCLUSIVE, actor.key, 0)

        assert_no_ua(actor)
        assert_ua(victim, 0x2A, 0x05)  # REGISTRATIONS PREEMPTED
        assert_ua(establisher, 0x2A, 0x05)
        pr_check_reservation(actor, {"reservation_key": actor.key, "scope": LU_SCOPE, "type": PR_TYPE.WRITE_EXCLUSIVE})


def test_pr_preempt_allreg_targeted_ua_fanout(configured_lun):
    """PREEMPT with a non-zero SA reservation key that doesn't match the
    current ALL_REGISTRANTS holder's own key: removes only the one
    registration matching that key, leaving the shared reservation and
    every other registrant's own registration untouched.
    TOPO_MIXED puts the targeted victim and an untouched sibling
    (establisher, the one actually holding the ALL_REGISTRANTS
    reservation) under the same identity -- the exact shape that
    exposed the :3215/:3248 bugs Patch 5 fixed, now exercised at this
    call site's all_reg sub-case instead (UA_RAISE_CALL_SITE_AUDIT.md's
    coverage gap for target_core_pr.c:3096)."""
    with open_topology(TOPO_MIXED, configured_lun.iqn) as sessions:
        register_all(sessions)
        victim, establisher, actor = sessions
        pr_reserve(establisher, PR_TYPE.WRITE_EXCLUSIVE_ALL_REGISTRANTS, establisher.key)
        for s in sessions:
            drain_ua(s)
        pr_preempt(actor, PR_TYPE.WRITE_EXCLUSIVE, actor.key, victim.key)

        # No-UA sessions first; see test_pr_preempt_ua_fanout.
        assert_no_ua(actor)
        assert_no_ua(establisher)  # same identity as victim, own registration untouched
        assert_ua(victim, 0x2A, 0x05)  # REGISTRATIONS PREEMPTED

        # SPC: for a Write Exclusive/Exclusive Access - All Registrants
        # reservation, READ RESERVATION reports reservation_key as zero,
        # not the establishing session's own key (target_core_pr.c's
        # core_scsi3_pri_read_reservation(), quoting spc4r17 5.7.10).
        pr_check_reservation(
            establisher,
            {"reservation_key": 0, "scope": LU_SCOPE, "type": PR_TYPE.WRITE_EXCLUSIVE_ALL_REGISTRANTS},
        )
        full = pr_read_full_status(establisher)
        keys = {d["reservation_key"] for d in full["full_status"]}
        assert victim.key not in keys, full
        assert establisher.key in keys, full
        assert actor.key in keys, full


# ---------------------------------------------------------------------------
# Trigger 4: UA Interlock Control (emulate_ua_intlck_ctrl)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "configured_lun,expect_established",
    [("CLEAR", False), ("NO_CLEAR", False), ("ESTABLISH_UA", True)],
    indirect=["configured_lun"],
)
def test_ua_interlock_control(configured_lun, expect_established):
    """Does not attempt to also verify the ASC/ASCQ dedup rule (SPC:
    "established only once ... regardless [of] the number of commands
    completed with [RESERVATION CONFLICT] status") -- ESTABLISH_UA's own
    UA is peek-only, and target_scsi3_ua_check() runs before
    target_check_reservation() on every dispatch, so once one is pending
    no further command from this session can reach the reservation-
    conflict logic again to generate a second one; clearing it back out
    would need REQUEST SENSE, which pyscsi doesn't support (same gap as
    explicit STPG). Trigger 6's sorting test already exercises
    __core_scsi3_ua_insert_sorted()'s dedup via independent trigger
    mechanisms that don't self-intercept this way.
    """
    with open_topology(("A",), configured_lun.iqn) as (session,):
        drain_ua(session)
        cause_reservation_conflict(session, configured_lun)
        if expect_established:
            assert_ua(session, 0x2C, 0x09)  # PREVIOUS RESERVATION CONFLICT STATUS
        else:
            assert_no_ua(session)


@pytest.mark.parametrize("configured_lun", ["NO_CLEAR"], indirect=True)
def test_ua_interlock_no_clear_peek(configured_lun):
    """NO_CLEAR: direct regression test for the bug Patch 1b fixed in
    core_scsi3_ua_for_check_condition()'s peek branch."""
    with open_topology(("A",), configured_lun.iqn) as (session,):
        drain_ua(session)
        resize_zvol(configured_lun, configured_lun.size_mb * 2)
        assert_ua(session, 0x2A, 0x09)
        assert_ua(session, 0x2A, 0x09)  # still there -- peeked, not cleared


@pytest.mark.parametrize("configured_lun", ["ESTABLISH_UA"], indirect=True)
def test_ua_interlock_sibling_isolation(configured_lun):
    """A sibling under the same identity, sharing nothing with the
    conflicting session, must stay clean -- the direct regression test
    for what the old nacl-shared-UA-queue design would have gotten
    wrong."""
    with open_topology(TOPO_SAME_IDENTITY, configured_lun.iqn) as (s0, s1):
        drain_ua(s0)
        drain_ua(s1)
        cause_reservation_conflict(s0, configured_lun)
        assert_ua(s0, 0x2C, 0x09)
        assert_no_ua(s1)


# ---------------------------------------------------------------------------
# Trigger 6: UA priority sorting / multi-UA insertion
# ---------------------------------------------------------------------------


def test_ua_multiple_pending_each_reported(configured_lun):
    """Raise several real triggers against one session, then check every
    one is reported, one per command, and none is lost: a nexus's UAs are
    queued independently and reporting one clears only that one (SAM-5
    5.14.1). Also pins the order LIO documents for the 2Ah family (lowest
    ASCQ first, from the sorting fixes in __core_scsi3_ua_insert_sorted());
    SAM-5 itself leaves the order of same-precedence UAs undefined, so
    the order is checked separately, and only for the 2Ah family. Every
    required UA must be delivered exactly once; further UAs the setup
    happens to cause are permitted.

    On HA/ALUA hardware, includes all three triggers (PREEMPT/ALUA/
    resize); on plain systems, just PREEMPT/resize, since implicit ALUA
    transitions aren't available without ALUA hardware.
    """
    with open_topology(("A",), configured_lun.iqn) as (session,):
        drain_ua(session)
        register_all([session])
        pr_reserve(session, PR_TYPE.WRITE_EXCLUSIVE, session.key)

        with iscsi_scsi_connection(truenas_server.ip, configured_lun.iqn, initiator_name=LABEL_B_IQN) as other_conn:
            other = SessionHandle(label="B", index=0, node=None, conn=other_conn)
            register_all([other], keys=[default_pr_key(99)])
            # REGISTRATIONS PREEMPTED (0x2A/0x05)
            pr_preempt(other, PR_TYPE.WRITE_EXCLUSIVE, other.key, session.key)

            expected = [(0x2A, 0x05)]
            # With node B ACTIVE, toggling ALUA would drop both sessions;
            # check the other two triggers only.
            if ha and not node_b_toggles_drop_sessions():
                # Toggling ALUA and waiting for it to settle takes minutes;
                # keep both sessions from being dropped as idle meanwhile.
                with keep_alive([session, other]), alua_enabled():
                    wait_for_alua_settle()
                    # Enabling ALUA can also report INQUIRY DATA HAS CHANGED
                    # (0x3F/0x03); that is permitted but not required, so it
                    # is not in `expected`.
                    cause_alua_transition_ua(configured_lun)  # 0x2A/0x06
                    expected.append((0x2A, 0x06))

            resize_zvol(configured_lun, configured_lun.size_mb * 2)  # 0x2A/0x09
            expected.append((0x2A, 0x09))

            delivered = collect_uas(session)
            required = [f"0x{asc:02X}{ascq:02X}" for asc, ascq in expected]
            missing = [ua for ua in required if ua not in delivered]
            assert not missing, f"UAs not delivered: {missing}; delivered {delivered}"
            duplicated = [ua for ua in required if delivered.count(ua) > 1]
            assert not duplicated, f"UAs delivered more than once: {duplicated}; delivered {delivered}"
            family_2ah = [ua for ua in delivered if ua.startswith("0x2A")]
            assert family_2ah == sorted(family_2ah), f"2Ah UAs not in ascending ASCQ order: {delivered}"


def test_lun_change_ua_not_lost_behind_pending_ua(configured_lun):
    """REPORTED LUNS DATA HAS CHANGED raised while another UA is already
    pending must still be reported afterwards: an initiator that never
    sees it does not notice the LUN it gained or lost."""
    with open_topology(("A",), configured_lun.iqn) as (session,):
        drain_ua(session)
        resize_zvol(configured_lun, configured_lun.size_mb * 2)  # 0x2A/0x09 left pending
        with add_zvol_lun(configured_lun, lun_id=1):
            assert_uas(session, [(0x2A, 0x09), (0x3F, 0x0E)])


# ---------------------------------------------------------------------------
# HA node-crossing coverage: sessions split across active/standby nodes.
# Scoped to resize and PR ops -- the two areas with confirmed ha_recv-
# specific fixes (see UA_PER_NEXUS_REDESIGN.md's "add_lio_alua cherry-pick
# notes"). ALUA-transition, interlock, and sorting don't depend on which
# physical node a session lands on.
# ---------------------------------------------------------------------------

HA_NODE_TOPOLOGIES = [
    pytest.param((("A", "active"), ("A", "standby")), id="same-identity-both-nodes"),
    pytest.param((("A", "active"), ("B", "standby")), id="diff-identity-both-nodes"),
]


@pytest.mark.skipif(not ha, reason="HA tests require HA hardware")
class TestHANodeCrossing:
    @pytest.mark.parametrize("topology", HA_NODE_TOPOLOGIES)
    def test_resize_notifies_all_sessions_both_nodes(self, topology, lio_alua_configured):
        node_ips = truenas_server.ha_ips()
        with open_topology(topology, lio_alua_configured.iqn, node_ips=node_ips) as sessions:
            for s in sessions:
                drain_ua(s)
            resize_zvol(lio_alua_configured, lio_alua_configured.size_mb * 2)
            for s in sessions:
                assert_ua(s, 0x2A, 0x09)

    @pytest.mark.parametrize("topology", HA_NODE_TOPOLOGIES)
    @pytest.mark.parametrize(
        "pr_type,expect_ua",
        [
            (PR_TYPE.WRITE_EXCLUSIVE_REGISTRANTS_ONLY, True),
            (PR_TYPE.EXCLUSIVE_ACCESS, False),
        ],
        ids=["regonly-triggers", "exclusive-no-ua"],
    )
    def test_pr_release_ua_fanout_both_nodes(self, topology, pr_type, expect_ua, lio_alua_configured):
        node_ips = truenas_server.ha_ips()
        with open_topology(topology, lio_alua_configured.iqn, node_ips=node_ips) as sessions:
            with registered_sessions(sessions):
                actor = sessions[0]
                others = sessions[1:]
                with pr_reservation(actor, pr_type, actor.key, other_sessions=others, check_releaser=True):
                    for s in sessions:
                        drain_ua(s)
