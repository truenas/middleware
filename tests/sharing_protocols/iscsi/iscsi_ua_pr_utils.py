"""
Shared helpers for test_267_iscsi_ua_pr_per_nexus.py,
test_268_iscsi_pr_identity.py and test_269_iscsi_pr_failover.py, plus
hard_failover() for test_266_iscsi_lio_alua.py.

Not imported by test_261_iscsi_cmd.py -- that file keeps its own,
differently-shaped PR helpers. See UA_PR_TEST_SUITE_PLAN.md for the design
rationale.
"""

import contextlib
from dataclasses import dataclass
import re
import socket
import threading
from time import monotonic, sleep

from assets.websocket.iscsi import target_extent_associate, zvol_extent
from assets.websocket.pool import zvol as zvol_dataset
from middlewared.test.integration.utils import call, ssh
from middlewared.test.integration.utils.client import truenas_server
from protocols import iscsi_scsi_connection
from pyscsi.pyscsi.scsi_cdb_persistentreservein import PR_SCOPE, PR_TYPE
from pyscsi.pyscsi.scsi_enum_persistentreserve import PROTOCOL_ID

LU_SCOPE = PR_SCOPE.LU_SCOPE

MB = 1024 * 1024
SERVICE_NAME = "iscsitarget"
LIO_MODE = 2
BASENAME = "iqn.2005-10.org.freenas.ctl"

# Identity-topology labels. "A" is the default pyscsi client identity (no
# initiator_name override); "B" is a fixed alternate identity. Sessions
# sharing a label share this IQN too (distinct ISID each, for free) --
# see open_topology().
CLIENT_IQN = f"iqn.2018-01.org.pyscsi:{socket.gethostname()}"
LABEL_B_IQN = f"{CLIENT_IQN}:ua-pr-b"
LABEL_C_IQN = f"{CLIENT_IQN}:ua-pr-c"
LABEL_INITIATOR_NAMES = {"A": None, "B": LABEL_B_IQN}

# Enterprise number used in every ISID the tests set explicitly: the IANA
# Private Enterprise Number of iXsystems (TrueNAS). Only the qualifier
# distinguishes one initiator port from another.
TEST_ISID_EN = 50536


def isid_en_context(qualifier, en=TEST_ISID_EN):
    """
    Return the context_params that make a session log in with ISID
    (en, qualifier), for iscsi_scsi_connection(context_params=...).
    Using the same qualifier again reconnects as the same initiator port.
    Passing a different `en` changes the leading bytes of the ISID, not just
    the trailing qualifier.
    """
    return {"isid_en": (en, qualifier)}


def isid_en_hex(qualifier, en=TEST_ISID_EN):
    """
    The 12 hex digits of the ISID that isid_en_context(qualifier, en)
    produces, as the target reports it in a TransportID (lower case). RFC
    7143 11.12.5: T=01b (EN format), B and C = enterprise number, D = 16-bit
    qualifier.
    """
    assert 0 <= qualifier <= 0xFFFF, qualifier
    return f"{(0x40 << 40) | (en << 16) | qualifier:012x}"


TOPO_SAME_IDENTITY = ("A", "A")
TOPO_DIFF_IDENTITY = ("A", "B")
TOPO_MIXED = ("A", "A", "B")

IBLOCK_BASE = "/sys/kernel/config/target/core/iblock_0"

# From drivers/target/target_core_alua.h
ALUA_ACCESS_STATE_ACTIVE_OPTIMIZED = 0x0
ALUA_ACCESS_STATE_ACTIVE_NON_OPTIMIZED = 0x1

# From enum target_ua_intlck_ctrl, drivers/target/target_core_base.h
UA_INTLCK_CTRL_VALUES = {"CLEAR": 0, "NO_CLEAR": 1, "ESTABLISH_UA": 2}


# ---------------------------------------------------------------------------
# LIO mode / service helpers
# ---------------------------------------------------------------------------


def _stop_service():
    call("service.control", "STOP", SERVICE_NAME, job=True)


def _start_service():
    call("service.control", "START", SERVICE_NAME, job=True)


def wait_for_alua_settle(retries=36):
    """Wait for iscsi.alua.settled, failing if it never is: a test that goes
    on with ALUA still moving fails later with a misleading assertion."""
    sleep(5)
    while retries:
        if call("iscsi.alua.settled"):
            return
        retries -= 1
        sleep(5)
    raise AssertionError("ALUA did not settle")


