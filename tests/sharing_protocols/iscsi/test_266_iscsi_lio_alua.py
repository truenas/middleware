"""
test_266_iscsi_lio_alua.py

LIO ALUA test suite.

Part A -- single-node tests (no HA hardware required).
Part B -- HA tests (require HA hardware and LIO+ALUA).

Related suites (not duplicated here):
  test_262_iscsi_alua.py  -- SCST ALUA HA
  test_264_iscsi_mode_compat.py  -- single-node SCST/LIO feature parity
"""

import contextlib
import random
import socket
import string
from time import sleep

from assets.websocket.iscsi import (
    _device_identification,
    _serial_number,
    initiator,
    initiator_portal,
    portal,
    target,
    target_extent_associate,
    zvol_extent,
)
from assets.websocket.pool import zvol as zvol_dataset
from assets.websocket.service import ensure_service_enabled
from auto_config import ha, isns_ip, pool_name
from iscsi_ua_pr_utils import (
    IBLOCK_BASE,
    LU_SCOPE,
    assert_registrations,
    drain_ua,
    fail_back_to,
    hard_failover,
    io_access,
    open_nexus,
    pr_check_reservation,
    pr_register_key,
    pr_reserve,
)
from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.assets.iscsi import lio_supported
from middlewared.test.integration.utils import call, ssh
from middlewared.test.integration.utils.client import truenas_server
from protocols import iscsi_scsi_connection
from pyscsi.pyscsi.scsi_cdb_persistentreservein import PR_TYPE
import pytest

# ---------------------------------------------------------------------------
# ISCSIMODE (mirrors the non-importable middleware enum)
# ---------------------------------------------------------------------------


class ISCSIMODE:
    SCST_DLM_PRSTATE_SAVE = 0
    SCST_DLM_PRSTATE_NOSAVE = 1
    LIO = 2


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SERVICE_NAME = "iscsitarget"
MB = 1024 * 1024
basename = "iqn.2005-10.org.freenas.ctl"

CONTROLLER_A_TPG_ID = 101
CONTROLLER_B_TPG_ID = 102

# Node B's TPG tag for a given target = rel_tgt_id + REL_TGT_ID_NODEB_OFFSET.
# Must match middlewared.utils.iscsi.constants.REL_TGT_ID_NODEB_OFFSET.
REL_TGT_ID_NODEB_OFFSET = 32000


def _tpg_port_ids(tgt_config):
    """Return (node_a_rtpi, node_b_rtpi) for a target.

    For iSCSI, the relative target port identifier in RTPG equals the TPG tag.
    TrueNAS sets each target's TPG tag to its rel_tgt_id on Node A, and to
    rel_tgt_id + REL_TGT_ID_NODEB_OFFSET on Node B.  These values are
    per-target, not global constants.
    """
    rel = tgt_config["rel_tgt_id"]
    return rel, rel + REL_TGT_ID_NODEB_OFFSET


_rnd = "".join(random.choices(string.digits, k=4))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _verify_rtpg(s, tpgs, active_tpg_id):
    """Assert RTPG response matches expected ALUA states and relative port IDs.

    tpgs: {group_id: [rtpi, ...]} -- expected relative port IDs per group.
    active_tpg_id: group_id that should report ACTIVE_OPTIMIZED (0); all
    others must report NONOPTIMIZED (1).
    """
    result = s.reporttargetportgroups().result
    for desc in result["target_port_group_descriptors"]:
        gid = desc["target_port_group"]
        got_ports = {p["relative_target_port_id"] for p in desc["target_ports"]}
        assert got_ports == set(tpgs[gid]), f"TPG {gid}: port IDs {got_ports!r} != {set(tpgs[gid])!r}"
        expected_state = 0 if gid == active_tpg_id else 1
        assert desc["asymmetric_access_state"] == expected_state, (
            f"TPG {gid}: state {desc['asymmetric_access_state']!r} != {expected_state!r}"
        )


# States the non-active group passes through until the returning STANDBY has
# synced and the ACTIVE node has been told: UNAVAILABLE, TRANSITIONING.
_STANDBY_SETTLING_STATES = (3, 15)


def _verify_rtpg_settled(ip, iqn, tpgs, active_tpg_id, retries=12):
    """_verify_rtpg through a new session to `ip`, retried every 5 seconds
    while the non-active group still reports UNAVAILABLE or TRANSITIONING.
    Every other mismatch fails at once."""
    for attempt in range(retries + 1):
        with open_nexus(ip, iqn) as session:
            drain_ua(session)
            result = session.conn.reporttargetportgroups().result
        settling = any(
            desc["target_port_group"] != active_tpg_id and desc["asymmetric_access_state"] in _STANDBY_SETTLING_STATES
            for desc in result["target_port_group_descriptors"]
        )
        if not settling or attempt == retries:
            break
        sleep(5)
    with open_nexus(ip, iqn) as session:
        drain_ua(session)
        _verify_rtpg(session.conn, tpgs, active_tpg_id)


def _check_rw_paths(s_preferred, s_nonpreferred):
    """Verify that both SCSI connections reach the same underlying LUN.

    Writes via each path and reads back via both, confirming that
    forwarding (NONOPTIMIZED -> ACTIVE) produces coherent storage.
    """
    zeros = bytearray(512)
    pattern_a = bytearray.fromhex("deadbeef") * 128
    pattern_b = bytearray.fromhex("abbaabba") * 128

    s_preferred.writesame16(0, 12, zeros)
    for s in (s_preferred, s_nonpreferred):
        for lba in range(12):
            assert s.read16(lba, 1).datain == zeros

    s_preferred.writesame16(0, 6, pattern_a)
    s_nonpreferred.writesame16(6, 6, pattern_b)
    for s in (s_preferred, s_nonpreferred):
        for lba in range(6):
            assert s.read16(lba, 1).datain == pattern_a
        for lba in range(6, 12):
            assert s.read16(lba, 1).datain == pattern_b


def _report_luns(s) -> frozenset:
    """Return frozenset of integer LUN IDs from REPORT LUNS (select_report=0).

    Parses the 8-byte LUN entries from the raw response.  For LIO LUNs 0-255
    (simple addressing, address method = 00b) the LUN ID is in the second byte
    of each entry.
    """
    buf = s.reportluns().datain
    if len(buf) < 8:
        return frozenset()
    lun_list_length = int.from_bytes(buf[0:4], "big")
    luns = set()
    for offset in range(8, 8 + lun_list_length, 8):
        if offset + 2 <= len(buf):
            addr_method = (buf[offset] >> 6) & 0x3
            if addr_method == 0:  # peripheral / simple
                luns.add(buf[offset + 1])
            elif addr_method == 1:  # flat space
                luns.add(((buf[offset] & 0x3F) << 8) | buf[offset + 1])
    return frozenset(luns)


