"""
test_269_iscsi_pr_failover.py

Persistent reservations through HA failover and failback (needs an HA pair, LIO
mode with ALUA). What a persistent reservation is and who may do what is fixed
by SPC-5 5.14 and the iSCSI identity rules of RFC 7143 4.4.2 and 4.4.3: a
registration belongs to an I_T nexus, which over iSCSI is the initiator name
plus ISID towards one target port. These tests follow that, and the TrueNAS
requirement that registrations survive failover. The expectations are written
in HA_PR_EXPECTATIONS.md (scenarios S7 to S21); they come from the standards,
not from what the kernel does.

Structure. One module fixture (`scenarios`) builds every scenario's target and
puts its reservation state in place through the node that is ACTIVE. Then
classes check the state in the order the module runs them:

  TestPreFailoverOnly    scenarios that need no failover (S7, S11a)
  TestBeforeFailover     the state as built
  TestAfterFailover      after the ACTIVE node is rebooted (S8, S10 to S13,
                         S16 to S21, plus S9 and S15, which change their
                         own targets)
  TestAfterFailback      after the new ACTIVE node is rebooted in turn (S14)

Each client reconnects through the port it used to register ("home" port: the
original ACTIVE node's address or the original STANDBY's), with the same ISID,
so it is the same I_T nexus before and after. The original ACTIVE node's port is
the forwarded STANDBY port once it has failed over.

S7, S9 and S11 need the physical-port identity work of
HA_PHYSICAL_PORT_IDENTITY_DESIGN.md (the ALL_TG_PT registration on the other
node's port, K2 and K1 in HA_PR_EXPECTATIONS.md) and fail without it; they are
not marked.
"""

import contextlib
from dataclasses import dataclass, field
import random
import string
from time import monotonic, sleep

from assets.websocket.iscsi import initiator, portal, target, target_extent_associate, zvol_extent
from assets.websocket.pool import zvol as zvol_dataset
from assets.websocket.service import ensure_service_enabled
from auto_config import ha, pool_name
from iscsi_ua_pr_utils import (
    BASENAME,
    CLIENT_IQN,
    LABEL_B_IQN,
    LABEL_C_IQN,
    LIO_MODE,
    LU_SCOPE,
    SERVICE_NAME,
    UA_WAIT_SECONDS,
    _start_service,
    _stop_service,
    assert_no_ua,
    assert_registrations,
    assert_ua,
    assert_uas,
    drain_ua,
    expect_reservation_conflict,
    expected_access,
    fail_back_to,
    hard_failover,
    holder_flags,
    io_access,
    isid_en_hex,
    open_nexus,
    pr_check_reservation,
    pr_clear,
    pr_preempt,
    pr_register_and_move,
    pr_register_ignore_existing,
    pr_register_key,
    pr_register_spec_i_pt,
    pr_registrations,
    pr_release,
    pr_reserve,
    pr_unregister_key,
    wait_for_alua_settle,
)
from middlewared.test.integration.assets.iscsi import lio_supported
from middlewared.test.integration.utils import call, ssh
from middlewared.test.integration.utils.client import truenas_server
from pyscsi.pyscsi.scsi_cdb_persistentreservein import PR_TYPE
import pytest

pytestmark = pytest.mark.skipif(not ha, reason="PR failover tests require HA hardware")

# Node B's TPG tag for a target is its rel_tgt_id plus this (must match
# middlewared.utils.iscsi.constants.REL_TGT_ID_NODEB_OFFSET).
REL_TGT_ID_NODEB_OFFSET = 32000
# The ALUA target port group ids of the two controllers (as test_266 uses).
CONTROLLER_A_TPG_ID = 101
CONTROLLER_B_TPG_ID = 102
# Asymmetric access state values in REPORT TARGET PORT GROUPS data (SPC-5)
ALUA_OPTIMIZED = 0
ALUA_NONOPTIMIZED = 1
ALUA_UNAVAILABLE = 3
ALUA_TRANSITIONING = 15
# What the ACTIVE node gives the STANDBY group until the STANDBY has synced.
ALUA_STANDBY_SETTLING = (ALUA_UNAVAILABLE, ALUA_TRANSITIONING)
LUN_MB = 20

# Three initiators. N1 is the default pyscsi name; None selects it.
N1, N2, N3 = None, LABEL_B_IQN, LABEL_C_IQN
# ISID qualifiers: a client keeps its qualifier to reconnect as the same
# initiator port, and uses another to be a different one.
Q1, Q2, Q3 = 1, 2, 3
K1, K2, K3 = 0xABCD000000000001, 0xABCD000000000002, 0xABCD000000000003

WE = PR_TYPE.WRITE_EXCLUSIVE
WE_RR = PR_TYPE.WRITE_EXCLUSIVE_REGISTRANTS_ONLY
WE_AR = PR_TYPE.WRITE_EXCLUSIVE_ALL_REGISTRANTS

# Reservation types of S13, with the names the test ids use.
S13_TYPES = [
    ("WE", PR_TYPE.WRITE_EXCLUSIVE),
    ("EA", PR_TYPE.EXCLUSIVE_ACCESS),
    ("WE-RR", PR_TYPE.WRITE_EXCLUSIVE_REGISTRANTS_ONLY),
    ("EA-RR", PR_TYPE.EXCLUSIVE_ACCESS_REGISTRANTS_ONLY),
    ("WE-AR", PR_TYPE.WRITE_EXCLUSIVE_ALL_REGISTRANTS),
    ("EA-AR", PR_TYPE.EXCLUSIVE_ACCESS_ALL_REGISTRANTS),
]
_ALL_REGISTRANTS = (PR_TYPE.WRITE_EXCLUSIVE_ALL_REGISTRANTS, PR_TYPE.EXCLUSIVE_ACCESS_ALL_REGISTRANTS)


# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------


@dataclass
class HaEnv:
    portal: dict
    initiator: dict


@dataclass
class PrTarget:
    iqn: str
    rtpis: tuple  # the two relative target port ids, node A's and node B's