@contextlib.contextmanager
def keep_alive(sessions, interval=5):
    """Send INQUIRY on each session every `interval` seconds while the block
    runs. libiscsi services its socket only during a command, so an idle
    session never answers LIO's NOP-Ins; after about 45s LIO drops it, and
    libiscsi silently reconnects on the next command with a new session,
    losing every UA queued on the old one. INQUIRY bypasses the UA check and
    neither reports nor clears a UA (target_core_ua.c).

    The block must not use the sessions itself: libiscsi contexts are not
    thread-safe. The pinging thread has stopped by the time the block exits."""
    stop = threading.Event()
    errors = []

    def ping():
        while not stop.wait(interval):
            for s in sessions:
                try:
                    s.conn.inquiry()
                except Exception as e:
                    errors.append(e)

    t = threading.Thread(target=ping, daemon=True)
    t.start()
    try:
        yield
    finally:
        stop.set()
        t.join()
    assert not errors, f"keep-alive INQUIRY failed: {errors}"


def hard_failover(old_node):
    """Reboot the ACTIVE node and wait for the other to take over and for the
    rebooted one to return as STANDBY. Returns the new ACTIVE node's name."""
    try:
        call("system.reboot", "failover test")
    except Exception:
        pass  # the connection drops before the reply
    new_node = None
    for _ in range(60):
        try:
            node = call("failover.node")
            if node != old_node and call("failover.status") == "MASTER":
                new_node = node
                break
        except Exception:
            pass
        sleep(10)
    assert new_node is not None, "failover did not complete within the timeout"
    for _ in range(30):
        try:
            if not call("failover.in_progress"):
                break
        except Exception:
            pass
        sleep(10)
    for _ in range(120):
        try:
            if not call("failover.disabled.reasons"):
                break
        except Exception:
            pass
        sleep(10)
    # iscsi.alua.settled can be true before the returning STANDBY has even
    # queued standby_after_start, which is what moves the ACTIVE node's view
    # of the STANDBY group to ACTIVE/NON-OPTIMIZED. In LIO mode with ALUA,
    # wait for the lio_ha link that job waits for, then for the job itself.
    if call("iscsi.global.lio_enabled") and call("iscsi.global.alua_enabled"):
        for _ in range(60):
            try:
                if call("failover.call_remote", "iscsi.lio.ha_state") == "synced":
                    break
            except Exception:
                pass
            sleep(5)
        else:
            raise AssertionError("lio_ha on the STANDBY node did not reach 'synced'")
    wait_for_alua_settle()
    return new_node


def node_b_toggles_drop_sessions():
    """True if toggling ALUA would drop the open sessions: node B is ACTIVE.

    Under ALUA node B's TPG tag is rel_tgt_id + REL_TGT_ID_NODEB_OFFSET.
    Toggling ALUA on node B therefore renumbers the live TPG: the
    reconciler deletes it (or keeps it as node A's phantom, without ACLs)
    and creates the other, dropping every session and its queued UAs.  On
    node A the tag does not change."""
    return call("failover.node") != "A"


def fail_back_to(node):
    """Make `node` ACTIVE again if a failover left the other node ACTIVE.
    For fixture teardown: run it in a `finally`, so that a failed or
    deselected failback phase does not leave later modules running against
    the other node."""
    current = call("failover.node")
    if current != node:
        back = hard_failover(current)
        assert back == node, f"expected {node} to become ACTIVE again, got {back}"


@contextlib.contextmanager
def lio_mode():
    """Switch to LIO mode (ALUA off), yield, restore original mode/state."""
    original = call("iscsi.global.config")
    original_mode = original["mode"]
    original_alua = original["alua"]
    original_started = call("service.started", SERVICE_NAME)
    _stop_service()
    try:
        call("iscsi.global.update", {"mode": LIO_MODE, "alua": False})
        _start_service()
        yield
    finally:
        _stop_service()
        call("iscsi.global.update", {"mode": original_mode, "alua": original_alua})
        if original_started:
            _start_service()


# ---------------------------------------------------------------------------
# Session / topology helpers
# ---------------------------------------------------------------------------


@dataclass
class SessionHandle:
    label: str
    index: int
    node: str | None
    conn: object
    key: int | None = None
    isid: str | None = None