def _scsi_name_string_tag(s) -> int | None:
    """Return the TPG tag integer from the target-port SCSI name string in VPD 0x83.

    LIO encodes the TPG tag as ',t,0x{tag:04x}' at the end of the target IQN
    in the SCSI name string designator (code_set=3 UTF-8, association=1, type=8).
    On the STANDBY path, lio_ha_replace_port_info() patches this in-place to
    reflect STANDBY's tpg_rtpi.  Returns None if the designator is absent.

    Uses pyscsi's parsed result rather than raw .datain to avoid header-offset
    ambiguity.  pyscsi exposes the SCSI name string under varying keys across
    versions; try the common ones, then fall through to scanning .designator
    bytes for the ',t,0x' marker.
    """
    # alloclen default is 96 bytes; VPD 0x83 with two SCSI name strings is
    # ~185 bytes, so the type-8 descriptors fall off the end without this.
    result = s.inquiry(evpd=1, page_code=0x83, alloclen=256)
    for desc in result.result.get("designator_descriptors", []):
        if desc.get("association") != 1:
            continue
        if desc.get("designator_type") != 8:
            continue
        d = desc.get("designator", {})
        # Common pyscsi keys for SCSI name string content
        raw = d.get("scsi_name_string") or d.get("scsi_name") or d.get("designator") or d.get("name")
        if isinstance(raw, (bytes, bytearray)):
            name = raw.decode("utf-8", errors="replace")
        elif isinstance(raw, str):
            name = raw
        else:
            continue
        idx = name.find(",t,0x")
        if idx >= 0:
            try:
                return int(name[idx + 5 : idx + 9], 16)
            except (ValueError, IndexError):
                pass
    return None


def _get_designator(s, designator_type):
    """Return the first VPD 0x83 designator descriptor of the given type
    (3 = NAA), for use as an XCOPY CSCD target descriptor identity."""
    x = s.inquiry(evpd=1, page_code=0x83)
    for designator in x.result["designator_descriptors"]:
        if designator["designator_type"] == designator_type:
            del designator["piv"]
            return designator


def _xcopy_one_block(s, d_src, d_dst, src_lba, dst_lba):
    """Issue EXTENDED COPY(LID4) of a single 512-byte block from the LU
    identified by d_src to the LU identified by d_dst, via session s.

    Mirrors the target/segment descriptor shape from test_261_iscsi_cmd.py's
    _xcopy_test(), reduced to a single block.
    """
    s.extendedcopy4(
        priority=1,
        list_identifier=0x15,
        target_descriptor_list=[
            {
                "descriptor_type_code": "Identification descriptor target descriptor",
                "peripheral_device_type": 0x00,
                "target_descriptor_parameters": d_src,
                "device_type_specific_parameters": {"disk_block_length": 512},
            },
            {
                "descriptor_type_code": "Identification descriptor target descriptor",
                "peripheral_device_type": 0x00,
                "target_descriptor_parameters": d_dst,
                "device_type_specific_parameters": {"disk_block_length": 512},
            },
        ],
        segment_descriptor_list=[
            {
                "descriptor_type_code": "Copy from block device to block device",
                "dc": 1,
                "source_target_descriptor_id": 0,
                "destination_target_descriptor_id": 1,
                "block_device_number_of_blocks": 1,
                "source_block_device_logical_block_address": src_lba,
                "destination_block_device_logical_block_address": dst_lba,
            }
        ],
    )


def _wait_for_alua_settle(retries=12):
    sleep(5)
    while retries:
        if call("iscsi.alua.settled"):
            return
        retries -= 1
        sleep(5)


def _stop_service():
    call("service.control", "STOP", SERVICE_NAME, job=True)


def _start_service():
    call("service.control", "START", SERVICE_NAME, job=True)


@contextlib.contextmanager
def _lio_mode(alua=False):
    """Switch to LIO mode (with optional ALUA), yield, restore original state."""
    original = call("iscsi.global.config")
    original_mode = original["mode"]
    original_alua = original["alua"]
    _stop_service()
    try:
        call("iscsi.global.update", {"mode": ISCSIMODE.LIO, "alua": alua})
        _start_service()
        _wait_for_alua_settle()
        yield
    finally:
        _stop_service()
        call("iscsi.global.update", {"mode": original_mode, "alua": original_alua})
        _start_service()


# ---------------------------------------------------------------------------
# Module-level guard
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module", autouse=True)
def _require_lio():
    """Skip entire module if LIO mode (2) is not supported by the API."""
    if not lio_supported():
        pytest.skip("LIO mode (2) not accepted by API")
    yield


# ---------------------------------------------------------------------------
# Part A -- single-node tests (no HA guard)
# ---------------------------------------------------------------------------


# A1
def test_non_ha_default_tg_pt_gp_state():
    """Non-HA LIO: default_tg_pt_gp state is ACTIVE_OPTIMIZED (0).

    Middleware path: _alua_groups enter, non-HA branch.
    """
    iblock_base = "/sys/kernel/config/target/core/iblock_0"
    with _lio_mode(alua=False):
        with zvol_dataset(f"a1{_rnd}", 20, pool_name) as zvol_config:
            with zvol_extent(zvol_config["id"], f"a1ext{_rnd}") as extent_config:
                with initiator_portal() as ip_config:
                    with target(f"a1tgt{_rnd}", [{"portal": ip_config["portal"]["id"]}]) as tgt_config:
                        with target_extent_associate(tgt_config["id"], extent_config["id"]):
                            states = ssh(
                                f'for f in {iblock_base}/*/alua/default_tg_pt_gp/alua_access_state; do cat "$f"; done'
                            )
                            for line in states.strip().splitlines():
                                assert line.strip() == "0", f"Expected ACTIVE_OPTIMIZED (0), got {line!r}"

                            ctrl_dirs = ssh(
                                f'find {iblock_base} -maxdepth 3 -name "controller_*" -type d 2>/dev/null || true'
                            )
                            assert ctrl_dirs.strip() == "", f"Unexpected HA controller groups found: {ctrl_dirs}"


# A2
def test_lio_ha_module_not_loaded_without_alua():
    """lio_ha module not loaded when alua=False.

    Middleware path: _load_modules, alua=False branch.
    """
    with _lio_mode(alua=False):
        ssh("test ! -d /sys/module/lio_ha")