@dataclass
class Scenarios:
    orig_node: str
    act_ip: str  # the original ACTIVE node's address: the "home" port of its clients
    stby_ip: str  # the original STANDBY node's address
    s7: PrTarget | None = None
    s8: PrTarget | None = None
    s9: PrTarget | None = None
    s10: PrTarget | None = None
    s11: PrTarget | None = None
    s11_setup_error: str | None = None
    s12: dict = field(default_factory=dict)
    s13: dict = field(default_factory=dict)
    s15: PrTarget | None = None
    # Set by TestAfterFailover once it has changed S9's and S15's state, for
    # TestAfterFailback to check that the change survived the failback.
    s9_changed_after_failover: bool = False
    s15_changed_after_failover: bool = False
    s16: PrTarget | None = None
    s17: dict = field(default_factory=dict)
    s18: PrTarget | None = None
    s19: PrTarget | None = None
    s20: PrTarget | None = None
    s21: PrTarget | None = None
    s22: PrTarget | None = None


def _tpg_port_ids(tgt_config):
    """(node A's rtpi, node B's rtpi) for a target."""
    rel = tgt_config["rel_tgt_id"]
    return rel, rel + REL_TGT_ID_NODEB_OFFSET


def _node_ips():
    """(address of the ACTIVE node, address of the STANDBY node)."""
    if call("failover.node") == "A":
        return truenas_server.nodea_ip, truenas_server.nodeb_ip
    return truenas_server.nodeb_ip, truenas_server.nodea_ip


@pytest.fixture(scope="module", autouse=True)
def _require_lio():
    if not lio_supported():
        pytest.skip("LIO mode (2) not accepted by API")


@pytest.fixture(scope="module")
def ha_env():
    """LIO mode with ALUA on, one named initiator group (ALUA requires one) with
    the three client names, and a portal. Restores the original configuration,
    failing back first if a failover phase left the other node ACTIVE (for
    example TestAfterFailback deselected, or a failover that raised)."""
    assert call("failover.config")["disabled"] is False
    original = call("iscsi.global.config")
    original_started = call("service.started", SERVICE_NAME)
    original_node = call("failover.node")
    with ensure_service_enabled(SERVICE_NAME):
        _stop_service()
        try:
            call("iscsi.global.update", {"mode": LIO_MODE, "alua": True})
            _start_service()
            wait_for_alua_settle()
            with initiator(initiators=[CLIENT_IQN, LABEL_B_IQN, LABEL_C_IQN]) as init_config:
                with portal() as portal_config:
                    yield HaEnv(portal=portal_config, initiator=init_config)
        finally:
            try:
                fail_back_to(original_node)
            finally:
                _stop_service()
                call("iscsi.global.update", {"mode": original["mode"], "alua": original["alua"]})
                if original_started:
                    _start_service()


@contextlib.contextmanager
def pr_target(env, label):
    """A target with one LUN (zvol + extent), removed again on exit."""
    rnd = "".join(random.choices(string.digits, k=6))
    zvol_path = f"{pool_name}/ds_prf_{label.replace('-', '_')}_{rnd}"
    ext_name = f"ext_prf_{label.replace('-', '_')}_{rnd}"
    with zvol_dataset(zvol_path, LUN_MB):
        with zvol_extent(zvol_path, ext_name) as extent_config:
            groups = [{"portal": env.portal["id"], "initiator": env.initiator["id"]}]
            with target(f"tgt-prf-{label}-{rnd}", groups) as tgt_config:
                with target_extent_associate(tgt_config["id"], extent_config["id"]):
                    yield PrTarget(iqn=f"{BASENAME}:{tgt_config['name']}", rtpis=_tpg_port_ids(tgt_config))


@contextlib.contextmanager
def client(host, tgt, name, qualifier):
    """A session of initiator `name` (None: the default) with ISID `qualifier`
    through `host`'s port, with its pending unit attentions cleared."""
    with open_nexus(host, tgt.iqn, initiator_name=name, qualifier=qualifier) as session:
        drain_ua(session)
        yield session


# ---------------------------------------------------------------------------
# Building the state (through the ACTIVE node, before the first failover)
# ---------------------------------------------------------------------------