@contextlib.contextmanager
def open_topology(topology, iqn, node_ips=None, lun=0):
    """
    One iscsi_scsi_connection() per entry in `topology`, opened in order.

    Each entry is either a bare label string (e.g. "A") -- resolved against
    truenas_server.ip -- or a (label, node) pair where `node` is a key into
    `node_ips` (e.g. "active"/"standby" for HA node-crossing topologies).
    Sessions sharing a label use the same target IQN with the same client
    identity (distinct ISID each, for free); different labels get distinct
    initiator_name overrides, per LABEL_INITIATOR_NAMES.

    Yields a list of SessionHandle in `topology` order.
    """
    entries = [(t, None) if isinstance(t, str) else t for t in topology]
    counts = {}
    with contextlib.ExitStack() as stack:
        sessions = []
        for label, node in entries:
            index = counts.get(label, 0)
            counts[label] = index + 1
            host = truenas_server.ip if node is None else node_ips[node]
            conn = stack.enter_context(
                iscsi_scsi_connection(host, iqn, lun, initiator_name=LABEL_INITIATOR_NAMES[label])
            )
            sessions.append(SessionHandle(label=label, index=index, node=node, conn=conn))
        yield sessions


@contextlib.contextmanager
def open_nexus(host, iqn, initiator_name=None, qualifier=None, label=None, node=None, lun=0, en=TEST_ISID_EN):
    """
    One session with a chosen initiator identity: `initiator_name` (None for
    the default pyscsi name) and, when `qualifier` is given, the explicit
    ISID isid_en_hex(qualifier). Logging in again with the same name and
    qualifier re-creates the same I_T nexus; a different qualifier is a
    different initiator port of the same initiator.

    Yields a SessionHandle usable with the pr_* helpers; handle.isid is the
    expected ISID string (None when the ISID is left random).
    """
    context_params = None if qualifier is None else isid_en_context(qualifier, en)
    with iscsi_scsi_connection(host, iqn, lun, initiator_name=initiator_name, context_params=context_params) as conn:
        yield SessionHandle(
            label=label or initiator_name or "A",
            index=0 if qualifier is None else qualifier,
            node=node,
            conn=conn,
            isid=None if qualifier is None else isid_en_hex(qualifier, en),
        )


def is_sibling(sessions, i, j):
    """True if sessions[i] and sessions[j] share an identity group."""
    return sessions[i].label == sessions[j].label


def _ascq_hex(asc, ascq):
    return f"0x{asc:02X}{ascq:02X}"


_UA_CODE_RE = re.compile(r"ASC\+Q:.*\(0x([0-9A-Fa-f]{4})\)")


def collect_uas(session, limit=16):
    """Issue TEST UNIT READY until it returns GOOD and return every unit
    attention delivered, in delivery order, as "0xAAQQ" strings (anything
    that does not parse as a UA is returned as its raw message). Each
    command reports one UA and clears only that one (SAM-5 5.14.1), so a
    nexus with several pending needs several commands. `limit` bounds the
    loop; reaching it is an error."""
    seen = []
    for _ in range(limit):
        try:
            session.conn.testunitready()
            return seen
        except Exception as e:
            m = _UA_CODE_RE.search(str(e))
            seen.append(f"0x{m.group(1).upper()}" if m else str(e))
    raise AssertionError(f"still reporting unit attentions after {limit} commands: {seen}")


def drain_ua(session):
    """Discard every pending UA -- clears stale state (e.g. from session
    establishment) before a test's real assertions."""
    collect_uas(session)


def assert_ua(session, asc, ascq, timeout=0):
    """Issue TEST UNIT READY, assert CHECK CONDITION with this ASC/ASCQ.
    Only the one UA reported is cleared; any others stay pending.

    With `timeout`, TEST UNIT READY is repeated while it returns GOOD, for
    up to `timeout` seconds, for a UA raised asynchronously.  A GOOD status
    clears nothing, so polling cannot hide a UA."""
    deadline = monotonic() + timeout
    while True:
        try:
            session.conn.testunitready()
        except Exception as e:
            # This CHECK CONDITION reported, and so cleared, the UA: assert
            # on it rather than on another command.
            error = e
            break
        if monotonic() >= deadline:
            raise AssertionError(
                f"expected {_ascq_hex(asc, ascq)}; "
                + (f"no UA within {timeout}s" if timeout else "TEST UNIT READY returned GOOD")
            )
        sleep(0.5)
    if _ascq_hex(asc, ascq) not in str(error):
        # Report every UA still queued, not just the first, so a mismatch
        # shows whether the expected one is pending behind another.
        raise AssertionError(
            f"expected {_ascq_hex(asc, ascq)}; UAs delivered in order: {[str(error)] + collect_uas(session)}"
        )