# ---------------------------------------------------------------------------
# Part B -- HA tests
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not ha, reason="HA tests require HA hardware")
class TestLIOALUA:
    # -----------------------------------------------------------------------
    # Wait helpers (match test_262 pattern)
    # -----------------------------------------------------------------------

    def _wait_for_settle(self):
        _wait_for_alua_settle()

    # -----------------------------------------------------------------------
    # Class fixture
    # -----------------------------------------------------------------------

    @pytest.fixture(scope="class")
    @classmethod
    def lio_alua_configured(cls):
        """Switch to LIO+ALUA, wait for settle, create a named initiator group
        (containing the pyscsi test-client IQN -- required by
        validate_alua_compat) plus a portal, yield config, restore on teardown."""
        assert call("failover.config")["disabled"] is False
        original = call("iscsi.global.config")
        original_mode = original["mode"]
        original_alua = original["alua"]
        original_started = call("service.started", SERVICE_NAME)
        original_node = call("failover.node")
        client_iqn = f"iqn.2018-01.org.pyscsi:{socket.gethostname()}"
        with ensure_service_enabled(SERVICE_NAME):
            _stop_service()
            try:
                call("iscsi.global.update", {"mode": ISCSIMODE.LIO, "alua": True})
                _start_service()
                _wait_for_alua_settle()
                with initiator(initiators=[client_iqn]) as init_config:
                    with portal() as portal_config:
                        yield {
                            "initiator": init_config,
                            "portal": portal_config,
                        }
            finally:
                try:
                    # test_hard_failover leaves the other node ACTIVE; fail
                    # back while still in LIO+ALUA mode.
                    fail_back_to(original_node)
                finally:
                    _stop_service()
                    call("iscsi.global.update", {"mode": original_mode, "alua": original_alua})
                    if original_started:
                        _start_service()

    # -----------------------------------------------------------------------
    # B1-B3: Validation tests (own setup, no lio_alua_configured fixture)
    # -----------------------------------------------------------------------

    # B1
    def test_validate_alua_compat_open_initiator_rejected(self):
        """validate_alua_compat: open initiator group rejected.

        Middleware path: iscsi.lio.validate_alua_compat.
        """
        tgt_name = f"b1tgt{_rnd}"
        with _lio_mode(alua=False):
            with initiator_portal() as ip_config:
                # initiator_portal() creates an open group (no IQNs) -- exactly
                # what validate_alua_compat rejects.
                with target(tgt_name, [{"portal": ip_config["portal"]["id"]}]):
                    _stop_service()
                    try:
                        with pytest.raises(ValidationErrors) as ve:
                            call("iscsi.global.update", {"alua": True})
                        assert ve.value.errors[0].attribute == "iscsiglobal_update.alua"
                        assert tgt_name in ve.value.errors[0].errmsg
                    finally:
                        _start_service()

    # B2
    def test_validate_alua_compat_named_initiator_accepted(self):
        """validate_alua_compat: named initiator group accepted.

        Middleware path: iscsi.lio.validate_alua_compat.
        """
        named_iqn = f"iqn.2005-10.org.freenas.ctl:b2init{_rnd}"
        with _lio_mode(alua=False):
            with initiator(initiators=[named_iqn]) as init_config:
                with portal() as portal_config:
                    with target(f"b2tgt{_rnd}", [{"portal": portal_config["id"], "initiator": init_config["id"]}]):
                        _stop_service()
                        try:
                            call("iscsi.global.update", {"alua": True})
                            assert call("iscsi.global.config")["alua"] is True
                        finally:
                            call("iscsi.global.update", {"alua": False})
                            _start_service()

    # B3
    def test_validate_scst_compat_isns_alua_rejected(self):
        """validate_scst_compat + ALUA: iSNS + ALUA together rejected on mode switch.

        Middleware path: iscsi.lio.validate_scst_compat(new_alua=True).
        """
        original_mode = call("iscsi.global.config")["mode"]
        if original_mode >= ISCSIMODE.LIO:
            pytest.skip("Baseline mode is already LIO; this test needs an SCST starting point")
        original_started = call("service.started", SERVICE_NAME)

        tgt_name = f"b3tgt{_rnd}"

        # An open initiator group (no named IQNs) exercises
        # validate_alua_compat, folded into validate_scst_compat's result
        # when new_alua=True; an iSNS server configured exercises
        # validate_scst_compat's own iSNS check. Together they cover both
        # halves of the expected combined ValidationError.
        with initiator_portal() as ip_config:
            with target(tgt_name, [{"portal": ip_config["portal"]["id"]}]):
                _stop_service()
                try:
                    call("iscsi.global.update", {"isns_servers": [isns_ip]})
                    try:
                        with pytest.raises(ValidationErrors) as ve:
                            call("iscsi.global.update", {"mode": ISCSIMODE.LIO, "alua": True})
                        messages = " ".join(e.errmsg for e in ve.value.errors)
                        assert "iSNS" in messages, f"Expected iSNS rejection, got: {messages}"
                        assert tgt_name in messages, (
                            f"Expected open-initiator-group rejection for {tgt_name}, got: {messages}"
                        )
                    finally:
                        call("iscsi.global.update", {"isns_servers": []})
                finally:
                    if original_started:
                        _start_service()

    # -----------------------------------------------------------------------
    # B4: Module presence
    # -----------------------------------------------------------------------

    # B4
    def test_lio_ha_module_loaded(self, lio_alua_configured):
        """lio_ha module loaded on both nodes when alua=True.

        Middleware path: _load_modules, alua=True branch.
        """
        standby_ip = truenas_server.ha_ips()["standby"]
        ssh("test -d /sys/module/lio_ha")
        ssh("test -d /sys/module/lio_ha", ip=standby_ip)

    # -----------------------------------------------------------------------
    # B5-B6: configfs structure
    # -----------------------------------------------------------------------

    # B5
    def test_controller_group_structure(self, lio_alua_configured):
        """Controller ALUA group structure visible in configfs.

        Middleware path: _alua_groups enter, HA branch.
        """
        iblock_base = "/sys/kernel/config/target/core/iblock_0"
        ext_name = f"b5ext{_rnd}"
        standby_ip = truenas_server.ha_ips()["standby"]

        with zvol_dataset(f"b5{_rnd}", 20, pool_name) as zvol_config:
            with zvol_extent(zvol_config["id"], ext_name) as extent_config:
                with target(
                    f"b5tgt{_rnd}",
                    [
                        {
                            "portal": lio_alua_configured["portal"]["id"],
                            "initiator": lio_alua_configured["initiator"]["id"],
                        }
                    ],
                ) as tgt_config:
                    with target_extent_associate(tgt_config["id"], extent_config["id"]):
                        for node_ip in (None, standby_ip):
                            ssh(f"test -d {iblock_base}/{ext_name}/alua/controller_A", ip=node_ip)
                            ssh(f"test -d {iblock_base}/{ext_name}/alua/controller_B", ip=node_ip)
                            id_a = ssh(
                                f"cat {iblock_base}/{ext_name}/alua/controller_A/tg_pt_gp_id",
                                ip=node_ip,
                            ).strip()
                            id_b = ssh(
                                f"cat {iblock_base}/{ext_name}/alua/controller_B/tg_pt_gp_id",
                                ip=node_ip,
                            ).strip()
                            assert id_a == str(CONTROLLER_A_TPG_ID), (
                                f"node {node_ip}: controller_A tg_pt_gp_id={id_a!r}"
                            )
                            assert id_b == str(CONTROLLER_B_TPG_ID), (
                                f"node {node_ip}: controller_B tg_pt_gp_id={id_b!r}"
                            )

    # B6
    def test_lun_port_group_assignment(self, lio_alua_configured):
        """LUN alua_tg_pt_gp attribute points to local controller group.

        Middleware path: _reconcile_luns with ha_mode=True.
        """
        iscsi_base = "/sys/kernel/config/target/iscsi"
        ext_name = f"b6ext{_rnd}"
        standby_ip = truenas_server.ha_ips()["standby"]
        active_node = call("failover.node")  # 'A' or 'B'
        standby_node = "B" if active_node == "A" else "A"

        with zvol_dataset(f"b6{_rnd}", 20, pool_name) as zvol_config:
            with zvol_extent(zvol_config["id"], ext_name) as extent_config:
                with target(
                    f"b6tgt{_rnd}",
                    [
                        {
                            "portal": lio_alua_configured["portal"]["id"],
                            "initiator": lio_alua_configured["initiator"]["id"],
                        }
                    ],
                ) as tgt_config:
                    with target_extent_associate(tgt_config["id"], extent_config["id"]):
                        iqn = f"{basename}:{tgt_config['name']}"
                        rel = tgt_config["rel_tgt_id"]
                        active_tag = rel if active_node == "A" else rel + REL_TGT_ID_NODEB_OFFSET
                        standby_tag = rel if standby_node == "A" else rel + REL_TGT_ID_NODEB_OFFSET

                        attr = f"{iscsi_base}/{iqn}/tpgt_{active_tag}/lun/lun_0/alua_tg_pt_gp"
                        val = ssh(f"cat {attr}").strip()
                        assert f"controller_{active_node}" in val, f"MASTER Node {active_node}: {val!r}"

                        attr_s = f"{iscsi_base}/{iqn}/tpgt_{standby_tag}/lun/lun_0/alua_tg_pt_gp"
                        val_s = ssh(f"cat {attr_s}", ip=standby_ip).strip()
                        assert f"controller_{standby_node}" in val_s, f"STANDBY Node {standby_node}: {val_s!r}"

    # -----------------------------------------------------------------------
    # B7: RTPG
    # -----------------------------------------------------------------------

    # B7
    def test_rtpg_alua_state(self, lio_alua_configured):
        """RTPG reports correct ALUA states from MASTER and BACKUP.

        Kernel path: REPORT TARGET PORT GROUPS response from LIO ALUA.
        """
        active_node = call("failover.node")
        active_ip = truenas_server.nodea_ip if active_node == "A" else truenas_server.nodeb_ip
        standby_ip = truenas_server.nodeb_ip if active_node == "A" else truenas_server.nodea_ip
        active_tpg_id = CONTROLLER_A_TPG_ID if active_node == "A" else CONTROLLER_B_TPG_ID

        with zvol_dataset(f"b7{_rnd}", 20, pool_name) as zvol_config:
            with zvol_extent(zvol_config["id"], f"b7ext{_rnd}") as extent_config:
                with target(
                    f"b7tgt{_rnd}",
                    [
                        {
                            "portal": lio_alua_configured["portal"]["id"],
                            "initiator": lio_alua_configured["initiator"]["id"],
                        }
                    ],
                ) as tgt_config:
                    with target_extent_associate(tgt_config["id"], extent_config["id"]):
                        iqn = f"{basename}:{tgt_config['name']}"
                        rtpi_a, rtpi_b = _tpg_port_ids(tgt_config)
                        tpgs = {
                            CONTROLLER_A_TPG_ID: [rtpi_a],
                            CONTROLLER_B_TPG_ID: [rtpi_b],
                        }
                        with iscsi_scsi_connection(active_ip, iqn) as s1:
                            with iscsi_scsi_connection(standby_ip, iqn) as s2:
                                _verify_rtpg(s1, tpgs, active_tpg_id)
                                _verify_rtpg(s2, tpgs, active_tpg_id)

    # -----------------------------------------------------------------------
    # B8: I/O from both paths
    # -----------------------------------------------------------------------

    # B8
    def test_io_both_paths(self, lio_alua_configured):
        """I/O via preferred path (MASTER) and non-preferred path (STANDBY).

        Kernel path: ha_recv forwarding + check_stop_free.
        """
        active_node = call("failover.node")
        active_ip = truenas_server.nodea_ip if active_node == "A" else truenas_server.nodeb_ip
        standby_ip = truenas_server.nodeb_ip if active_node == "A" else truenas_server.nodea_ip

        with zvol_dataset(f"b8{_rnd}", 20, pool_name) as zvol_config:
            with zvol_extent(zvol_config["id"], f"b8ext{_rnd}") as extent_config:
                with target(
                    f"b8tgt{_rnd}",
                    [
                        {
                            "portal": lio_alua_configured["portal"]["id"],
                            "initiator": lio_alua_configured["initiator"]["id"],
                        }
                    ],
                ) as tgt_config:
                    with target_extent_associate(tgt_config["id"], extent_config["id"]):
                        iqn = f"{basename}:{tgt_config['name']}"
                        with iscsi_scsi_connection(active_ip, iqn) as s_pref:
                            with iscsi_scsi_connection(standby_ip, iqn) as s_nonpref:
                                _check_rw_paths(s_pref, s_nonpref)

    # -----------------------------------------------------------------------
    # B10/B11: Hard failover
    # -----------------------------------------------------------------------

    # B10/B11
    @pytest.mark.timeout(600)
    def test_hard_failover(self, lio_alua_configured):
        """Hard failover: targets accessible and ALUA state correct after reboot.

        Kernel path: lio_ha become_active(); ha_recv session teardown;
        ha_recv_check_stop_free (UAF fix exercised by in-flight commands at teardown).
        """
        orig_node = call("failover.node")
        orig_active_ip = truenas_server.nodea_ip if orig_node == "A" else truenas_server.nodeb_ip
        orig_standby_ip = truenas_server.nodeb_ip if orig_node == "A" else truenas_server.nodea_ip
        orig_active_tpg = CONTROLLER_A_TPG_ID if orig_node == "A" else CONTROLLER_B_TPG_ID

        with zvol_dataset(f"b10{_rnd}", 20, pool_name) as zvol_config:
            with zvol_extent(zvol_config["id"], f"b10ext{_rnd}") as extent_config:
                with target(
                    f"b10tgt{_rnd}",
                    [
                        {
                            "portal": lio_alua_configured["portal"]["id"],
                            "initiator": lio_alua_configured["initiator"]["id"],
                        }
                    ],
                ) as tgt_config:
                    with target_extent_associate(tgt_config["id"], extent_config["id"]):
                        iqn = f"{basename}:{tgt_config['name']}"
                        rtpi_a, rtpi_b = _tpg_port_ids(tgt_config)
                        tpgs = {
                            CONTROLLER_A_TPG_ID: [rtpi_a],
                            CONTROLLER_B_TPG_ID: [rtpi_b],
                        }

                        # Pre-failover: verify RTPG and coherent I/O from both paths.
                        with iscsi_scsi_connection(orig_active_ip, iqn) as s1:
                            with iscsi_scsi_connection(orig_standby_ip, iqn) as s2:
                                _verify_rtpg(s1, tpgs, orig_active_tpg)
                                _check_rw_paths(s1, s2)

                        # Reboot the current MASTER, wait for the old STANDBY
                        # to take over and for the rebooted node to return
                        # as a synced STANDBY.
                        new_node = hard_failover(orig_node)

                        # Post-failover: ALUA states must have flipped.  The
                        # new STANDBY's group is UNAVAILABLE or TRANSITIONING
                        # until the ACTIVE node is told it synced.
                        new_active_ip = truenas_server.nodea_ip if new_node == "A" else truenas_server.nodeb_ip
                        new_active_tpg = CONTROLLER_A_TPG_ID if new_node == "A" else CONTROLLER_B_TPG_ID
                        _verify_rtpg_settled(new_active_ip, iqn, tpgs, new_active_tpg)

                        with iscsi_scsi_connection(new_active_ip, iqn) as s_new:
                            zeros = bytearray(512)
                            s_new.writesame16(0, 4, zeros)
                            for lba in range(4):
                                assert s_new.read16(lba, 1).datain == zeros

    # -----------------------------------------------------------------------
    # B12: ALUA toggle
    # -----------------------------------------------------------------------

    # B12
    def test_alua_toggle(self, lio_alua_configured):
        """ALUA toggle on running HA system -- disable then re-enable.

        Middleware path: _alua_groups exit; _load_modules unload/reload;
        _reconcile_luns reassign alua_tg_pt_gp.
        """
        iblock_base = "/sys/kernel/config/target/core/iblock_0"
        iscsi_base = "/sys/kernel/config/target/iscsi"
        ext_name = f"b12ext{_rnd}"
        active_node = call("failover.node")
        standby_ip = truenas_server.ha_ips()["standby"]

        # Reuse the class fixture's named initiator + portal: a private
        # portal() would conflict with the fixture's portal on 0.0.0.0:3260.
        with zvol_dataset(f"b12{_rnd}", 20, pool_name) as zvol_config:
            with zvol_extent(zvol_config["id"], ext_name) as extent_config:
                with target(
                    f"b12tgt{_rnd}",
                    [
                        {
                            "portal": lio_alua_configured["portal"]["id"],
                            "initiator": lio_alua_configured["initiator"]["id"],
                        }
                    ],
                ) as tgt_config:
                    with target_extent_associate(tgt_config["id"], extent_config["id"]):
                        iqn = f"{basename}:{tgt_config['name']}"
                        rel = tgt_config["rel_tgt_id"]
                        active_tag = rel if active_node == "A" else rel + REL_TGT_ID_NODEB_OFFSET
                        lun_attr = f"{iscsi_base}/{iqn}/tpgt_{active_tag}/lun/lun_0/alua_tg_pt_gp"
                        # Disabling ALUA collapses the TPG tag to rel_tgt_id
                        # (no node offset) on every node -- see
                        # _build_iscsi_desired() in utils/lio/config.py.
                        non_alua_lun_attr = f"{iscsi_base}/{iqn}/tpgt_{rel}/lun/lun_0/alua_tg_pt_gp"

                        # Baseline: ALUA enabled -- groups present, module loaded.
                        ssh(f"test -d {iblock_base}/{ext_name}/alua/controller_A")
                        ssh(f"test -d {iblock_base}/{ext_name}/alua/controller_B")
                        ssh("test -d /sys/module/lio_ha")

                        # ---- disable ALUA ----
                        call("iscsi.global.update", {"alua": False})
                        _wait_for_alua_settle()

                        # MASTER: groups removed, LUN reassigned to default_tg_pt_gp.
                        ssh(f"test ! -d {iblock_base}/{ext_name}/alua/controller_A")
                        ssh(f"test ! -d {iblock_base}/{ext_name}/alua/controller_B")
                        val = ssh(f"cat {non_alua_lun_attr}").strip()
                        assert "default_tg_pt_gp" in val, f"Expected default_tg_pt_gp after disable, got {val!r}"
                        ssh("test ! -d /sys/module/lio_ha")
                        # STANDBY service was stopped by do_update -- module gone.
                        ssh("test ! -d /sys/module/lio_ha", ip=standby_ip)

                        # ---- re-enable ALUA ----
                        call("iscsi.global.update", {"alua": True})
                        _wait_for_alua_settle()

                        # MASTER: groups restored with correct IDs.
                        for node_ip in (None, standby_ip):
                            ssh(f"test -d {iblock_base}/{ext_name}/alua/controller_A", ip=node_ip)
                            ssh(f"test -d {iblock_base}/{ext_name}/alua/controller_B", ip=node_ip)
                            id_a = ssh(
                                f"cat {iblock_base}/{ext_name}/alua/controller_A/tg_pt_gp_id",
                                ip=node_ip,
                            ).strip()
                            id_b = ssh(
                                f"cat {iblock_base}/{ext_name}/alua/controller_B/tg_pt_gp_id",
                                ip=node_ip,
                            ).strip()
                            assert id_a == str(CONTROLLER_A_TPG_ID), f"node {node_ip}: controller_A id={id_a!r}"
                            assert id_b == str(CONTROLLER_B_TPG_ID), f"node {node_ip}: controller_B id={id_b!r}"
                            ssh("test -d /sys/module/lio_ha", ip=node_ip)

                        # MASTER: LUN reassigned to local controller group.
                        val = ssh(f"cat {lun_attr}").strip()
                        assert f"controller_{active_node}" in val, (
                            f"Expected controller_{active_node} after re-enable, got {val!r}"
                        )

    # -----------------------------------------------------------------------
    # B13: SCST+ALUA -> LIO+ALUA migration (own setup)
    # -----------------------------------------------------------------------

    # B13
    def test_scst_alua_to_lio_alua_identity_stable(self, lio_alua_configured):
        """SCST+ALUA -> LIO+ALUA migration: initiator sees no identity change.

        Verifies TPG IDs, relative port IDs, ALUA states, and NAA are
        stable across the mode switch.  Reuses the class fixture's portal
        and named initiator (private portal would conflict on 0.0.0.0:3260).
        """
        assert call("failover.config")["disabled"] is False
        active_node = call("failover.node")
        active_ip = truenas_server.nodea_ip if active_node == "A" else truenas_server.nodeb_ip
        standby_ip = truenas_server.nodeb_ip if active_node == "A" else truenas_server.nodea_ip
        active_tpg_id = CONTROLLER_A_TPG_ID if active_node == "A" else CONTROLLER_B_TPG_ID

        with zvol_dataset(f"b13{_rnd}", 20, pool_name) as zvol_config:
            with zvol_extent(zvol_config["id"], f"b13ext{_rnd}") as extent_config:
                with target(
                    f"b13tgt{_rnd}",
                    [
                        {
                            "portal": lio_alua_configured["portal"]["id"],
                            "initiator": lio_alua_configured["initiator"]["id"],
                        }
                    ],
                ) as tgt_config:
                    with target_extent_associate(tgt_config["id"], extent_config["id"]):
                        iqn = f"{basename}:{tgt_config['name']}"
                        rtpi_a, rtpi_b = _tpg_port_ids(tgt_config)
                        tpgs = {
                            CONTROLLER_A_TPG_ID: [rtpi_a],
                            CONTROLLER_B_TPG_ID: [rtpi_b],
                        }

                        try:
                            # ---- Switch to SCST+ALUA for the pre-migration baseline ----
                            _stop_service()
                            call(
                                "iscsi.global.update",
                                {
                                    "mode": ISCSIMODE.SCST_DLM_PRSTATE_NOSAVE,
                                    "alua": True,
                                },
                            )
                            _start_service()
                            _wait_for_alua_settle()

                            # Record VPD 0x83 identity and RTPG from each path
                            # under SCST+ALUA.
                            with iscsi_scsi_connection(active_ip, iqn) as s1:
                                pre_active = _device_identification(s1)
                                _verify_rtpg(s1, tpgs, active_tpg_id)
                            with iscsi_scsi_connection(standby_ip, iqn) as s2:
                                pre_standby = _device_identification(s2)

                            # ---- Migrate to LIO+ALUA ----
                            _stop_service()
                            call(
                                "iscsi.global.update",
                                {
                                    "mode": ISCSIMODE.LIO,
                                    "alua": True,
                                },
                            )
                            _start_service()
                            _wait_for_alua_settle()

                            # Verify identity is unchanged after the mode switch.
                            with iscsi_scsi_connection(active_ip, iqn) as s1:
                                post_active = _device_identification(s1)
                                _verify_rtpg(s1, tpgs, active_tpg_id)
                            with iscsi_scsi_connection(standby_ip, iqn) as s2:
                                post_standby = _device_identification(s2)

                            for label, pre, post in (
                                ("active", pre_active, post_active),
                                ("standby", pre_standby, post_standby),
                            ):
                                assert post["naa"] == pre["naa"], (
                                    f"{label}: NAA changed {pre['naa']!r} -> {post['naa']!r}"
                                )
                                assert (
                                    post["relative_target_port_identifier"] == pre["relative_target_port_identifier"]
                                ), (
                                    f"{label}: rtpi changed "
                                    f"{pre['relative_target_port_identifier']!r}"
                                    f" -> {post['relative_target_port_identifier']!r}"
                                )
                                assert post["target_port_group"] == pre["target_port_group"], (
                                    f"{label}: TPG ID changed "
                                    f"{pre['target_port_group']!r}"
                                    f" -> {post['target_port_group']!r}"
                                )

                        finally:
                            # Ensure LIO+ALUA is restored for subsequent tests.
                            current = call("iscsi.global.config")
                            if current["mode"] != ISCSIMODE.LIO or not current["alua"]:
                                _stop_service()
                                call(
                                    "iscsi.global.update",
                                    {
                                        "mode": ISCSIMODE.LIO,
                                        "alua": True,
                                    },
                                )
                                _start_service()
                                _wait_for_alua_settle()

    # -----------------------------------------------------------------------
    # B15: XCOPY
    # -----------------------------------------------------------------------

    # B15
    def test_xcopy_both_paths(self, lio_alua_configured):
        """XCOPY via MASTER (direct) and STANDBY (forwarded through ha_recv).

        Kernel path: target_core_xcopy.c copy manager.
        """
        active_node = call("failover.node")
        active_ip = truenas_server.nodea_ip if active_node == "A" else truenas_server.nodeb_ip
        standby_ip = truenas_server.nodeb_ip if active_node == "A" else truenas_server.nodea_ip

        with zvol_dataset(f"b15a{_rnd}", 20, pool_name) as zvol_a:
            with zvol_dataset(f"b15b{_rnd}", 20, pool_name) as zvol_b:
                with zvol_extent(zvol_a["id"], f"b15exta{_rnd}") as ext_a:
                    with zvol_extent(zvol_b["id"], f"b15extb{_rnd}") as ext_b:
                        with target(
                            f"b15tgt{_rnd}",
                            [
                                {
                                    "portal": lio_alua_configured["portal"]["id"],
                                    "initiator": lio_alua_configured["initiator"]["id"],
                                }
                            ],
                        ) as tgt_config:
                            with target_extent_associate(tgt_config["id"], ext_a["id"], lun_id=0):
                                with target_extent_associate(tgt_config["id"], ext_b["id"], lun_id=1):
                                    iqn = f"{basename}:{tgt_config['name']}"
                                    with (
                                        iscsi_scsi_connection(active_ip, iqn, lun=0) as m0,
                                        iscsi_scsi_connection(active_ip, iqn, lun=1) as m1,
                                        iscsi_scsi_connection(standby_ip, iqn, lun=0) as s0,
                                        iscsi_scsi_connection(standby_ip, iqn, lun=1) as s1,
                                    ):
                                        d0 = _get_designator(m0, 3)
                                        d1 = _get_designator(m1, 3)
                                        zeros = bytearray(512)
                                        pattern_m = bytearray.fromhex("cafebabe") * 128
                                        pattern_s = bytearray.fromhex("deadbeef") * 128

                                        # Step 1 -- XCOPY via MASTER (direct execution).
                                        m1.writesame16(0, 1, zeros)
                                        m0.write16(0, 1, pattern_m)
                                        _xcopy_one_block(m0, d0, d1, 0, 0)
                                        assert m1.read16(0, 1).datain == pattern_m, (
                                            "XCOPY via MASTER did not copy the expected pattern"
                                        )

                                        # Step 2 -- XCOPY via STANDBY (forwarded to MASTER;
                                        # MASTER's copy manager resolves both LUN designators
                                        # locally and performs the copy against its own
                                        # open backends).
                                        m1.writesame16(0, 1, zeros)
                                        m0.write16(0, 1, pattern_s)
                                        _xcopy_one_block(s0, d0, d1, 0, 0)
                                        assert m1.read16(0, 1).datain == pattern_s, (
                                            "XCOPY via STANDBY did not copy the expected pattern (MASTER path)"
                                        )
                                        assert s1.read16(0, 1).datain == pattern_s, (
                                            "XCOPY via STANDBY did not copy the expected pattern (STANDBY path)"
                                        )

    # -----------------------------------------------------------------------
    # B16: SYNCHRONIZE CACHE
    # -----------------------------------------------------------------------

    # B16
    def test_synchronize_cache_both_paths(self, lio_alua_configured):
        """SYNCHRONIZE CACHE via MASTER and STANDBY; verified on-disk via dd O_DIRECT.

        Kernel path: iblock execute_sync_cache() on ACTIVE for both the direct
        (MASTER) and forwarded (STANDBY) cases.  On-disk verification uses
        dd iflag=direct on the TrueNAS node to bypass the page cache, confirming
        the data was durably committed before the SYNC CACHE response returned.
        """
        active_node = call("failover.node")
        active_ip = truenas_server.nodea_ip if active_node == "A" else truenas_server.nodeb_ip
        standby_ip = truenas_server.nodeb_ip if active_node == "A" else truenas_server.nodea_ip

        with zvol_dataset(f"b16{_rnd}", 20, pool_name) as zvol_config:
            with zvol_extent(zvol_config["id"], f"b16ext{_rnd}") as extent_config:
                with target(
                    f"b16tgt{_rnd}",
                    [
                        {
                            "portal": lio_alua_configured["portal"]["id"],
                            "initiator": lio_alua_configured["initiator"]["id"],
                        }
                    ],
                ) as tgt_config:
                    with target_extent_associate(tgt_config["id"], extent_config["id"]):
                        iqn = f"{basename}:{tgt_config['name']}"
                        zvol_path = f"/dev/zvol/{zvol_config['name']}"
                        pattern_m = bytearray.fromhex("cafebabe") * 128  # 512 bytes
                        pattern_s = bytearray.fromhex("deadbeef") * 128  # 512 bytes

                        with iscsi_scsi_connection(active_ip, iqn) as s_m:
                            with iscsi_scsi_connection(standby_ip, iqn) as s_s:
                                # Write via MASTER, flush via MASTER, verify on-disk.
                                s_m.write16(0, 1, pattern_m)
                                s_m.synchronizecache10(0, 0)
                                on_disk = ssh(
                                    f"dd if={zvol_path} bs=512 count=1 iflag=direct 2>/dev/null"
                                    f' | od -An -tx1 -v | tr -d " \\n"'
                                ).strip()
                                assert on_disk == pattern_m.hex(), (
                                    "MASTER SYNC CACHE: on-disk block does not match written pattern"
                                )

                                # Write via STANDBY, flush via STANDBY, verify on-disk.
                                s_s.write16(0, 1, pattern_s)
                                s_s.synchronizecache10(0, 0)
                                on_disk = ssh(
                                    f"dd if={zvol_path} bs=512 count=1 iflag=direct 2>/dev/null"
                                    f' | od -An -tx1 -v | tr -d " \\n"'
                                ).strip()
                                assert on_disk == pattern_s.hex(), (
                                    "STANDBY SYNC CACHE: on-disk block does not match written pattern"
                                )

    # -----------------------------------------------------------------------
    # B17: TMR forwarding
    # -----------------------------------------------------------------------

    # B17
    @pytest.mark.timeout(120)
    def test_tmr_lun_reset_forwarding(self, lio_alua_configured):
        """TMR forwarding -- LUN RESET via STANDBY.

        Kernel path: target_tmr_work() interception via lio_ha_forward_active.
        A LUN RESET is issued through the STANDBY node, which must forward it
        to the ACTIVE node and return the response: the ACTIVE node's reset
        count for the device must rise by one (a STANDBY that handled it
        locally would still answer, but nothing would be reset).  A
        persistent reservation is not affected by LUN RESET, and I/O must
        behave as before through both ports afterwards.
        """
        key = 0x1111
        resets_path = f"{IBLOCK_BASE}/b17ext{_rnd}/statistics/scsi_lu/resets"
        active_node = call("failover.node")
        active_ip = truenas_server.nodea_ip if active_node == "A" else truenas_server.nodeb_ip
        standby_ip = truenas_server.nodeb_ip if active_node == "A" else truenas_server.nodea_ip

        with zvol_dataset(f"b17{_rnd}", 20, pool_name) as zvol_config:
            with zvol_extent(zvol_config["id"], f"b17ext{_rnd}") as extent_config:
                with target(
                    f"b17tgt{_rnd}",
                    [
                        {
                            "portal": lio_alua_configured["portal"]["id"],
                            "initiator": lio_alua_configured["initiator"]["id"],
                        }
                    ],
                ) as tgt_config:
                    with target_extent_associate(tgt_config["id"], extent_config["id"]):
                        iqn = f"{basename}:{tgt_config['name']}"
                        reservation = {"reservation_key": key, "type": PR_TYPE.WRITE_EXCLUSIVE, "scope": LU_SCOPE}
                        with (
                            open_nexus(active_ip, iqn, qualifier=1) as holder,
                            open_nexus(standby_ip, iqn, qualifier=2) as via_standby,
                            open_nexus(active_ip, iqn, qualifier=3) as observer,
                        ):
                            for session in (holder, via_standby, observer):
                                drain_ua(session)
                            pr_register_key(holder, key)
                            pr_reserve(holder, PR_TYPE.WRITE_EXCLUSIVE, key)
                            assert io_access(holder) == (True, True)
                            assert io_access(via_standby) == (True, False)

                            resets_before = int(ssh(f"cat {resets_path}", ip=active_ip))
                            # Forwarded to the ACTIVE node; returns once its
                            # response arrives.
                            # lun_reset() exists only in a patched pyscsi.
                            lun_reset = getattr(via_standby.conn.device, "lun_reset", None)
                            if lun_reset is None:
                                pytest.skip("this pyscsi cannot send a LUN RESET")
                            try:
                                lun_reset()
                            except NotImplementedError as e:
                                pytest.skip(str(e))
                            resets_after = int(ssh(f"cat {resets_path}", ip=active_ip))
                            assert resets_after == resets_before + 1, (
                                f"ACTIVE node reset count {resets_before} -> {resets_after}, expected one more"
                            )

                            for session in (holder, via_standby, observer):
                                drain_ua(session)
                            assert_registrations(observer, [(key, None, 1)])
                            pr_check_reservation(observer, reservation)
                            assert io_access(holder) == (True, True)
                            assert io_access(via_standby) == (True, False)
                            assert io_access(observer) == (True, False)

    # -----------------------------------------------------------------------
    # B18: VPD pages via STANDBY
    # -----------------------------------------------------------------------

    # B18
    def test_vpd_pages_via_standby(self, lio_alua_configured):
        """VPD 0x83/0x80/0xB0 responses via STANDBY are correct.

        Kernel path: lio_ha_replace_port_info() patches Relative Target Port,
        Target Port Group, and SCSI name string designators in VPD 0x83 to
        reflect STANDBY's tpg_rtpi.  VPD 0x80 and 0xB0 pass through unchanged
        (same raw bytes from both paths).
        """
        active_node = call("failover.node")
        active_ip = truenas_server.nodea_ip if active_node == "A" else truenas_server.nodeb_ip
        standby_ip = truenas_server.nodeb_ip if active_node == "A" else truenas_server.nodea_ip
        active_tpg_id = CONTROLLER_A_TPG_ID if active_node == "A" else CONTROLLER_B_TPG_ID
        standby_tpg_id = CONTROLLER_B_TPG_ID if active_node == "A" else CONTROLLER_A_TPG_ID

        with zvol_dataset(f"b18{_rnd}", 20, pool_name) as zvol_config:
            with zvol_extent(zvol_config["id"], f"b18ext{_rnd}") as extent_config:
                with target(
                    f"b18tgt{_rnd}",
                    [
                        {
                            "portal": lio_alua_configured["portal"]["id"],
                            "initiator": lio_alua_configured["initiator"]["id"],
                        }
                    ],
                ) as tgt_config:
                    with target_extent_associate(tgt_config["id"], extent_config["id"]):
                        iqn = f"{basename}:{tgt_config['name']}"
                        rtpi_a, rtpi_b = _tpg_port_ids(tgt_config)
                        active_rtpi = rtpi_a if active_node == "A" else rtpi_b
                        standby_rtpi = rtpi_b if active_node == "A" else rtpi_a

                        with iscsi_scsi_connection(active_ip, iqn) as s_m:
                            with iscsi_scsi_connection(standby_ip, iqn) as s_s:
                                vpd_m = _device_identification(s_m)
                                vpd_s = _device_identification(s_s)

                                # NAA: device-wide, identical from both paths.
                                assert vpd_m["naa"] == vpd_s["naa"], (
                                    f"NAA mismatch: {vpd_m['naa']!r} vs {vpd_s['naa']!r}"
                                )

                                # Relative Target Port: each path reports its own RTPI.
                                assert vpd_m["relative_target_port_identifier"] == active_rtpi, (
                                    f"MASTER RTPI: expected {active_rtpi:#x}, "
                                    f"got {vpd_m['relative_target_port_identifier']:#x}"
                                )
                                assert vpd_s["relative_target_port_identifier"] == standby_rtpi, (
                                    f"STANDBY RTPI: expected {standby_rtpi:#x}, "
                                    f"got {vpd_s['relative_target_port_identifier']:#x}"
                                )

                                # Target Port Group: each path reports its own group.
                                assert vpd_m["target_port_group"] == active_tpg_id, (
                                    f"MASTER TPG: expected {active_tpg_id:#x}, got {vpd_m['target_port_group']:#x}"
                                )
                                assert vpd_s["target_port_group"] == standby_tpg_id, (
                                    f"STANDBY TPG: expected {standby_tpg_id:#x}, got {vpd_s['target_port_group']:#x}"
                                )

                                # SCSI name string: ',t,0x{tag}' suffix must match RTPI.
                                # lio_ha_replace_port_info() patches this in-place on STANDBY.
                                ns_tag_m = _scsi_name_string_tag(s_m)
                                ns_tag_s = _scsi_name_string_tag(s_s)
                                assert ns_tag_m == active_rtpi, (
                                    f"MASTER SCSI name tag: expected {active_rtpi:#x}, got {ns_tag_m!r}"
                                )
                                assert ns_tag_s == standby_rtpi, (
                                    f"STANDBY SCSI name tag: expected {standby_rtpi:#x}, got {ns_tag_s!r}"
                                )

                                # VPD 0x80 (Unit Serial Number): same from both paths.
                                assert _serial_number(s_m) == _serial_number(s_s), (
                                    "VPD 0x80 serial mismatch between MASTER and STANDBY"
                                )

                                # VPD 0xB0 (Block Limits): identical raw bytes from both paths.
                                b0_m = s_m.inquiry(evpd=1, page_code=0xB0).datain
                                b0_s = s_s.inquiry(evpd=1, page_code=0xB0).datain
                                assert b0_m == b0_s, "VPD 0xB0 mismatch between MASTER and STANDBY"

    # -----------------------------------------------------------------------
    # B19: REPORT LUNS via STANDBY
    # -----------------------------------------------------------------------

    # B19
    def test_report_luns_via_standby(self, lio_alua_configured):
        """REPORT LUNS via STANDBY returns same live LUN list as MASTER.

        Kernel path: emulated REPORT LUNS handler forwarded via ha_recv;
        verifies live state including after LUN removal.

        Phase 1: two LUNs (0, 1) — both paths see {0, 1}.
        Phase 2: LUN 1 removed — both paths see {0} without reconnect.
        """
        active_node = call("failover.node")
        active_ip = truenas_server.nodea_ip if active_node == "A" else truenas_server.nodeb_ip
        standby_ip = truenas_server.nodeb_ip if active_node == "A" else truenas_server.nodea_ip

        with zvol_dataset(f"b19a{_rnd}", 20, pool_name) as zvol_a:
            with zvol_dataset(f"b19b{_rnd}", 20, pool_name) as zvol_b:
                with zvol_extent(zvol_a["id"], f"b19exta{_rnd}") as ext_a:
                    with zvol_extent(zvol_b["id"], f"b19extb{_rnd}") as ext_b:
                        with target(
                            f"b19tgt{_rnd}",
                            [
                                {
                                    "portal": lio_alua_configured["portal"]["id"],
                                    "initiator": lio_alua_configured["initiator"]["id"],
                                }
                            ],
                        ) as tgt_config:
                            iqn = f"{basename}:{tgt_config['name']}"
                            with target_extent_associate(tgt_config["id"], ext_a["id"], lun_id=0):
                                with target_extent_associate(tgt_config["id"], ext_b["id"], lun_id=1):
                                    # Phase 1: both LUNs present — MASTER and STANDBY agree.
                                    with iscsi_scsi_connection(active_ip, iqn) as s_m:
                                        with iscsi_scsi_connection(standby_ip, iqn) as s_s:
                                            luns_m = _report_luns(s_m)
                                            luns_s = _report_luns(s_s)
                                            assert luns_m == {0, 1}, (
                                                f"MASTER REPORT LUNS: expected {{0, 1}}, got {luns_m}"
                                            )
                                            assert luns_s == {0, 1}, (
                                                f"STANDBY REPORT LUNS: expected {{0, 1}}, got {luns_s}"
                                            )

                                # Phase 2: LUN 1 (assoc_b) removed by exiting its context manager.
                                # Open fresh connections so REPORT LUNS reflects current state.
                                with iscsi_scsi_connection(active_ip, iqn) as s_m:
                                    with iscsi_scsi_connection(standby_ip, iqn) as s_s:
                                        luns_m = _report_luns(s_m)
                                        luns_s = _report_luns(s_s)
                                        assert luns_m == {0}, (
                                            f"MASTER REPORT LUNS after removal: expected {{0}}, got {luns_m}"
                                        )
                                        assert luns_s == {0}, (
                                            f"STANDBY REPORT LUNS after removal: expected {{0}}, got {luns_s}"
                                        )

    # -----------------------------------------------------------------------
    # B20: CHECK CONDITION propagation via STANDBY
    # -----------------------------------------------------------------------

    # B20
    def test_check_condition_via_standby(self, lio_alua_configured):
        """CHECK CONDITION sense data forwarded correctly from ACTIVE to STANDBY.

        Kernel path: ha_fwd_cmd_response_handler() memcpy of sense_len bytes +
        SCF_TRANSPORT_TASK_SENSE flag so the transport delivers the forwarded
        sense data rather than synthesising a generic HARDWARE ERROR.

        Trigger: READ 16 with LBA beyond end of device -> ILLEGAL REQUEST /
        LOGICAL BLOCK ADDRESS OUT OF RANGE (sense key 5, ASCQ 0x2100).
        Verified from MASTER path (direct execution, baseline) then STANDBY
        path (forwarded via ha_recv on ACTIVE, response returned to STANDBY).
        """
        active_node = call("failover.node")
        active_ip = truenas_server.nodea_ip if active_node == "A" else truenas_server.nodeb_ip
        standby_ip = truenas_server.nodeb_ip if active_node == "A" else truenas_server.nodea_ip

        with zvol_dataset(f"b20{_rnd}", 20, pool_name) as zvol_config:
            with zvol_extent(zvol_config["id"], f"b20ext{_rnd}") as extent_config:
                with target(
                    f"b20tgt{_rnd}",
                    [
                        {
                            "portal": lio_alua_configured["portal"]["id"],
                            "initiator": lio_alua_configured["initiator"]["id"],
                        }
                    ],
                ) as tgt_config:
                    with target_extent_associate(tgt_config["id"], extent_config["id"]):
                        iqn = f"{basename}:{tgt_config['name']}"
                        with iscsi_scsi_connection(active_ip, iqn) as s_m:
                            with iscsi_scsi_connection(standby_ip, iqn) as s_s:
                                max_lba = s_m.readcapacity16().result["returned_lba"]

                                # MASTER path: baseline, direct execution on ACTIVE.
                                with pytest.raises(Exception) as exc:
                                    s_m.read16(max_lba + 1, 1)
                                assert "0x2100" in str(exc.value), (
                                    f"MASTER: expected LOGICAL BLOCK ADDRESS OUT OF RANGE "
                                    f"(ASCQ 0x2100), got: {exc.value}"
                                )

                                # STANDBY path: forwarded; sense data must survive the
                                # ha_fwd_cmd_response_handler memcpy to reach the initiator.
                                with pytest.raises(Exception) as exc:
                                    s_s.read16(max_lba + 1, 1)
                                assert "0x2100" in str(exc.value), (
                                    f"STANDBY: expected LOGICAL BLOCK ADDRESS OUT OF RANGE "
                                    f"(ASCQ 0x2100), got: {exc.value}"
                                )

    # -----------------------------------------------------------------------
    # B21: Extent resize notifies multiple clients on both paths
    # -----------------------------------------------------------------------

    # B21
    def test_resize_notifies_multiple_clients_both_paths(self, lio_alua_configured):
        """Resizing the backing zvol notifies every connected client on both
        MASTER and STANDBY paths via CAPACITY DATA HAS CHANGED.

        Kernel path: iblock's "rescan=1" control token -> target_dev_ua_allocate()
        broadcasts the UA to every I_T nexus on every LUN exporting the device.
        LIO's UA delivery is pull-based (surfaced only on each nexus's own next
        command) -- unlike SCST there is no separate AEN push to disable for
        determinism.
        """
        active_node = call("failover.node")
        active_ip = truenas_server.nodea_ip if active_node == "A" else truenas_server.nodeb_ip
        standby_ip = truenas_server.nodeb_ip if active_node == "A" else truenas_server.nodea_ip
        pattern = bytearray.fromhex("deadbeef") * 128

        def _check_write_lba_limits(s, num_bytes):
            max_lba = num_bytes // 512 - 1
            s.write16(0, 1, pattern)
            s.write16(max_lba, 1, pattern)
            with pytest.raises(Exception) as exc:
                s.write16(max_lba + 1, 1, pattern)
            assert "0x2100" in str(exc.value), (
                f"Expected LOGICAL BLOCK ADDRESS OUT OF RANGE (ASCQ 0x2100), got: {exc.value}"
            )

        with zvol_dataset(f"b21{_rnd}", 20, pool_name) as zvol_config:
            with zvol_extent(zvol_config["id"], f"b21ext{_rnd}") as extent_config:
                with target(
                    f"b21tgt{_rnd}",
                    [
                        {
                            "portal": lio_alua_configured["portal"]["id"],
                            "initiator": lio_alua_configured["initiator"]["id"],
                        }
                    ],
                ) as tgt_config:
                    with target_extent_associate(tgt_config["id"], extent_config["id"]):
                        iqn = f"{basename}:{tgt_config['name']}"
                        # Two clients per node -- verifies the UA broadcast reaches
                        # every I_T nexus, not just the first one found.
                        with (
                            iscsi_scsi_connection(active_ip, iqn) as a1,
                            iscsi_scsi_connection(active_ip, iqn) as a2,
                            iscsi_scsi_connection(standby_ip, iqn) as s1,
                            iscsi_scsi_connection(standby_ip, iqn) as s2,
                        ):
                            sessions = (a1, a2, s1, s2)

                            for s in sessions:
                                try:
                                    s.testunitready()
                                except Exception:
                                    pass  # clear any stale UA from session establishment
                                assert s.readcapacity16().result["returned_lba"] == 20 * MB // 512 - 1
                                _check_write_lba_limits(s, 20 * MB)

                            call("pool.dataset.update", zvol_config["name"], {"volsize": 40 * MB})

                            for s in sessions:
                                with pytest.raises(Exception) as exc:
                                    s.testunitready()
                                assert "0x2A09" in str(exc.value), (
                                    f"Expected CAPACITY DATA HAS CHANGED (ASCQ 0x2A09), got: {exc.value}"
                                )
                                assert s.readcapacity16().result["returned_lba"] == 40 * MB // 512 - 1
                                _check_write_lba_limits(s, 40 * MB)