def _build_scenarios(env, stack):
    act, stby = _node_ips()
    sc = Scenarios(orig_node=call("failover.node"), act_ip=act, stby_ip=stby)

    def new_target(label):
        return stack.enter_context(pr_target(env, label))

    # S7: registered with ALL_TG_PT=1 through the ACTIVE node's port.
    sc.s7 = new_target("s7")
    with client(act, sc.s7, N1, Q1) as n1:
        pr_register_key(n1, K1, all_tg_pt=True)

    # S8: registered and holding, through the ACTIVE node's port only; a
    # registered non-holder alongside.
    sc.s8 = new_target("s8")
    with client(act, sc.s8, N1, Q1) as n1, client(act, sc.s8, N2, Q2) as n2:
        pr_register_key(n1, K1)
        pr_register_key(n2, K2)
        pr_reserve(n1, WE, K1)

    # S9: registered through the ACTIVE node's port only (ALL_TG_PT=0).
    sc.s9 = new_target("s9")
    with client(act, sc.s9, N1, Q1) as n1:
        pr_register_key(n1, K1)
        pr_reserve(n1, WE, K1)

    # S10: one initiator, two ISIDs, one through each node's port.
    sc.s10 = new_target("s10")
    with client(act, sc.s10, N1, Q1) as a, client(stby, sc.s10, N1, Q2) as b:
        pr_register_key(a, K1)
        pr_register_key(b, K2)
        pr_reserve(a, WE_RR, K1)

    # S11: one initiator port (same name and ISID) towards both nodes' ports.
    # The kernel may refuse the second registration (K1); that is recorded for
    # the S11 tests instead of failing the setup of every other scenario.
    sc.s11 = new_target("s11")
    try:
        with client(act, sc.s11, N1, Q1) as a, client(stby, sc.s11, N1, Q1) as b:
            pr_register_key(a, K1)
            pr_register_key(b, K2)
            pr_reserve(a, WE_RR, K1)
    except Exception as e:
        sc.s11_setup_error = f"{e.__class__.__name__}: {e}"

    # S12: state changed before the failover.
    for kind in ("unreg", "release", "preempt", "clear"):
        tgt = sc.s12[kind] = new_target(f"s12-{kind}")
        with client(act, tgt, N1, Q1) as n1, client(act, tgt, N2, Q2) as n2:
            pr_register_key(n1, K1)
            pr_register_key(n2, K2)
            if kind == "unreg":
                pr_reserve(n1, WE, K1)
                pr_unregister_key(n2, K2)
            elif kind == "release":
                pr_reserve(n1, WE_RR, K1)
                pr_release(n1, WE_RR, K1)
            elif kind == "preempt":
                pr_reserve(n1, WE, K1)
                pr_preempt(n2, WE, K2, K1)
            else:
                pr_reserve(n1, WE, K1)
                pr_clear(n1, K1)

    # S13: every reservation type, held by N1, with N2 registered.
    for index, (_, pr_type) in enumerate(S13_TYPES):
        tgt = sc.s13[pr_type] = new_target(f"s13-{index}")
        with client(act, tgt, N1, Q1) as n1, client(act, tgt, N2, Q2) as n2:
            pr_register_key(n1, K1)
            pr_register_key(n2, K2)
            pr_reserve(n1, pr_type, K1)

    # S15: three registrants, the holder and one other through the ACTIVE
    # node's port and one through the STANDBY node's.
    sc.s15 = new_target("s15")
    with client(act, sc.s15, N1, Q1) as n1, client(stby, sc.s15, N2, Q2) as n2, client(act, sc.s15, N3, Q3) as n3:
        pr_register_key(n1, K1)
        pr_register_key(n2, K2)
        pr_register_key(n3, K3)
        pr_reserve(n1, WE_RR, K1)

    # S16: registered and holding through the STANDBY node's port only; a
    # registered non-holder through the same port.
    sc.s16 = new_target("s16")
    with client(stby, sc.s16, N1, Q1) as n1, client(stby, sc.s16, N2, Q2) as n2:
        pr_register_key(n1, K1)
        pr_register_key(n2, K2)
        pr_reserve(n1, WE, K1)

    # S17: the reservation moved with REGISTER AND MOVE to another ISID of the
    # same initiator, logged in through the same port of the ACTIVE node. The
    # source stays registered, or with UNREG set is unregistered.
    for unreg in (False, True):
        tgt = sc.s17[unreg] = new_target("s17-unreg" if unreg else "s17")
        with client(act, tgt, N1, Q1) as src, client(act, tgt, N1, Q2):
            pr_register_key(src, K1)
            pr_reserve(src, WE, K1)
            rtpi = assert_registrations(src, [(K1, N1, Q1)])[0].rtpi
            pr_register_and_move(src, K1, K2, CLIENT_IQN, isid_en_hex(Q2), rtpi, unreg=unreg)

    # S18 to S21: the PR state left by a PR OUT whose effect on other
    # registrations or on the reservation is more than "the issuer's own
    # registration". The STANDBY node's copy must be that state, not its own
    # reading of the command.

    # S18: N1 registers itself and, with SPEC_I_PT, N2; N1 reserves
    # registrants-only.
    sc.s18 = new_target("s18")
    with client(act, sc.s18, N1, Q1) as n1, client(act, sc.s18, N2, Q2):
        pr_register_spec_i_pt(n1, K1, [(N2, isid_en_hex(Q2))])
        pr_reserve(n1, WE_RR, K1)

    # S19: N1 holds; N3 preempts N2's key, which is not the holder's. N2 is
    # unregistered and N1 keeps the reservation (SPC-5 5.14.11.4.4).
    sc.s19 = new_target("s19")
    with (
        client(act, sc.s19, N1, Q1) as n1,
        client(act, sc.s19, N2, Q2) as n2,
        client(act, sc.s19, N3, Q3) as n3,
    ):
        pr_register_key(n1, K1)
        pr_register_key(n2, K2)
        pr_register_key(n3, K3)
        pr_reserve(n1, WE, K1)
        pr_preempt(n3, WE, K3, K2)

    # S20: N1 reserves all-registrants; N2, also a holder of it, releases it.
    # The reservation is gone (SPC-5 5.14.10, 5.14.11.2.2).
    sc.s20 = new_target("s20")
    with client(act, sc.s20, N1, Q1) as n1, client(act, sc.s20, N2, Q2) as n2:
        pr_register_key(n1, K1)
        pr_register_key(n2, K2)
        pr_reserve(n1, WE_AR, K1)
        pr_release(n2, WE_AR, K2)

    # S21: N1 reserves all-registrants and unregisters. The reservation stays
    # with N2, the remaining registrant (SPC-5 5.14.11.3).
    sc.s21 = new_target("s21")
    with client(act, sc.s21, N1, Q1) as n1, client(act, sc.s21, N2, Q2) as n2:
        pr_register_key(n1, K1)
        pr_register_key(n2, K2)
        pr_reserve(n1, WE_AR, K1)
        pr_unregister_key(n1, K1)

    # S22: registered with ALL_TG_PT=1 through the ACTIVE node's port, then
    # reserved through the STANDBY node's port, so the registration through
    # that port holds the reservation.
    sc.s22 = new_target("s22")
    with client(act, sc.s22, N1, Q1) as via_act, client(stby, sc.s22, N1, Q1) as via_stby:
        pr_register_key(via_act, K1, all_tg_pt=True)
        pr_reserve(via_stby, WE, K1)

    # Nothing on the STANDBY node shows how far PR replication has got, so
    # there is no condition to wait for here.
    sleep(5)  # let the PR state replicate to the STANDBY node
    return sc


@pytest.fixture(scope="module")
def scenarios(ha_env):
    with contextlib.ExitStack() as stack:
        yield _build_scenarios(ha_env, stack)


@pytest.fixture(scope="module")
def failed_over(scenarios):
    """The state after the original ACTIVE node has been rebooted."""
    return hard_failover(scenarios.orig_node)


@pytest.fixture(scope="module")
def failed_back(failed_over, scenarios):
    """The state after the node that took over has been rebooted in turn."""
    back = hard_failover(failed_over)
    assert back == scenarios.orig_node, f"expected {scenarios.orig_node} to become ACTIVE again, got {back}"
    return back


# ---------------------------------------------------------------------------
# What the state must look like (the same in every phase)
# ---------------------------------------------------------------------------