def assert_uas(session, expected):
    """Assert exactly the UAs in `expected` ((asc, ascq) pairs) are
    delivered across successive commands, in any order -- SAM-5 5.14.1
    leaves the order of same-precedence UAs undefined -- and none is lost."""
    want = sorted(_ascq_hex(asc, ascq) for asc, ascq in expected)
    got = collect_uas(session)
    assert sorted(got) == want, f"expected {want}; delivered in order: {got}"


def assert_no_ua(session):
    """Issue TEST UNIT READY, assert clean GOOD status."""
    session.conn.testunitready()


def _sense_key_asc_ascq(sense):
    """(sense key, ASC, ASCQ) from fixed- or descriptor-format sense data."""
    if sense[0] & 0x7F in (0x72, 0x73):
        return sense[1] & 0x0F, sense[2], sense[3]
    return sense[2] & 0x0F, sense[12], sense[13]


def lun_testunitready(session, lun):
    """Send TEST UNIT READY to `lun` over `session`'s existing I_T nexus.

    A session can address every LUN mapped to its ACL, not only the one it
    was opened on, but pyscsi always sends to the LUN in the device URL.
    This goes to the libiscsi context underneath (`device._iscsi`) instead.

    Returns None on GOOD, or (sense key, ASC, ASCQ) on CHECK CONDITION.
    Each call reports, and clears, at most one unit attention."""
    import iscsi

    task = iscsi.Task(bytearray(6), iscsi.scsi_xfer_dir.SCSI_XFER_NONE, 0)
    session.conn.device._iscsi.command(lun, task, bytearray(), bytearray())
    if task.status == 0:  # GOOD
        return None
    if task.status == 2:  # CHECK CONDITION
        return _sense_key_asc_ascq(task.raw_sense)
    raise AssertionError(f"TEST UNIT READY to LUN {lun}: SCSI status 0x{task.status:02X}")


def collect_lun_uas(session, lun, limit=16):
    """collect_uas() for `lun` addressed over `session` (see
    lun_testunitready()). Any CHECK CONDITION that is not a unit attention
    is an error."""
    seen = []
    for _ in range(limit):
        sense = lun_testunitready(session, lun)
        if sense is None:
            return seen
        key, asc, ascq = sense
        assert key == 0x6, f"LUN {lun}: sense key 0x{key:X} ASC/ASCQ {_ascq_hex(asc, ascq)}, not a unit attention"
        seen.append(_ascq_hex(asc, ascq))
    raise AssertionError(f"LUN {lun} still reporting unit attentions after {limit} commands: {seen}")


# ---------------------------------------------------------------------------
# Triggers
# ---------------------------------------------------------------------------


def resize_zvol(configured_lun, new_size_mb):
    resize_zvol_path(configured_lun.zvol, new_size_mb)


def resize_zvol_path(zvol, new_size_mb):
    call("pool.dataset.update", zvol, {"volsize": new_size_mb * MB})


@contextlib.contextmanager
def add_zvol_lun(configured_lun, lun_id, size_mb=20):
    """Add a second zvol-backed LUN to configured_lun's existing target,
    removed again on exit -- for tests that need to exercise a LUN-
    mapping change against an already-configured, already-connected
    target (e.g. target_luns_data_has_changed(), which notifies every
    other already-mapped LUN's connected sessions under a nacl when a
    LUN gets added to or removed from that nacl's target). Yields the new
    zvol's path."""
    zvol_path = f"{configured_lun.zvol}-{lun_id}"
    ext_name = f"{configured_lun.ext_name}-{lun_id}"
    with zvol_dataset(zvol_path, size_mb):
        with zvol_extent(zvol_path, ext_name) as extent_config:
            with target_extent_associate(configured_lun.target_id, extent_config["id"], lun_id):
                yield zvol_path