def check_s7(sc):
    """S7: the initiator port registered with ALL_TG_PT=1 is registered through
    both nodes' ports. The same ISID is registered through either port;
    another ISID of the same name is not (SPC-5 6.17.3, RFC 7143 4.4.3)."""
    t = sc.s7
    with (
        client(sc.act_ip, t, N1, Q1) as a,
        client(sc.stby_ip, t, N1, Q1) as b,
        client(sc.act_ip, t, N1, Q2) as other_isid,
        client(sc.act_ip, t, N3, Q3) as observer,
    ):
        regs = pr_registrations(observer)
        assert {(r.key, r.initiator, r.isid) for r in regs} == {(K1, CLIENT_IQN, isid_en_hex(Q1))}, regs
        assert any(r.all_tg_pt for r in regs), regs
        for session in (a, b):
            pr_release(session, WE, K1)  # registered: accepted, nothing to release
        with expect_reservation_conflict(other_isid):
            pr_release(other_isid, WE, K1)


def check_s8(sc):
    """S8: the holder reconnects through the same port with the same ISID and is
    still the holder; the registered non-holder and an unregistered initiator
    get the access SPC-5 table 66 gives them under WRITE EXCLUSIVE."""
    t = sc.s8
    with client(sc.act_ip, t, N1, Q1) as n1, client(sc.act_ip, t, N2, Q2) as n2, client(sc.act_ip, t, N3, Q3) as n3:
        regs = assert_registrations(n3, [(K1, N1, Q1), (K2, N2, Q2)])
        assert holder_flags(regs) == {K1: True, K2: False}, regs
        pr_check_reservation(n3, {"reservation_key": K1, "type": WE, "scope": LU_SCOPE})
        assert io_access(n1) == expected_access(WE, "holder")
        assert io_access(n2) == expected_access(WE, "registered")
        assert io_access(n3) == expected_access(WE, "unregistered")


def check_rtpg(sc, retries=12):
    """REPORT TARGET PORT GROUPS, through either node's port, lists both
    controllers' groups with their relative target port ids; the group of the
    node that is ACTIVE now is ACTIVE/OPTIMIZED and the other
    ACTIVE/NON-OPTIMIZED.

    The STANDBY group passes through UNAVAILABLE or TRANSITIONING until the
    STANDBY node has synced and the ACTIVE node has been told, so those states
    are retried for a while. Any other wrong state fails at once: in
    particular the STANDBY group reported ACTIVE/OPTIMIZED, which is what the
    new ACTIVE node reported before it learned to rewrite the peer's group on
    takeover."""
    t = sc.s8
    rtpi_a, rtpi_b = t.rtpis
    ports = {CONTROLLER_A_TPG_ID: {rtpi_a}, CONTROLLER_B_TPG_ID: {rtpi_b}}
    active_group = CONTROLLER_A_TPG_ID if call("failover.node") == "A" else CONTROLLER_B_TPG_ID
    for host in (sc.act_ip, sc.stby_ip):
        for attempt in range(retries + 1):
            with client(host, t, N3, Q3) as session:
                descriptors = session.conn.reporttargetportgroups().result["target_port_group_descriptors"]
            assert {d["target_port_group"] for d in descriptors} == set(ports), (host, descriptors)
            transient = False
            for d in descriptors:
                gid = d["target_port_group"]
                got = {p["relative_target_port_id"] for p in d["target_ports"]}
                assert got == ports[gid], f"{host}: group {gid} ports {got!r} != {ports[gid]!r}"
                expected = ALUA_OPTIMIZED if gid == active_group else ALUA_NONOPTIMIZED
                state = d["asymmetric_access_state"]
                if gid != active_group and state in ALUA_STANDBY_SETTLING and attempt < retries:
                    transient = True
                    continue
                assert state == expected, f"{host}: group {gid} state {state!r} != {expected!r}"
            if not transient:
                break
            sleep(5)


def check_s16(sc):
    """S16: registered and holding through the STANDBY node's port (the
    registration is forwarded to the ACTIVE node). The holder through that same
    port is still the holder, a registered non-holder through it keeps its
    access, and the holder's name and ISID through the other port is not the
    registrant there."""
    t = sc.s16
    with (
        client(sc.stby_ip, t, N1, Q1) as n1,
        client(sc.stby_ip, t, N2, Q2) as n2,
        client(sc.act_ip, t, N1, Q1) as n1_other_port,
        client(sc.act_ip, t, N3, Q3) as n3,
    ):
        regs = assert_registrations(n3, [(K1, N1, Q1), (K2, N2, Q2)])
        assert holder_flags(regs) == {K1: True, K2: False}, regs
        pr_check_reservation(n3, {"reservation_key": K1, "type": WE, "scope": LU_SCOPE})
        assert io_access(n1) == expected_access(WE, "holder")
        assert io_access(n2) == expected_access(WE, "registered")
        assert io_access(n1_other_port) == expected_access(WE, "unregistered")


def check_s17(sc, unreg):
    """S17: REGISTER AND MOVE registers the initiator port named by the
    TransportID, name and ISID, and makes it the holder (SPC-5 5.14.8). That
    is the nexus that holds the reservation after a failover, too: another
    ISID of the same name is neither registered nor the holder (RFC 7143
    4.4.3). The source keeps its registration, unless UNREG was set, in
    which case it stays unregistered."""
    t = sc.s17[unreg]
    with (
        client(sc.act_ip, t, N1, Q1) as src,
        client(sc.act_ip, t, N1, Q2) as dest,
        client(sc.act_ip, t, N1, Q3) as other_isid,
        client(sc.act_ip, t, N3, Q3) as observer,
    ):
        if unreg:
            regs = assert_registrations(observer, [(K2, N1, Q2)])
            assert holder_flags(regs) == {K2: True}, regs
        else:
            regs = assert_registrations(observer, [(K1, N1, Q1), (K2, N1, Q2)])
            assert holder_flags(regs) == {K1: False, K2: True}, regs
        pr_check_reservation(observer, {"reservation_key": K2, "type": WE, "scope": LU_SCOPE})
        assert io_access(dest) == expected_access(WE, "holder")
        assert io_access(src) == expected_access(WE, "unregistered" if unreg else "registered")
        assert io_access(other_isid) == expected_access(WE, "unregistered")
        if unreg:
            # Not the holder either way, so this changes nothing if it is
            # (wrongly) still registered.
            with expect_reservation_conflict(src):
                pr_release(src, WE, K1)


def check_s18(sc):
    """S18: the initiator port SPEC_I_PT named is registered, with the
    issuer's key, and has a registered nexus's access to the issuer's
    registrants-only reservation; another ISID of the same name does not."""
    t = sc.s18
    with (
        client(sc.act_ip, t, N1, Q1) as n1,
        client(sc.act_ip, t, N2, Q2) as n2,
        client(sc.act_ip, t, N2, Q3) as n2_other_isid,
    ):
        regs = assert_registrations(n2_other_isid, [(K1, N1, Q1), (K1, N2, Q2)])
        assert [(r.initiator, r.isid) for r in regs if r.holder] == [(CLIENT_IQN, isid_en_hex(Q1))], regs
        pr_check_reservation(n2_other_isid, {"reservation_key": K1, "type": WE_RR, "scope": LU_SCOPE})
        assert io_access(n1) == expected_access(WE_RR, "holder")
        assert io_access(n2) == expected_access(WE_RR, "registered")
        assert io_access(n2_other_isid) == expected_access(WE_RR, "unregistered")


def check_s19(sc):
    """S19: the preempted key's registration is gone, and the reservation is
    still the original holder's, not the preemptor's."""
    t = sc.s19
    with (
        client(sc.act_ip, t, N1, Q1) as n1,
        client(sc.act_ip, t, N2, Q2) as n2,
        client(sc.act_ip, t, N3, Q3) as n3,
    ):
        regs = assert_registrations(n2, [(K1, N1, Q1), (K3, N3, Q3)])
        assert holder_flags(regs) == {K1: True, K3: False}, regs
        pr_check_reservation(n2, {"reservation_key": K1, "type": WE, "scope": LU_SCOPE})
        assert io_access(n1) == expected_access(WE, "holder")
        assert io_access(n3) == expected_access(WE, "registered")
        assert io_access(n2) == expected_access(WE, "unregistered")


def check_s20(sc):
    """S20: both registrations remain and there is no reservation."""
    t = sc.s20
    with client(sc.act_ip, t, N3, Q3) as n3:
        assert_registrations(n3, [(K1, N1, Q1), (K2, N2, Q2)])
        pr_check_reservation(n3)
        assert io_access(n3) == (True, True)


def check_s21(sc):
    """S21: only N2 is registered, and the all-registrants reservation is
    still in place: N2 has a holder's access, the unregistered N1 that of an
    unregistered nexus."""
    t = sc.s21
    with client(sc.act_ip, t, N1, Q1) as n1, client(sc.act_ip, t, N2, Q2) as n2:
        assert_registrations(n1, [(K2, N2, Q2)])
        pr_check_reservation(n1, {"type": WE_AR, "scope": LU_SCOPE})
        assert io_access(n2) == expected_access(WE_AR, "holder")
        assert io_access(n1) == expected_access(WE_AR, "unregistered")


def check_s22(sc):
    """S22: an ALL_TG_PT registrant that reserved through another port than it
    registered through still holds the reservation through that port: READ
    FULL STATUS flags the registration through the original STANDBY node's
    port, the I_T nexus through that port can write, and the one through the
    original ACTIVE node's port is a registered non-holder (SPC-5 6.17.3,
    table 66). A failover that put the reservation back on the port the
    registrant registered through would swap the two."""
    t = sc.s22
    rtpi_a, rtpi_b = t.rtpis
    stby_rtpi = rtpi_b if sc.orig_node == "A" else rtpi_a
    with (
        client(sc.act_ip, t, N1, Q1) as via_act,
        client(sc.stby_ip, t, N1, Q1) as via_stby,
        client(sc.act_ip, t, N3, Q3) as observer,
    ):
        regs = pr_registrations(observer)
        assert {r.rtpi for r in regs if r.holder} == {stby_rtpi}, regs
        pr_check_reservation(observer, {"reservation_key": K1, "type": WE, "scope": LU_SCOPE})
        assert io_access(via_stby) == expected_access(WE, "holder")
        assert io_access(via_act) == expected_access(WE, "registered")
        assert io_access(observer) == expected_access(WE, "unregistered")


def check_s10(sc):
    """S10: both registrations, made through different ports with different
    ISIDs, are present, and each works through its own port."""
    t = sc.s10
    with (
        client(sc.act_ip, t, N1, Q1) as a,
        client(sc.stby_ip, t, N1, Q2) as b,
        client(sc.act_ip, t, N3, Q3) as other,
    ):
        regs = assert_registrations(other, [(K1, N1, Q1), (K2, N1, Q2)])
        assert holder_flags(regs) == {K1: True, K2: False}, regs
        assert io_access(a) == expected_access(WE_RR, "holder")
        assert io_access(b) == expected_access(WE_RR, "registered")
        assert io_access(other) == expected_access(WE_RR, "unregistered")


def check_s11(sc):
    """S11: the same initiator port, registered through both ports, has two
    registrations, one per target port, and both work."""
    assert sc.s11_setup_error is None, f"setting up the two registrations failed: {sc.s11_setup_error}"
    t = sc.s11
    with (
        client(sc.act_ip, t, N1, Q1) as a,
        client(sc.stby_ip, t, N1, Q1) as b,
        client(sc.act_ip, t, N3, Q3) as other,
    ):
        regs = assert_registrations(other, [(K1, N1, Q1), (K2, N1, Q1)])
        assert {r.rtpi for r in regs} == set(t.rtpis), regs
        assert io_access(a) == expected_access(WE_RR, "holder")
        assert io_access(b) == expected_access(WE_RR, "registered")


_S12_EXPECTED = {
    # kind: (registrations, reservation)
    "unreg": ([(K1, N1, Q1)], {"reservation_key": K1, "type": WE, "scope": LU_SCOPE}),
    "release": ([(K1, N1, Q1), (K2, N2, Q2)], None),
    "preempt": ([(K2, N2, Q2)], {"reservation_key": K2, "type": WE, "scope": LU_SCOPE}),
    "clear": ([], None),
}