def _wait_for_configfs_path(path, retries=10):
    """Poll for a configfs path to appear. iscsi.extent.create() etc.
    return once the database is updated, not once the LIO configfs render
    (etc.generate('lio')) has actually finished -- the renderer itself has
    to poll-wait for its own paths for the same reason (_wait_for() in
    middlewared/utils/lio/config.py)."""
    for _ in range(retries):
        if ssh(f"test -e {path}", check=False, complete_response=True)["result"]:
            return
        sleep(0.5)
    raise RuntimeError(f"configfs path never appeared: {path}")


def cause_alua_transition_ua(configured_lun, state=ALUA_ACCESS_STATE_ACTIVE_NON_OPTIMIZED):
    """Write alua_access_state directly via configfs -- this is the
    implicit ALUA transition path (see
    target_tg_pt_gp_alua_access_state_store()), the same one TrueNAS's own
    HA failover logic drives."""
    active_node = call("failover.node")
    path = f"{IBLOCK_BASE}/{configured_lun.ext_name}/alua/controller_{active_node}/alua_access_state"
    _wait_for_configfs_path(path)
    ssh(f"echo {state} > {path}")


@contextlib.contextmanager
def expect_reservation_conflict(session):
    """As in test_261_iscsi_cmd.py/test_266_iscsi_lio_alua.py: pyscsi raises
    a dynamically-created ReservationConflict exception class for SCSI
    status RESERVATION CONFLICT."""
    try:
        yield
        assert False, "Expected RESERVATION CONFLICT, command succeeded"
    except Exception as e:
        if e.__class__.__name__ != "ReservationConflict":
            raise


def cause_reservation_conflict(session, configured_lun):
    """Open a throwaway holder session, take an EXCLUSIVE_ACCESS
    reservation, and issue one WRITE from `session` to trigger
    RESERVATION CONFLICT on it."""
    holder_key = 0xF00D000000000001
    with iscsi_scsi_connection(truenas_server.ip, configured_lun.iqn, 0) as holder_conn:
        holder = SessionHandle(label="_holder", index=0, node=None, conn=holder_conn)
        with pr_registration(holder, holder_key):
            with pr_reservation(holder, PR_TYPE.EXCLUSIVE_ACCESS, holder_key):
                with expect_reservation_conflict(session):
                    session.conn.write16(0, 1, bytearray(512))


def set_ua_intlck_ctrl(ext_name, mode):
    """SSH+configfs setter for emulate_ua_intlck_ctrl. Only accepted by the
    kernel while the backstore has zero exports (see
    emulate_ua_intlck_ctrl_store() in target_core_configfs.c) -- callers
    must set this before associating the extent with any target/LUN, not
    after."""
    path = f"{IBLOCK_BASE}/{ext_name}/attrib/emulate_ua_intlck_ctrl"
    _wait_for_configfs_path(path)
    ssh(f"echo {UA_INTLCK_CTRL_VALUES[mode]} > {path}")


# ---------------------------------------------------------------------------
# Persistent Reservation helpers
#
# Architecture based on test_261_iscsi_cmd.py's context-manager shape
# (pr_registration()/pr_reservation() auto-cleanup, generalized to assert
# both the positive and negative UA-fanout case on release), plus
# test_266_iscsi_lio_alua.py's pr_preempt()/pr_read_full_status() (261 has
# no equivalent of either). See UA_PR_TEST_SUITE_PLAN.md.
# ---------------------------------------------------------------------------

_REGISTRANTS_TYPES = (
    PR_TYPE.WRITE_EXCLUSIVE_REGISTRANTS_ONLY,
    PR_TYPE.EXCLUSIVE_ACCESS_REGISTRANTS_ONLY,
    PR_TYPE.WRITE_EXCLUSIVE_ALL_REGISTRANTS,
    PR_TYPE.EXCLUSIVE_ACCESS_ALL_REGISTRANTS,
)


def _opcodes(session):
    return session.conn.device.opcodes


def pr_register_key(session, key, all_tg_pt=False):
    """REGISTER the issuing nexus with `key`. With `all_tg_pt`, set the ALL_TG_PT
    bit: the initiator port is registered on every target port."""
    opcodes = _opcodes(session)
    kwargs = {"all_tg_pt": 1} if all_tg_pt else {}
    session.conn.persistentreserveout(
        opcodes.PERSISTENT_RESERVE_OUT.serviceaction.REGISTER,
        service_action_reservation_key=key,
        **kwargs,
    )
    session.key = key