def check_s12(sc, kind):
    """S12: the state left by an unregister, a release, a preempt or a clear is
    what the failover carries: nothing resurrected, nothing lost."""
    registrations, reservation = _S12_EXPECTED[kind]
    with client(sc.act_ip, sc.s12[kind], N3, Q3) as observer:
        assert_registrations(observer, registrations)
        pr_check_reservation(observer, reservation)


def check_s13(sc, pr_type):
    """S13: after the failover the holder, a registered non-holder and an
    unregistered initiator get the access SPC-5 tables 66 and 67 give them under
    this reservation type, whichever port they use."""
    t = sc.s13[pr_type]
    with (
        client(sc.act_ip, t, N1, Q1) as holder,
        client(sc.act_ip, t, N2, Q2) as registered,
        client(sc.act_ip, t, N3, Q3) as unregistered,
        client(sc.stby_ip, t, N3, Q3) as unregistered_other_port,
    ):
        regs = assert_registrations(unregistered, [(K1, N1, Q1), (K2, N2, Q2)])
        if pr_type in _ALL_REGISTRANTS:
            # Every registrant is a reservation holder (SPC-5 5.14.10.2).
            assert holder_flags(regs) == {K1: True, K2: True}, regs
            pr_check_reservation(unregistered, {"type": pr_type, "scope": LU_SCOPE})
        else:
            assert holder_flags(regs) == {K1: True, K2: False}, regs
            pr_check_reservation(unregistered, {"reservation_key": K1, "type": pr_type, "scope": LU_SCOPE})
        assert io_access(holder) == expected_access(pr_type, "holder")
        assert io_access(registered) == expected_access(pr_type, "registered")
        assert io_access(unregistered) == expected_access(pr_type, "unregistered")
        assert io_access(unregistered_other_port) == expected_access(pr_type, "unregistered")


def check_s15_after_preempt(observer):
    """S15 after the PREEMPT that follows the failover: K1's registration is
    gone and K2 holds the registrants-only reservation."""
    regs = assert_registrations(observer, [(K2, N2, Q2), (K3, N3, Q3)])
    assert holder_flags(regs) == {K2: True, K3: False}, regs
    pr_check_reservation(observer, {"reservation_key": K2, "type": WE_RR, "scope": LU_SCOPE})


class _StateChecks:
    """The checks every phase runs; subclasses provide the `stage` fixture."""

    def test_rtpg_reports_the_active_group(self, stage):
        check_rtpg(stage)

    def test_s7_all_tg_pt_registered_through_both_ports(self, stage):
        check_s7(stage)

    def test_s8_holder_through_the_same_port(self, stage):
        check_s8(stage)

    def test_s16_holder_registered_through_the_standby_port(self, stage):
        check_s16(stage)

    @pytest.mark.parametrize("unreg", [False, True], ids=["keep-source", "unreg"])
    def test_s17_register_and_move_keeps_the_destination_isid(self, unreg, stage):
        check_s17(stage, unreg)

    def test_s18_spec_i_pt_registration(self, stage):
        check_s18(stage)

    def test_s19_preempt_of_a_non_holder_key(self, stage):
        check_s19(stage)

    def test_s20_release_of_an_all_registrants_reservation(self, stage):
        check_s20(stage)

    def test_s21_all_registrants_holder_unregisters(self, stage):
        check_s21(stage)

    def test_s22_all_tg_pt_reserved_through_another_port(self, stage):
        check_s22(stage)

    def test_s10_two_isids_through_two_ports(self, stage):
        check_s10(stage)

    def test_s11_same_isid_through_two_ports(self, stage):
        check_s11(stage)

    @pytest.mark.parametrize("kind", list(_S12_EXPECTED))
    def test_s12_state_changes_before_failover(self, kind, stage):
        check_s12(stage, kind)

    @pytest.mark.parametrize("pr_type", [t for _, t in S13_TYPES], ids=[n for n, _ in S13_TYPES])
    def test_s13_access_by_reservation_type(self, pr_type, stage):
        check_s13(stage, pr_type)


# ---------------------------------------------------------------------------
# Scenarios that need no failover
# ---------------------------------------------------------------------------


class TestPreFailoverOnly:
    def test_s7_all_tg_pt_registers_the_initiator_port_on_every_port(self, ha_env):
        """S7: ALL_TG_PT=1 registers the initiator port (name + ISID) through
        every target port, as if the REGISTER had arrived through each (SPC-5
        6.17.3). The same ISID through the other port is registered; another ISID
        of the same name is not. Fails without the ALL_TG_PT registration on the
        other node's port."""
        act, stby = _node_ips()
        with pr_target(ha_env, "s7") as t:
            with client(act, t, N1, Q1) as n1:
                pr_register_key(n1, K1, all_tg_pt=True)
                regs = pr_registrations(n1)
                assert {(r.key, r.initiator, r.isid) for r in regs} == {(K1, CLIENT_IQN, isid_en_hex(Q1))}, regs
                assert any(r.all_tg_pt for r in regs), regs
            with client(stby, t, N1, Q1) as same_isid:
                pr_release(same_isid, WE, K1)  # registered: accepted, nothing to release
            with client(stby, t, N1, Q2) as other_isid:
                with expect_reservation_conflict(other_isid):
                    pr_release(other_isid, WE, K1)

    def test_s7_all_tg_pt_through_the_standby_port(self, ha_env):
        """S7, registered through the STANDBY node's port: the initiator port is
        registered through the ACTIVE node's port as well. Same checks as
        test_s7_all_tg_pt_registers_the_initiator_port_on_every_port."""
        act, stby = _node_ips()
        with pr_target(ha_env, "s7s") as t:
            with client(stby, t, N1, Q1) as n1:
                pr_register_key(n1, K1, all_tg_pt=True)
            with (
                client(act, t, N1, Q1) as same_isid,
                client(act, t, N1, Q2) as other_isid,
                client(act, t, N3, Q3) as observer,
            ):
                regs = pr_registrations(observer)
                assert {(r.key, r.initiator, r.isid) for r in regs} == {(K1, CLIENT_IQN, isid_en_hex(Q1))}, regs
                assert any(r.all_tg_pt for r in regs), regs
                pr_release(same_isid, WE, K1)  # registered: accepted, nothing to release
                with expect_reservation_conflict(other_isid):
                    pr_release(other_isid, WE, K1)

    def test_s7_preempt_with_own_key_removes_the_registration_on_every_port(self, ha_env):
        """S7: PREEMPT whose RESERVATION KEY and SERVICE ACTION RESERVATION KEY
        are the same removes every registration with that key, here the initiator
        port's registrations through both nodes' ports (SPC-5 5.14.11.2.5). The
        I_T nexus that issued it gets no unit attention; the other nexus that
        lost its registration gets REGISTRATIONS PREEMPTED."""
        act, stby = _node_ips()
        with pr_target(ha_env, "s7p") as t:
            with (
                client(act, t, N1, Q1) as via_act,
                client(stby, t, N1, Q1) as via_stby,
                client(act, t, N3, Q3) as observer,
            ):
                pr_register_key(via_act, K1, all_tg_pt=True)
                pr_preempt(via_stby, WE, K1, K1)
                assert_registrations(observer, [])
                assert_no_ua(via_stby)
                assert_uas(via_act, [(0x2A, 0x05)])
                for session in (via_act, via_stby):
                    with expect_reservation_conflict(session):
                        pr_release(session, WE, K1)

    def test_s7_all_tg_pt_registers_a_nexus_already_logged_in_on_the_other_port(self, ha_env):
        """S7, with the initiator port already logged in through the STANDBY
        node's port when it registers with ALL_TG_PT=1 through the ACTIVE
        node's: the nexus through the STANDBY port is registered from then on,
        without logging in again. Under a registrants-only reservation held
        through the ACTIVE port it has the access of a registered non-holder,
        and another ISID of the same name through the STANDBY port has that of
        an unregistered one (SPC-5 6.17.3, table 66)."""
        act, stby = _node_ips()
        with pr_target(ha_env, "s7l") as t:
            with (
                client(act, t, N1, Q1) as via_act,
                client(stby, t, N1, Q1) as via_stby,
                client(stby, t, N1, Q2) as other_isid,
            ):
                pr_register_key(via_act, K1, all_tg_pt=True)
                pr_reserve(via_act, WE_RR, K1)
                assert io_access(via_stby) == expected_access(WE_RR, "registered")
                assert io_access(other_isid) == expected_access(WE_RR, "unregistered")

    @pytest.mark.parametrize("other_registrant", [False, True], ids=["last-registrant", "other-registrant-stays"])
    def test_s7_all_tg_pt_holder_unregisters_from_an_all_registrants_reservation(self, other_registrant, ha_env):
        """S7: an initiator port registered with ALL_TG_PT=1 reserves EXCLUSIVE
        ACCESS - ALL REGISTRANTS, then unregisters. Its registrations through
        both nodes' ports go. If another I_T nexus is still registered, the
        reservation stays and that nexus holds it; otherwise the reservation is
        released (SPC-5 5.14.10, 5.14.11.3). Without the kernel fix the
        reservation passes to the registration through the other node's port,
        which the UNREGISTER then frees: the device keeps reporting, and
        enforcing, a reservation nobody holds."""
        ea_ar = PR_TYPE.EXCLUSIVE_ACCESS_ALL_REGISTRANTS
        act, stby = _node_ips()
        with pr_target(ha_env, "s7uo" if other_registrant else "s7ul") as t:
            with (
                client(act, t, N1, Q1) as n1,
                client(act, t, N3, Q3) as n3,
                client(stby, t, N1, Q1) as n1_other_port,
            ):
                pr_register_key(n1, K1, all_tg_pt=True)
                if other_registrant:
                    pr_register_key(n3, K3)  # after the other port's registration on the list
                pr_reserve(n1, ea_ar, K1)
                pr_unregister_key(n1, K1, all_tg_pt=True)

                if other_registrant:
                    assert_registrations(n3, [(K3, N3, Q3)])
                    pr_check_reservation(n3, {"type": ea_ar, "scope": LU_SCOPE})
                    assert io_access(n3) == expected_access(ea_ar, "holder")
                    assert io_access(n1) == expected_access(ea_ar, "unregistered")
                    assert io_access(n1_other_port) == expected_access(ea_ar, "unregistered")
                else:
                    assert_registrations(n3, [])
                    pr_check_reservation(n3)
                    for session in (n1, n3, n1_other_port):
                        assert io_access(session) == (True, True)

    def test_s11_same_isid_registers_once_per_port(self, ha_env):
        """S11, before any failover: the same initiator port through both ports
        is two I_T nexuses with two registrations (RFC 7143 4.4.3), and
        unregistering one leaves the other."""
        act, stby = _node_ips()
        with pr_target(ha_env, "s11a") as t:
            with client(act, t, N1, Q1) as a, client(stby, t, N1, Q1) as b:
                pr_register_key(a, K1)
                pr_register_key(b, K2)
                regs = assert_registrations(a, [(K1, N1, Q1), (K2, N1, Q1)])
                assert {r.rtpi for r in regs} == set(t.rtpis), regs
                pr_unregister_key(b, K2)
                assert_registrations(a, [(K1, N1, Q1)])


# ---------------------------------------------------------------------------
# Deleting an ACL on the ACTIVE node while the initiator uses the STANDBY's port
# ---------------------------------------------------------------------------

# Seconds the ACTIVE node may take to delete an ACL, or to recreate it.
ACL_CHANGE_TIMEOUT = 60


def _acl_dirs(target_iqn, initiator_name):
    """Shell glob for `initiator_name`'s ACL in every TPG of `target_iqn`."""
    return f"/sys/kernel/config/target/iscsi/{target_iqn}/tpgt_*/acls/{initiator_name}"


def _acl_count(host, acls):
    return int(ssh(f"ls -d {acls} 2>/dev/null | wc -l", ip=host).strip())


def _wait_for_acl_count(host, acls, done, what):
    deadline = monotonic() + ACL_CHANGE_TIMEOUT
    while not done(_acl_count(host, acls)):
        assert monotonic() < deadline, f"{what} on {host} not done after {ACL_CHANGE_TIMEOUT}s"
        sleep(1)