def pr_register_ignore_existing(session, key):
    """REGISTER AND IGNORE EXISTING KEY: registers (or re-keys) the nexus
    whether or not it is registered, ignoring the RESERVATION KEY field."""
    opcodes = _opcodes(session)
    session.conn.persistentreserveout(
        opcodes.PERSISTENT_RESERVE_OUT.serviceaction.REGISTER_AND_IGNORE_EXISTING_KEY,
        service_action_reservation_key=key,
    )
    session.key = key


def pr_replace_key(session, old_key, new_key):
    """REGISTER from an already-registered nexus: change its key."""
    opcodes = _opcodes(session)
    session.conn.persistentreserveout(
        opcodes.PERSISTENT_RESERVE_OUT.serviceaction.REGISTER,
        reservation_key=old_key,
        service_action_reservation_key=new_key,
    )
    session.key = new_key


def pr_register_raw(session, reservation_key, service_action_key):
    """REGISTER with both key fields chosen by the caller, for the
    unregistered-nexus rules (SPC-5 5.14.7 table 68). Leaves session.key
    alone."""
    opcodes = _opcodes(session)
    session.conn.persistentreserveout(
        opcodes.PERSISTENT_RESERVE_OUT.serviceaction.REGISTER,
        reservation_key=reservation_key,
        service_action_reservation_key=service_action_key,
    )


def pr_register_and_move(
    session, key, new_key, dest_iqn, dest_isid, rtpi, pr_type=PR_TYPE.WRITE_EXCLUSIVE, unreg=False
):
    """REGISTER AND MOVE to the iSCSI initiator port `dest_iqn` + `dest_isid`
    (12 hex digits) on relative target port `rtpi`, registering `new_key`
    for it. With `unreg`, set the UNREG bit, so the issuing nexus is
    unregistered once the reservation has moved (SPC-5 5.14.8). Leaves
    session.key alone."""
    opcodes = _opcodes(session)
    kwargs = {"unreg": 1} if unreg else {}
    session.conn.persistentreserveout(
        opcodes.PERSISTENT_RESERVE_OUT.serviceaction.REGISTER_AND_MOVE,
        scope=LU_SCOPE,
        pr_type=pr_type,
        reservation_key=key,
        service_action_reservation_key=new_key,
        relative_target_port_id=rtpi,
        transport_id={
            "protocol_id": PROTOCOL_ID.ISCSI,
            "tpid_format": 1,
            "iscsi_name": dest_iqn,
            "iscsi_initiator_session_id": dest_isid,
        },
        **kwargs,
    )


def pr_register_spec_i_pt(session, key, ports):
    """REGISTER with SPEC_I_PT=1: register the issuing nexus and every iSCSI
    initiator port in `ports`, (iscsi_name, isid) pairs with the ISID as 12
    hex digits, with `key`, through the target port the command arrived on
    (SPC-5 5.14.7, 6.17.3)."""
    opcodes = _opcodes(session)
    session.conn.persistentreserveout(
        opcodes.PERSISTENT_RESERVE_OUT.serviceaction.REGISTER,
        service_action_reservation_key=key,
        spec_i_pt=1,
        transport_ids=[
            {
                "protocol_id": PROTOCOL_ID.ISCSI,
                "tpid_format": 1,
                "iscsi_name": name,
                "iscsi_initiator_session_id": isid,
            }
            for name, isid in ports
        ],
    )
    session.key = key


def pr_unregister_key(session, key, all_tg_pt=False):
    """UNREGISTER the issuing nexus (REGISTER with SERVICE ACTION RESERVATION
    KEY 0). LIO requires `all_tg_pt` for a registration made with ALL_TG_PT
    set, and refuses the command with INVALID FIELD IN CDB without it."""
    opcodes = _opcodes(session)
    kwargs = {"all_tg_pt": 1} if all_tg_pt else {}
    session.conn.persistentreserveout(
        opcodes.PERSISTENT_RESERVE_OUT.serviceaction.REGISTER,
        reservation_key=key,
        service_action_reservation_key=0,
        **kwargs,
    )
    session.key = None


def pr_reserve(session, pr_type, key, scope=LU_SCOPE):
    opcodes = _opcodes(session)
    session.conn.persistentreserveout(
        opcodes.PERSISTENT_RESERVE_OUT.serviceaction.RESERVE,
        scope=scope,
        pr_type=pr_type,
        reservation_key=key,
    )


def pr_release(session, pr_type, key, scope=LU_SCOPE):
    opcodes = _opcodes(session)
    session.conn.persistentreserveout(
        opcodes.PERSISTENT_RESERVE_OUT.serviceaction.RELEASE,
        scope=scope,
        pr_type=pr_type,
        reservation_key=key,
    )


def pr_clear(session, key):
    opcodes = _opcodes(session)
    session.conn.persistentreserveout(
        opcodes.PERSISTENT_RESERVE_OUT.serviceaction.CLEAR,
        reservation_key=key,
    )


def pr_preempt(session, pr_type, preemptor_key, victim_key, scope=LU_SCOPE):
    opcodes = _opcodes(session)
    session.conn.persistentreserveout(
        opcodes.PERSISTENT_RESERVE_OUT.serviceaction.PREEMPT,
        scope=scope,
        pr_type=pr_type,
        reservation_key=preemptor_key,
        service_action_reservation_key=victim_key,
    )


def pr_read_full_status(session):
    opcodes = _opcodes(session)
    return session.conn.persistentreservein(opcodes.PERSISTENT_RESERVE_IN.serviceaction.READ_FULL_STATUS).result


@dataclass(frozen=True)
class Registration:
    """One READ FULL STATUS descriptor (SPC-5 6.16.3): a registered I_T
    nexus. `isid` is lower-case hex, or None when the target reports the
    initiator port without one (TransportID format 00b)."""

    key: int
    initiator: str
    isid: str | None
    rtpi: int
    holder: bool
    all_tg_pt: bool
    scope: int
    pr_type: int


def pr_registrations(session):
    """READ FULL STATUS parsed into a list of Registration, in the order the
    target returned them (which carries no meaning)."""
    regs = []
    for d in pr_read_full_status(session)["full_status"]:
        tid = d["transport_id"]
        isid = tid.get("iscsi_initiator_session_id")
        regs.append(
            Registration(
                key=d["reservation_key"],
                initiator=tid["iscsi_name"],
                isid=isid.lower() if isid else None,
                rtpi=d["relative_target_port_id"],
                holder=bool(d["r_holder"]),
                all_tg_pt=bool(d["all_tg_pt"]),
                scope=d["scope"],
                pr_type=d["type"],
            )
        )
    return regs


def registrations_for(regs, key):
    """The registrations in `regs` that carry `key` (one per I_T nexus: a key
    registered through several nexuses appears once for each)."""
    return [r for r in regs if r.key == key]


def assert_registered(session, expected):
    """READ FULL STATUS shows exactly the registrations in `expected`, a
    collection of (key, qualifier) or (key, qualifier, en) tuples naming the
    I_T nexus by the qualifier (and enterprise number, if not the default)
    it logged in with (see isid_en_hex()); every one must belong to
    CLIENT_IQN. Returns the Registration list."""
    regs = pr_registrations(session)
    got = sorted((r.key, r.isid) for r in regs)
    want = sorted((key, isid_en_hex(*isid)) for key, *isid in expected)
    assert got == want, f"registrations {regs!r}, expected {want!r}"
    assert {r.initiator for r in regs} <= {CLIENT_IQN}, regs
    return regs


def assert_registrations(session, expected):
    """READ FULL STATUS shows exactly the registrations in `expected`, a
    collection of (key, initiator_name, qualifier) tuples; an initiator_name of
    None means CLIENT_IQN, the qualifier is the one the nexus logged in with
    (see isid_en_hex()). Several nexuses with the same key, or the same
    initiator port through different target ports, are listed once per
    registration. Returns the Registration list."""
    regs = pr_registrations(session)
    got = sorted((r.key, r.initiator, r.isid) for r in regs)
    want = sorted((key, name or CLIENT_IQN, isid_en_hex(q)) for key, name, q in expected)
    assert got == want, f"registrations {regs!r}, expected {want!r}"
    return regs


def holder_flags(regs):
    """{key: holder} for a Registration list whose keys are distinct."""
    flags = {r.key: r.holder for r in regs}
    assert len(flags) == len(regs), regs
    return flags


def io_access(session):
    """(readable, writable) for LBA 0: whether a READ(16) and a WRITE(16) of one
    block are accepted (True) or get RESERVATION CONFLICT (False). Any other
    error propagates. The write stores zeros."""

    def accepted(command):
        try:
            command()
        except Exception as e:
            if e.__class__.__name__ == "ReservationConflict":
                return False
            raise
        return True

    return (
        accepted(lambda: session.conn.read16(0, 1)),
        accepted(lambda: session.conn.write16(0, 1, bytearray(512))),
    )