def _delete_acls_in_background(host, acls):
    """Delete the ACLs matching `acls` in LIO configfs on `host`, each
    mapped LUN first, without waiting: on a kernel without the fix the
    rmdir blocks."""
    script = (
        f'for acl in {acls}; do [ -d "$acl" ] || continue; '
        'for m in "$acl"/lun_*; do [ -d "$m" ] || continue; '
        'for l in "$m"/*; do [ -L "$l" ] && unlink "$l"; done; rmdir "$m"; done; '
        'rmdir "$acl"; done'
    )
    ssh(f"nohup sh -c '{script}' >/dev/null 2>&1 &", ip=host)


class TestAclDeletionOnActive:
    def test_acl_deletion_does_not_wait_for_a_session_through_the_standby(self, ha_env):
        """Deleting an initiator's ACL on the ACTIVE node while the initiator
        is logged in through the STANDBY node's port completes at once: the
        session the ACTIVE node keeps for the forwarded initiator is removed
        first, instead of the deletion waiting for the initiator to log out
        of the STANDBY.

        The ACL is deleted in configfs directly, as a reload does when it
        reaches the ACTIVE node before the STANDBY; deleting a target
        through the API handles the STANDBY first. Without the fix the
        deletion stays blocked until leaving the session's `with` block
        logs it out, so a failure cleans up after itself.

        A reload then recreates the ACL, and a new session through the
        STANDBY works."""
        act, stby = _node_ips()
        with pr_target(ha_env, "acl-del") as t:
            acls = _acl_dirs(t.iqn, N2)
            with client(stby, t, N2, Q1) as via_stby:
                # Forwarded, so the ACTIVE node has built its session.
                via_stby.conn.testunitready()
                assert _acl_count(act, acls) > 0, f"no ACL for {N2} on the ACTIVE node"
                _delete_acls_in_background(act, acls)
                _wait_for_acl_count(act, acls, lambda n: n == 0, "ACL deletion")

            call("service.control", "RELOAD", SERVICE_NAME, job=True)
            _wait_for_acl_count(act, acls, lambda n: n > 0, "ACL recreation")
            with client(stby, t, N2, Q2) as fresh:
                fresh.conn.testunitready()


# ---------------------------------------------------------------------------
# The three phases
# ---------------------------------------------------------------------------


class TestBeforeFailover(_StateChecks):
    @pytest.fixture
    def stage(self, scenarios):
        return scenarios


class TestAfterFailover(_StateChecks):
    @pytest.fixture
    def stage(self, scenarios, failed_over):
        return scenarios

    def test_s9_same_isid_through_the_other_port_is_not_the_registrant(self, stage):
        """S9: registered through one node's port (ALL_TG_PT=0). After the
        failover the same name and ISID through the *other* node's port is a
        different I_T nexus and not registered: PR OUT gets RESERVATION
        CONFLICT, and REGISTER AND IGNORE EXISTING KEY registers it."""
        t = stage.s9
        with client(stage.stby_ip, t, N1, Q1) as n1:
            with expect_reservation_conflict(n1):
                pr_release(n1, WE, K1)
            pr_register_ignore_existing(n1, K2)
            assert_registrations(n1, [(K1, N1, Q1), (K2, N1, Q1)])
        stage.s9_changed_after_failover = True

    def test_s15_unit_attentions_for_events_after_failover(self, stage):
        """S15: PR events after the failover notify each I_T nexus as SPC-5
        requires. The holder releasing a registrants-only reservation gives every
        other registrant RESERVATIONS RELEASED (5.14.11.2.2). A PREEMPT of the
        holder's key with the same type gives the victim REGISTRATIONS PREEMPTED
        and nobody else a unit attention (5.14.11.2.4), removes the victim's
        registration and makes the preemptor the holder."""
        t = stage.s15
        with (
            client(stage.act_ip, t, N1, Q1) as n1,
            client(stage.stby_ip, t, N2, Q2) as n2,
            client(stage.act_ip, t, N3, Q3) as n3,
        ):
            assert_registrations(n3, [(K1, N1, Q1), (K2, N2, Q2), (K3, N3, Q3)])

            pr_release(n1, WE_RR, K1)
            assert_ua(n2, 0x2A, 0x04, timeout=UA_WAIT_SECONDS)
            assert_ua(n3, 0x2A, 0x04, timeout=UA_WAIT_SECONDS)
            assert_no_ua(n1)
            pr_check_reservation(n3)

            pr_reserve(n1, WE_RR, K1)
            pr_preempt(n2, WE_RR, K2, K1)
            assert_ua(n1, 0x2A, 0x05, timeout=UA_WAIT_SECONDS)
            assert_no_ua(n2)
            assert_no_ua(n3)
            check_s15_after_preempt(n3)
        stage.s15_changed_after_failover = True


class TestAfterFailback(_StateChecks):
    @pytest.fixture
    def stage(self, scenarios, failed_back):
        return scenarios

    def test_s9_registration_made_after_failover_survives_failback(self, stage):
        """S9, after the failback: the registration made through the other
        node's port after the failover is still there, alongside the original
        one. Each I_T nexus has its own key: RELEASE with it gets GOOD (the
        holder ends the reservation, the non-holder changes nothing), where a
        wrong key would get RESERVATION CONFLICT."""
        if not stage.s9_changed_after_failover:
            pytest.skip("TestAfterFailover's S9 test did not run")
        t = stage.s9
        with client(stage.act_ip, t, N1, Q1) as via_act, client(stage.stby_ip, t, N1, Q1) as via_stby:
            regs = assert_registrations(via_act, [(K1, N1, Q1), (K2, N1, Q1)])
            assert holder_flags(regs) == {K1: True, K2: False}, regs
            pr_check_reservation(via_act, {"reservation_key": K1, "type": WE, "scope": LU_SCOPE})
            pr_release(via_stby, WE, K2)
            pr_check_reservation(via_act, {"reservation_key": K1, "type": WE, "scope": LU_SCOPE})
            pr_release(via_act, WE, K1)
            pr_check_reservation(via_act)

    def test_s15_preempt_after_failover_survives_failback(self, stage):
        """S15, after the failback: the PREEMPT made after the failover still
        holds."""
        if not stage.s15_changed_after_failover:
            pytest.skip("TestAfterFailover's S15 test did not run")
        with client(stage.act_ip, stage.s15, N3, Q3) as n3:
            check_s15_after_preempt(n3)