_WRITE_EXCLUSIVE_TYPES = (
    PR_TYPE.WRITE_EXCLUSIVE,
    PR_TYPE.WRITE_EXCLUSIVE_REGISTRANTS_ONLY,
    PR_TYPE.WRITE_EXCLUSIVE_ALL_REGISTRANTS,
)


def expected_access(pr_type, role):
    """(readable, writable) that a nexus must get under a persistent
    reservation of `pr_type` held by another nexus, per SPC-5 tables 66 and 67.
    `role` is "holder", "registered" (registered, not the holder) or
    "unregistered". With the all-registrants types every registered nexus is a
    holder (5.14.10)."""
    if role == "holder":
        return True, True
    if role == "registered" and pr_type in _REGISTRANTS_TYPES:
        return True, True
    return pr_type in _WRITE_EXCLUSIVE_TYPES, False


def pr_check_registered_keys(session, expected=()):
    opcodes = _opcodes(session)
    data = session.conn.persistentreservein(opcodes.PERSISTENT_RESERVE_IN.serviceaction.READ_KEYS).result
    assert set(data["reservation_keys"]) == set(expected), data
    return data


def pr_check_reservation(session, expected=None):
    opcodes = _opcodes(session)
    data = session.conn.persistentreservein(opcodes.PERSISTENT_RESERVE_IN.serviceaction.READ_RESERVATION).result
    if expected is None:
        expected = {"reservation_key": None, "scope": None, "type": None}
    for key, value in expected.items():
        assert data.get(key) == value, data
    return data


@contextlib.contextmanager
def pr_registration(session, key):
    pr_register_key(session, key)
    try:
        yield
    finally:
        pr_unregister_key(session, key)


def default_pr_key(index):
    return 0xABCD000000000000 | (index + 1)


def register_all(sessions, keys=None):
    """Register a distinct PR key on every session, with no unregister-on-
    exit -- for triggers (CLEAR, PREEMPT) that wipe registrations
    server-side, where pr_registration()'s auto-unregister teardown would
    otherwise fail (same SPC-5 5.14.11.2.3 hygiene gap noted in
    test_261_iscsi_cmd.py's _pr_registration())."""
    if keys is None:
        keys = [default_pr_key(i) for i in range(len(sessions))]
    for session, key in zip(sessions, keys):
        pr_register_key(session, key)


@contextlib.contextmanager
def registered_sessions(sessions, keys=None):
    """Register a distinct PR key on every session; unregister all on
    exit, regardless of which session raises."""
    if keys is None:
        keys = [default_pr_key(i) for i in range(len(sessions))]
    with contextlib.ExitStack() as stack:
        for session, key in zip(sessions, keys):
            stack.enter_context(pr_registration(session, key))
        yield


# How long to wait for a UA raised by another session's command.
UA_WAIT_SECONDS = 5


@contextlib.contextmanager
def pr_reservation(session, pr_type, key, scope=LU_SCOPE, other_sessions=(), check_releaser=False):
    """Reserve on enter, release on exit. After the release, assert every
    session in `other_sessions` sees RESERVATIONS RELEASED (0x2A/0x04) if
    `pr_type` is registrants-only/all-registrants, and assert_no_ua
    otherwise.

    With `check_releaser`, first assert the releasing session itself has
    no UA.  That check must come before any session that shares its
    identity is drained: with a per-ACL rather than per-nexus queue, the
    other session would consume the UA and the releaser's check would pass
    vacuously.

    If the body raises, the reservation is released and nothing is
    asserted, so the body's exception is the one reported."""
    assert session not in other_sessions, "Invalid parameter mix"
    pr_reserve(session, pr_type, key, scope)
    try:
        yield
    except BaseException:
        pr_release(session, pr_type, key, scope)
        raise
    pr_release(session, pr_type, key, scope)
    if check_releaser:
        assert_no_ua(session)
    if pr_type in _REGISTRANTS_TYPES:
        for other in other_sessions:
            assert_ua(other, 0x2A, 0x04, timeout=UA_WAIT_SECONDS)
    else:
        for other in other_sessions:
            assert_no_ua(other)
