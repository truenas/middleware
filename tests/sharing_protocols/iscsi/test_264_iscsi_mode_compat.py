"""
test_264_iscsi_mode_compat.py

Cross-mode compatibility suite for iSCSI target stacks.

Validates that client-visible behaviour is consistent across ISCSIMODEs.
The primary guard: a customer switching from SCST to LIO must not encounter
a regression in any area covered here.

One service restart per mode; all targets and extents are created once and
shared across all mode iterations.
"""

import contextlib
import random
import string
from time import sleep

import pytest

from assets.websocket.iscsi import (
    TUR,
    _device_identification,
    _serial_number,
    initiator,
    portal,
    target,
    target_extent_associate,
    verify_capacity,
    verify_luns,
    zvol_extent,
)
from assets.websocket.pool import zvol as zvol_dataset
from assets.websocket.service import ensure_service_enabled
from auto_config import pool_name
from middlewared.test.integration.utils import call
from middlewared.test.integration.utils.client import truenas_server
from protocols import ISCSIDiscover, iscsi_scsi_connection


class ISCSIMODE:
    SCST_DLM_PRSTATE_SAVE = 0
    SCST_DLM_PRSTATE_NOSAVE = 1
    LIO = 2


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SERVICE_NAME = 'iscsitarget'
MB = 1024 * 1024
basename = 'iqn.2005-10.org.freenas.ctl'

MODES_UNDER_TEST = [
    ISCSIMODE.SCST_DLM_PRSTATE_SAVE,  # 0 -- default SCST
    ISCSIMODE.LIO,  # 2
]
MODE_IDS = {
    ISCSIMODE.SCST_DLM_PRSTATE_SAVE: 'scst',
    ISCSIMODE.LIO: 'lio',
}

# Random suffix to avoid name collisions with other test modules running
# in the same environment.
_rnd = ''.join(random.choices(string.digits, k=4))

# Target names and IQNs
T_BASIC = f'mc{_rnd}basic'
IQN_BASIC = f'{basename}:{T_BASIC}'

T_CHAP = f'mc{_rnd}chap'
IQN_CHAP = f'{basename}:{T_CHAP}'

# Zvol sizes (MB)
SIZE_BASIC = 256
SIZE_CHAP = 64

# CHAP credentials for t_chap (14 chars -- within the 12-16 char API requirement)
CHAP_USER = f'mc{_rnd}user'
CHAP_SECRET = f'mc{_rnd}secret12'

# Specific initiator IQN for the CHAP target.
# LIO requires static ACLs (specific IQN) for CHAP credential verification;
# dynamic ACLs (generate_node_acls=1) have empty credentials and reject everyone.
CHAP_INITIATOR_IQN = f'iqn.2005-10.org.freenas.ctl:mc{_rnd}init'

T_MUTUAL = f'mc{_rnd}mutual'
IQN_MUTUAL = f'{basename}:{T_MUTUAL}'
SIZE_MUTUAL = 64

# Mutual CHAP credentials (12-16 chars each; peersecret must differ from secret)
# user/secret    -- initiator proves itself to the target
# peer_user/peer_secret -- target proves itself to the initiator
MUTUAL_USER = f'mc{_rnd}mutuser'  # 13 chars
MUTUAL_SECRET = f'mc{_rnd}mutsec01'  # 14 chars
MUTUAL_PEER_USER = f'mc{_rnd}tgtuser'  # 13 chars
MUTUAL_PEER_SECRET = f'mc{_rnd}tgtsec01'  # 14 chars; differs from MUTUAL_SECRET
MUTUAL_INITIATOR_IQN = f'iqn.2005-10.org.freenas.ctl:mc{_rnd}mutinit'

T_MULTILUN = f'mc{_rnd}ml'
IQN_MULTILUN = f'{basename}:{T_MULTILUN}'
# Three LUNs of distinct sizes so per-LUN capacity tests are unambiguous.
# Index == LUN ID (LUN 0 = 64 MB, LUN 1 = 128 MB, LUN 2 = 192 MB).
ML_LUN_SIZES = [64, 128, 192]  # MB

T_NOLUN0 = f'mc{_rnd}nl0'
IQN_NOLUN0 = f'{basename}:{T_NOLUN0}'
SIZE_NOLUN0 = 64  # MB
NOLUN0_LUN_ID = 1  # only LUN on this target; LUN 0 is intentionally absent

T_ACL = f'mc{_rnd}acl'
IQN_ACL = f'{basename}:{T_ACL}'
SIZE_ACL = 64  # MB

# The IQN that is explicitly permitted on the ACL target.
ACL_INITIATOR_IQN = f'iqn.2005-10.org.freenas.ctl:mc{_rnd}aclinit'
# A different IQN that is NOT in the ACL -- must be rejected.
ACL_UNLISTED_IQN = f'iqn.2005-10.org.freenas.ctl:mc{_rnd}notlisted'

# Discovery CHAP credentials (tag 3 -- distinct from target CHAP tags 1 and 2).
DISC_USER = f'mc{_rnd}discusr'  # 13 chars
DISC_SECRET = f'mc{_rnd}discsec0'  # 14 chars

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_designator(s, designator_type):
    """Return the first VPD 0x83 designator matching designator_type."""
    x = s.inquiry(evpd=1, page_code=0x83)
    for designator in x.result['designator_descriptors']:
        if designator['designator_type'] == designator_type:
            del designator['piv']
            return designator


@contextlib.contextmanager
def _snapshot(dataset, name):
    """Create a ZFS snapshot; delete it on exit (survives rollback)."""
    snap_id = f'{dataset}@{name}'
    call('pool.snapshot.create', {'dataset': dataset, 'name': name})
    try:
        yield snap_id
    finally:
        with contextlib.suppress(Exception):
            call('pool.snapshot.delete', snap_id)


@contextlib.contextmanager
def iscsi_auth(tag, user, secret, **kwargs):
    auth_config = call(
        'iscsi.auth.create', {'tag': tag, 'user': user, 'secret': secret, **kwargs}
    )
    try:
        yield auth_config
    finally:
        call('iscsi.auth.delete', auth_config['id'])


def _vendor_nibbles_from_naa(naa_hex):
    """Extract the 25-char vendor-specific field from a TrueNAS NAA hex string.

    The stored NAA format is "0x" + 32 hex chars:
      1 nibble : NAA type (6)
      6 nibbles: IEEE company ID
      25 nibbles: vendor-specific field (written to LIO wwn/vpd_unit_serial)

    LIO returns these 25 chars as the VPD page 0x80 Unit Serial Number.
    """
    # skip "0x" (2) + NAA nibble (1) + company ID (6) = 9 chars
    return naa_hex[9:]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope='module')
def saved_iscsi_mode():
    """Save the current iSCSI mode and service state; restore both on teardown."""
    cfg = call('iscsi.global.config')
    original_mode = cfg['mode']
    was_running = call('service.started', SERVICE_NAME)
    try:
        yield
    finally:
        call('service.control', 'STOP', SERVICE_NAME, job=True)
        call('iscsi.global.update', {'mode': original_mode})
        if was_running:
            call('service.control', 'START', SERVICE_NAME, job=True)


@pytest.fixture(scope='module')
def iscsi_config(saved_iscsi_mode):
    """Create a minimal set of targets and extents once for the entire module."""
    with contextlib.ExitStack() as stack:
        stack.enter_context(ensure_service_enabled(SERVICE_NAME))

        # One wildcard portal and one open initiator group for non-CHAP targets.
        p_wild = stack.enter_context(portal(comment=f'mc{_rnd}-wildcard'))
        init_open = stack.enter_context(initiator(comment=f'mc{_rnd}-open'))
        # Named initiator group for the CHAP target -- LIO requires a static ACL
        # (specific IQN) to have per-ACL credentials for CHAP_N verification.
        init_chap = stack.enter_context(
            initiator(comment=f'mc{_rnd}-chap', initiators=[CHAP_INITIATOR_IQN])
        )
        init_mutual = stack.enter_context(
            initiator(comment=f'mc{_rnd}-mutual', initiators=[MUTUAL_INITIATOR_IQN])
        )
        init_acl = stack.enter_context(
            initiator(comment=f'mc{_rnd}-acl', initiators=[ACL_INITIATOR_IQN])
        )

        p_wild_id = p_wild['id']
        init_open_id = init_open['id']
        init_chap_id = init_chap['id']
        init_mutual_id = init_mutual['id']
        init_acl_id = init_acl['id']

        # ---- t_basic: single LUN 0, no auth ----
        zv_basic = stack.enter_context(
            zvol_dataset(f'{pool_name}/mc{_rnd}ba', SIZE_BASIC)
        )
        ext_basic = stack.enter_context(
            zvol_extent(f'{pool_name}/mc{_rnd}ba', f'mcext{_rnd}ba')
        )
        t_basic = stack.enter_context(
            target(T_BASIC, [{'portal': p_wild_id, 'initiator': init_open_id}])
        )
        stack.enter_context(target_extent_associate(t_basic['id'], ext_basic['id'], 0))

        # ---- t_chap: single LUN 0, CHAP auth ----
        auth_chap = stack.enter_context(iscsi_auth(1, CHAP_USER, CHAP_SECRET))
        stack.enter_context(zvol_dataset(f'{pool_name}/mc{_rnd}ch', SIZE_CHAP))
        ext_chap = stack.enter_context(
            zvol_extent(f'{pool_name}/mc{_rnd}ch', f'mcext{_rnd}ch')
        )
        t_chap_obj = stack.enter_context(
            target(
                T_CHAP,
                [
                    {
                        'portal': p_wild_id,
                        'initiator': init_chap_id,
                        'authmethod': 'CHAP',
                        'auth': auth_chap['tag'],
                    }
                ],
            )
        )
        stack.enter_context(
            target_extent_associate(t_chap_obj['id'], ext_chap['id'], 0)
        )

        # ---- t_mutual: single LUN 0, mutual CHAP ----
        auth_mutual = stack.enter_context(
            iscsi_auth(
                2,
                MUTUAL_USER,
                MUTUAL_SECRET,
                peeruser=MUTUAL_PEER_USER,
                peersecret=MUTUAL_PEER_SECRET,
            )
        )
        stack.enter_context(zvol_dataset(f'{pool_name}/mc{_rnd}mu', SIZE_MUTUAL))
        ext_mutual = stack.enter_context(
            zvol_extent(f'{pool_name}/mc{_rnd}mu', f'mcext{_rnd}mu')
        )
        t_mutual_obj = stack.enter_context(
            target(
                T_MUTUAL,
                [
                    {
                        'portal': p_wild_id,
                        'initiator': init_mutual_id,
                        'authmethod': 'CHAP_MUTUAL',
                        'auth': auth_mutual['tag'],
                    }
                ],
            )
        )
        stack.enter_context(
            target_extent_associate(t_mutual_obj['id'], ext_mutual['id'], 0)
        )

        # ---- t_multilun: 3 LUNs (IDs 0/1/2) of different sizes ----
        ext_ml = []
        for i, sz in enumerate(ML_LUN_SIZES):
            stack.enter_context(zvol_dataset(f'{pool_name}/mc{_rnd}ml{i}', sz))
            ext_ml.append(
                stack.enter_context(
                    zvol_extent(f'{pool_name}/mc{_rnd}ml{i}', f'mcext{_rnd}ml{i}')
                )
            )
        t_multilun = stack.enter_context(
            target(T_MULTILUN, [{'portal': p_wild_id, 'initiator': init_open_id}])
        )
        for lun_id, ex in enumerate(ext_ml):
            stack.enter_context(
                target_extent_associate(t_multilun['id'], ex['id'], lun_id)
            )

        # ---- t_nolun0: single LUN at ID 1; LUN 0 intentionally absent ----
        stack.enter_context(zvol_dataset(f'{pool_name}/mc{_rnd}nl0', SIZE_NOLUN0))
        ext_nolun0 = stack.enter_context(
            zvol_extent(f'{pool_name}/mc{_rnd}nl0', f'mcext{_rnd}nl0')
        )
        t_nolun0 = stack.enter_context(
            target(T_NOLUN0, [{'portal': p_wild_id, 'initiator': init_open_id}])
        )
        stack.enter_context(
            target_extent_associate(t_nolun0['id'], ext_nolun0['id'], NOLUN0_LUN_ID)
        )

        # ---- t_acl: single LUN 0, no auth, named initiator group ----
        stack.enter_context(zvol_dataset(f'{pool_name}/mc{_rnd}ac', SIZE_ACL))
        ext_acl = stack.enter_context(
            zvol_extent(f'{pool_name}/mc{_rnd}ac', f'mcext{_rnd}ac')
        )
        t_acl = stack.enter_context(
            target(T_ACL, [{'portal': p_wild_id, 'initiator': init_acl_id}])
        )
        stack.enter_context(target_extent_associate(t_acl['id'], ext_acl['id'], 0))

        # ---- discovery auth: enforces CHAP on SendTargets ----
        stack.enter_context(
            iscsi_auth(3, DISC_USER, DISC_SECRET, discovery_auth='CHAP')
        )

        try:
            yield {
                'ip': truenas_server.ip,
                'portal_id': p_wild_id,
                'initiator_id': init_open_id,
                'targets': {
                    'basic': {
                        'iqn': IQN_BASIC,
                        'extent': ext_basic,
                        'zvol': zv_basic['id'],
                        'size_mb': SIZE_BASIC,
                    },
                    'chap': {
                        'iqn': IQN_CHAP,
                    },
                    'mutual': {
                        'iqn': IQN_MUTUAL,
                    },
                    'multilun': {
                        'iqn': IQN_MULTILUN,
                        'lun_sizes_mb': ML_LUN_SIZES,
                    },
                    'nolun0': {
                        'iqn': IQN_NOLUN0,
                        'lun_id': NOLUN0_LUN_ID,
                        'size_mb': SIZE_NOLUN0,
                    },
                    'acl': {
                        'iqn': IQN_ACL,
                    },
                },
            }
        finally:
            # Stop the service before ExitStack tears down targets/extents/zvols.
            # The service holds these resources in its config; deletion may fail
            # while it is running.
            call('service.control', 'STOP', SERVICE_NAME, job=True)


@pytest.fixture(
    scope='module',
    params=MODES_UNDER_TEST,
    ids=[MODE_IDS[m] for m in MODES_UNDER_TEST],
)
def active_mode(request, iscsi_config):
    """Switch ISCSIMODE and restart the service. One restart per mode value."""
    mode = request.param
    call('service.control', 'STOP', SERVICE_NAME, job=True)
    call('iscsi.global.update', {'mode': mode})
    call('service.control', 'START', SERVICE_NAME, job=True)
    sleep(5)
    yield mode


# ---------------------------------------------------------------------------
# t_basic -- standard INQUIRY and VPD pages
# ---------------------------------------------------------------------------


def test_standard_inquiry(iscsi_config, active_mode):
    """Standard INQUIRY: vendor, product_id, and revision must be non-empty;
    product_id must match the value stored in the database.
    """
    cfg = iscsi_config['targets']['basic']
    extent_data = call(
        'iscsi.extent.query',
        [['name', '=', cfg['extent']['name']]],
        {'get': True},
    )
    db_product_id = extent_data['product_id']

    with iscsi_scsi_connection(iscsi_config['ip'], cfg['iqn']) as s:
        TUR(s)
        data = s.inquiry().result

    vendor = data['t10_vendor_identification'].decode('utf-8').strip()
    product = data['product_identification'].decode('utf-8').strip()
    revision = data['product_revision_level'].decode('utf-8').strip()

    assert vendor, f'mode={active_mode}: vendor_id is empty'
    assert product, f'mode={active_mode}: product_id is empty'
    assert revision, f'mode={active_mode}: product_revision_level is empty'
    assert product == db_product_id, (
        f'mode={active_mode}: product_id mismatch -- '
        f'wire={product!r}  db={db_product_id!r}'
    )


def test_vpd_0x83_naa(iscsi_config, active_mode):
    """VPD page 0x83 NAA designator must match the stored TrueNAS NAA for all modes.

    This is the key migration invariant: switching from SCST to LIO must not
    change the device identity seen by initiators.
    """
    cfg = iscsi_config['targets']['basic']
    extent_data = call(
        'iscsi.extent.query',
        [['name', '=', cfg['extent']['name']]],
        {'get': True},
    )
    expected_naa = extent_data['naa']

    with iscsi_scsi_connection(iscsi_config['ip'], cfg['iqn']) as s:
        TUR(s)
        wire = _device_identification(s)

    assert 'naa' in wire, f'No NAA designator in VPD 0x83 response: {wire}'
    assert wire['naa'] == expected_naa, (
        f'mode={active_mode}: VPD 0x83 NAA mismatch -- '
        f'wire={wire["naa"]!r}  db={expected_naa!r}'
    )


def test_vpd_0x80_serial(iscsi_config, active_mode):
    """VPD page 0x80 Unit Serial Number: assert the per-mode expected value.

    SCST returns the human-readable serial UUID stored in the database.
    LIO returns the 25-char vendor-nibble hex derived from the stored NAA
    (written to wwn/vpd_unit_serial at config time).

    This test explicitly validates the known intentional difference rather
    than requiring cross-mode equality.
    """
    cfg = iscsi_config['targets']['basic']
    extent_data = call(
        'iscsi.extent.query',
        [['name', '=', cfg['extent']['name']]],
        {'get': True},
    )

    with iscsi_scsi_connection(iscsi_config['ip'], cfg['iqn']) as s:
        TUR(s)
        wire_serial = _serial_number(s).rstrip('\x00')

    if active_mode == ISCSIMODE.LIO:
        expected = _vendor_nibbles_from_naa(extent_data['naa'])
    else:
        expected = extent_data['serial']

    assert wire_serial == expected, (
        f'mode={active_mode}: VPD 0x80 serial mismatch -- '
        f'wire={wire_serial!r}  expected={expected!r}'
    )


def test_read_capacity(iscsi_config, active_mode):
    """Wire-reported capacity must match the configured zvol size."""
    cfg = iscsi_config['targets']['basic']
    with iscsi_scsi_connection(iscsi_config['ip'], cfg['iqn']) as s:
        verify_capacity(s, cfg['size_mb'] * MB)


def test_basic_read_write(iscsi_config, active_mode):
    """Write a known pattern, read it back in-session and after reconnect."""
    cfg = iscsi_config['targets']['basic']
    ip = iscsi_config['ip']
    iqn = cfg['iqn']
    zeros = bytearray(512)
    pattern = bytearray.fromhex('c0ffee00') * 128  # 512 bytes

    with iscsi_scsi_connection(ip, iqn) as s:
        TUR(s)
        s.writesame16(0, 4, zeros)  # clear first 4 LBAs
        s.write16(2, 1, pattern)  # write pattern to LBA 2
        assert s.read16(2, 1).datain == pattern
        assert s.read16(0, 1).datain == zeros

    # Reconnect and verify persistence
    with iscsi_scsi_connection(ip, iqn) as s:
        TUR(s)
        assert s.read16(2, 1).datain == pattern
        assert s.read16(0, 1).datain == zeros


def test_session_count(iscsi_config, active_mode):
    """client_count must be at least 1 while a session is active."""
    cfg = iscsi_config['targets']['basic']
    with iscsi_scsi_connection(iscsi_config['ip'], cfg['iqn']) as s:
        TUR(s)
        count = call('iscsi.global.client_count')
    assert count >= 1, f'mode={active_mode}: expected client_count >= 1, got {count}'


def test_session_list(iscsi_config, active_mode):
    """iscsi.global.sessions must contain an entry for the active session.

    Checks target IQN and that initiator_addr is present.  For LIO in
    generate_node_acls mode the kernel only exposes the initiator IQN via
    tpgt_N/dynamic_sessions (no IP), so initiator_addr is '' -- the assertion
    is relaxed to isinstance check in that case.
    """
    cfg = iscsi_config['targets']['basic']
    with iscsi_scsi_connection(iscsi_config['ip'], cfg['iqn']) as s:
        TUR(s)
        sessions = call('iscsi.global.sessions')

    matching = [sess for sess in sessions if sess['target'] == cfg['iqn']]
    assert matching, (
        f'mode={active_mode}: no session found for {cfg["iqn"]} -- sessions={sessions!r}'
    )
    addr = matching[0]['initiator_addr']
    if active_mode == ISCSIMODE.LIO:
        assert isinstance(addr, str), (
            f'mode={active_mode}: initiator_addr is not a string in session {matching[0]!r}'
        )
    else:
        assert addr, (
            f'mode={active_mode}: initiator_addr is empty in session {matching[0]!r}'
        )


# ---------------------------------------------------------------------------
# t_basic -- concurrent initiators
# ---------------------------------------------------------------------------


def test_concurrent_initiators(iscsi_config, active_mode):
    """Two simultaneous sessions to the same target must both be active and
    share the same underlying storage.

    Each iscsi_scsi_connection context creates an independent libiscsi session
    with its own TCP connection and ISID.  Verifies:

    - client_count is at least 2 while both sessions are open.
    - A write from one session is immediately visible to the other
      (shared block device; no per-session write buffering).
    """
    ip = iscsi_config['ip']
    iqn = iscsi_config['targets']['basic']['iqn']
    pattern_1 = bytearray.fromhex('11111111') * 128
    pattern_2 = bytearray.fromhex('22222222') * 128

    init1 = f'iqn.2005-10.org.freenas.ctl:mc{_rnd}ci1'
    init2 = f'iqn.2005-10.org.freenas.ctl:mc{_rnd}ci2'

    with iscsi_scsi_connection(ip, iqn, initiator_name=init1) as s1:
        with iscsi_scsi_connection(ip, iqn, initiator_name=init2) as s2:
            TUR(s1)
            TUR(s2)

            # client_count counts distinct initiator IPs, not sessions.
            # Both connections originate from the same test machine, so
            # client_count == 1; use the session list to verify two sessions.
            sessions = call('iscsi.global.sessions', [['target', '=', iqn]])
            assert len(sessions) >= 2, (
                f'mode={active_mode}: expected >= 2 sessions to {iqn}, got {sessions!r}'
            )

            s1.write16(8, 1, pattern_1)
            s2.write16(9, 1, pattern_2)

            # Cross-read: each session must see the other's write.
            assert s2.read16(8, 1).datain == pattern_1, (
                f'mode={active_mode}: session 2 cannot read session 1 write at LBA 8'
            )
            assert s1.read16(9, 1).datain == pattern_2, (
                f'mode={active_mode}: session 1 cannot read session 2 write at LBA 9'
            )


# ---------------------------------------------------------------------------
# t_basic -- resize
# ---------------------------------------------------------------------------


def test_resize_zvol_visible(iscsi_config, active_mode):
    """Zvol resize must be reflected in READ CAPACITY on the connected session.

    With AEN enabled (the default) the target sends an async capacity-change
    notification so no CHECK CONDITION appears on the initiator; the new size
    is simply visible on the next READ CAPACITY.  Uses a dedicated
    zvol/extent/target so the shared t_basic size is unaffected.
    """
    ip = iscsi_config['ip']
    zvol_path = f'{pool_name}/mc{_rnd}rz'
    extent_name = f'mcext{_rnd}rz'
    target_name = f'mc{_rnd}resize'
    iqn = f'{basename}:{target_name}'

    with contextlib.ExitStack() as stack:
        stack.enter_context(zvol_dataset(zvol_path, SIZE_BASIC))
        ext = stack.enter_context(zvol_extent(zvol_path, extent_name))
        t = stack.enter_context(
            target(
                target_name,
                [
                    {
                        'portal': iscsi_config['portal_id'],
                        'initiator': iscsi_config['initiator_id'],
                    }
                ],
            )
        )
        stack.enter_context(target_extent_associate(t['id'], ext['id'], 0))

        with iscsi_scsi_connection(ip, iqn) as s:
            TUR(s)
            verify_capacity(s, SIZE_BASIC * MB)

            call('pool.dataset.update', zvol_path, {'volsize': (SIZE_BASIC * 2) * MB})

            verify_capacity(s, (SIZE_BASIC * 2) * MB)


# ---------------------------------------------------------------------------
# t_basic -- product_id customisation
# ---------------------------------------------------------------------------


def test_product_id_create(iscsi_config, active_mode):
    """A custom product_id set at extent creation must appear in Standard INQUIRY.

    test_261 covers the default product_id ("iSCSI Disk").  This test verifies
    that a non-default value supplied at iscsi.extent.create is correctly written
    to the storage object identity (SCST: config template; LIO: wwn/product_id
    at SO creation time, before enable, when export_count == 0).

    Hot-update (iscsi.extent.update on a live SO) is intentionally not tested:
    LIO's wwn/product_id is a configfs attribute gated by export_count -- writes
    are silently ignored once LUNs are mapped, so updating requires a full
    service restart to tear down and recreate the storage object.  That is an
    acceptable constraint for a rarely-changed identity field.
    """
    ip = iscsi_config['ip']
    zvol_path = f'{pool_name}/mc{_rnd}pid'
    extent_name = f'mcext{_rnd}pid'
    target_name = f'mc{_rnd}pid'
    iqn = f'{basename}:{target_name}'
    custom_pid = f'mc{_rnd}pid'[:16]

    def _inquiry_product(s):
        return s.inquiry().result['product_identification'].decode('utf-8').strip()

    with contextlib.ExitStack() as stack:
        stack.enter_context(zvol_dataset(zvol_path, 64))
        ext = call(
            'iscsi.extent.create',
            {
                'type': 'DISK',
                'disk': f'zvol/{zvol_path}',
                'name': extent_name,
                'product_id': custom_pid,
            },
        )
        stack.callback(lambda: call('iscsi.extent.delete', ext['id'], True))
        t = stack.enter_context(
            target(
                target_name,
                [
                    {
                        'portal': iscsi_config['portal_id'],
                        'initiator': iscsi_config['initiator_id'],
                    }
                ],
            )
        )
        stack.enter_context(target_extent_associate(t['id'], ext['id'], 0))

        with iscsi_scsi_connection(ip, iqn) as s:
            TUR(s)
            assert _inquiry_product(s) == custom_pid, (
                f'mode={active_mode}: custom product_id not reflected in INQUIRY'
            )


# ---------------------------------------------------------------------------
# t_snapshot -- snapshot and rollback
# ---------------------------------------------------------------------------


def test_snapshot_rollback(iscsi_config, active_mode):
    """Snapshot rollback must restore the zvol to its pre-snapshot state.

    Pattern:
      1. Write pattern A to LBA 4 and close the session.
      2. Take a snapshot.
      3. Open a new session and overwrite LBA 4 with pattern B.
      4. Roll back to the snapshot.
      5. Open a new session and verify LBA 4 contains pattern A again.

    A new connection is used after rollback so the read goes to the target
    stack fresh, with no possibility of a session-level read cache returning
    stale data.
    """
    ip = iscsi_config['ip']
    iqn = iscsi_config['targets']['basic']['iqn']
    zvol_path = iscsi_config['targets']['basic']['zvol']
    zeros = bytearray(512)
    pattern_a = bytearray.fromhex('aabbccdd') * 128  # state at snapshot time
    pattern_b = bytearray.fromhex('11223344') * 128  # written after snapshot

    # Establish known state: zeros in LBAs 0-7, pattern_a in LBA 4.
    with iscsi_scsi_connection(ip, iqn) as s:
        TUR(s)
        s.writesame16(0, 8, zeros)
        s.write16(4, 1, pattern_a)

    with _snapshot(zvol_path, f'mc{_rnd}snap') as snap_id:
        # Overwrite LBA 4 with pattern_b (post-snapshot write).
        with iscsi_scsi_connection(ip, iqn) as s:
            TUR(s)
            s.write16(4, 1, pattern_b)

        call('pool.snapshot.rollback', snap_id)

        # New connection -- data at LBA 4 must be pattern_a (rollback restored it).
        with iscsi_scsi_connection(ip, iqn) as s:
            TUR(s)
            assert s.read16(4, 1).datain == pattern_a, (
                f'mode={active_mode}: LBA 4 should be pattern_a after rollback'
            )
            assert s.read16(3, 1).datain == zeros, (
                f'mode={active_mode}: LBA 3 should still be zeros after rollback'
            )


# ---------------------------------------------------------------------------
# t_chap -- target authentication
# ---------------------------------------------------------------------------


def test_chap_valid_login(iscsi_config, active_mode):
    """Login with correct CHAP credentials must succeed."""
    cfg = iscsi_config['targets']['chap']
    with iscsi_scsi_connection(
        iscsi_config['ip'],
        cfg['iqn'],
        user=CHAP_USER,
        secret=CHAP_SECRET,
        initiator_name=CHAP_INITIATOR_IQN,
    ) as s:
        TUR(s)


def test_chap_no_credentials(iscsi_config, active_mode):
    """Login without credentials must be rejected by a CHAP-protected target."""
    cfg = iscsi_config['targets']['chap']
    with pytest.raises(RuntimeError) as exc:
        with iscsi_scsi_connection(
            iscsi_config['ip'],
            cfg['iqn'],
            initiator_name=CHAP_INITIATOR_IQN,
        ) as s:
            TUR(s)
    assert 'Unable to connect to' in str(exc), exc


def test_chap_wrong_secret(iscsi_config, active_mode):
    """Login with an incorrect CHAP secret must be rejected."""
    cfg = iscsi_config['targets']['chap']
    with pytest.raises(RuntimeError) as exc:
        with iscsi_scsi_connection(
            iscsi_config['ip'],
            cfg['iqn'],
            user=CHAP_USER,
            secret='wrongsecret123',
            initiator_name=CHAP_INITIATOR_IQN,
        ) as s:
            TUR(s)
    assert 'Unable to connect to' in str(exc), exc


# ---------------------------------------------------------------------------
# t_mutual -- mutual CHAP
# ---------------------------------------------------------------------------


def test_mutual_chap_valid_login(iscsi_config, active_mode):
    """Login with correct credentials on both sides must succeed.

    The initiator proves itself to the target (CHAP_N / CHAP_R) and the
    target proves itself back to the initiator (reverse CHAP).
    """
    cfg = iscsi_config['targets']['mutual']
    with iscsi_scsi_connection(
        iscsi_config['ip'],
        cfg['iqn'],
        user=MUTUAL_USER,
        secret=MUTUAL_SECRET,
        target_user=MUTUAL_PEER_USER,
        target_secret=MUTUAL_PEER_SECRET,
        initiator_name=MUTUAL_INITIATOR_IQN,
    ) as s:
        TUR(s)


def test_mutual_chap_wrong_target_secret(iscsi_config, active_mode):
    """Login must fail when the target's reverse-CHAP response does not match.

    The initiator presents correct credentials, but the expected target secret
    differs from the one the target will use.  The initiator rejects the
    target's reverse-CHAP response and aborts the login.
    """
    cfg = iscsi_config['targets']['mutual']
    with pytest.raises(RuntimeError) as exc:
        with iscsi_scsi_connection(
            iscsi_config['ip'],
            cfg['iqn'],
            user=MUTUAL_USER,
            secret=MUTUAL_SECRET,
            target_user=MUTUAL_PEER_USER,
            target_secret='wrongtarget12',
            initiator_name=MUTUAL_INITIATOR_IQN,
        ) as s:
            TUR(s)
    assert 'Unable to connect to' in str(exc), exc


# ---------------------------------------------------------------------------
# t_multilun -- LUN enumeration and per-LUN properties
# ---------------------------------------------------------------------------


def test_multilun_report_luns(iscsi_config, active_mode):
    """REPORT LUNS must enumerate all configured LUN IDs."""
    cfg = iscsi_config['targets']['multilun']
    with iscsi_scsi_connection(iscsi_config['ip'], cfg['iqn']) as s:
        TUR(s)
        verify_luns(s, list(range(len(cfg['lun_sizes_mb']))))


def test_multilun_per_lun_capacity(iscsi_config, active_mode):
    """READ CAPACITY on each LUN must reflect its individual configured size."""
    cfg = iscsi_config['targets']['multilun']
    ip = iscsi_config['ip']
    iqn = cfg['iqn']
    for lun_id, size_mb in enumerate(cfg['lun_sizes_mb']):
        with iscsi_scsi_connection(ip, iqn, lun=lun_id) as s:
            verify_capacity(s, size_mb * MB)


def test_multilun_xcopy(iscsi_config, active_mode):
    """XCOPY (Extended Copy, opcode 0x83) must copy blocks between two LUNs on the
    same target without the data traversing the initiator.

    Uses LUN 0 as source and LUN 1 as destination on the t_multilun target.
    Writes deadbeef to LBAs 1, 3, 4 on LUN 0; issues XCOPY to copy 4 blocks
    starting at source LBA 1 to destination LBA 10; verifies:
      - Source LUN 0 is unchanged.
      - Destination LUN 1 has the correct blocks at LBAs 10, 12, 13 (zeros
        elsewhere), matching the block-offset copy of LBAs 1-4.
    """
    ip = iscsi_config['ip']
    iqn = iscsi_config['targets']['multilun']['iqn']
    zeros = bytearray(512)
    deadbeef = bytearray.fromhex('deadbeef') * 128

    with iscsi_scsi_connection(ip, iqn, lun=0) as s1:
        with iscsi_scsi_connection(ip, iqn, lun=1) as s2:
            TUR(s1)
            TUR(s2)

            d1 = _get_designator(s1, 3)
            d2 = _get_designator(s2, 3)

            s1.writesame16(0, 20, zeros)
            s2.writesame16(0, 20, zeros)

            # Write source pattern: deadbeef at LBAs 1, 3, 4.
            s1.write16(1, 1, deadbeef)
            s1.write16(3, 1, deadbeef)
            s1.write16(4, 1, deadbeef)

            s1.extendedcopy4(
                priority=1,
                list_identifier=0x34,
                target_descriptor_list=[
                    {
                        'descriptor_type_code': 'Identification descriptor target descriptor',
                        'peripheral_device_type': 0x00,
                        'target_descriptor_parameters': d1,
                        'device_type_specific_parameters': {'disk_block_length': 512},
                    },
                    {
                        'descriptor_type_code': 'Identification descriptor target descriptor',
                        'peripheral_device_type': 0x00,
                        'target_descriptor_parameters': d2,
                        'device_type_specific_parameters': {'disk_block_length': 512},
                    },
                ],
                segment_descriptor_list=[
                    {
                        'descriptor_type_code': 'Copy from block device to block device',
                        'dc': 1,
                        'source_target_descriptor_id': 0,
                        'destination_target_descriptor_id': 1,
                        'block_device_number_of_blocks': 4,
                        'source_block_device_logical_block_address': 1,
                        'destination_block_device_logical_block_address': 10,
                    }
                ],
            )

            # Source LUN 0 must be unchanged.
            for lba in range(0, 20):
                r = s1.read16(lba, 1)
                expected = deadbeef if lba in (1, 3, 4) else zeros
                assert r.datain == expected, (
                    f'mode={active_mode}: LUN 0 LBA {lba}: unexpected data after XCOPY'
                )

            # Destination LUN 1: LBAs 10, 12, 13 copied (1->10, 3->12, 4->13); rest zeros.
            for lba in range(0, 20):
                r = s2.read16(lba, 1)
                expected = deadbeef if lba in (10, 12, 13) else zeros
                assert r.datain == expected, (
                    f'mode={active_mode}: LUN 1 LBA {lba}: unexpected data after XCOPY'
                )


# ---------------------------------------------------------------------------
# t_nolun0 -- no LUN 0
# ---------------------------------------------------------------------------


def test_nolun0_report_luns(iscsi_config, active_mode):
    """REPORT LUNS must enumerate only LUN 1 when LUN 0 is absent.

    Tests that the target stack correctly reports a sparse LUN space:
    only the configured LUN ID appears; LUN 0 is not fabricated.

    We connect to the existing LUN (1) rather than the absent LUN 0 because
    libiscsi sends a TUR to the connected LUN on login; that TUR would fail
    against an absent LUN before we could issue REPORT LUNS.  See the
    equivalent comment in test_261_iscsi_cmd.py::test__no_lun_zero.

    Note: a SCSI-compliant target (including SCST) does respond to REPORT
    LUNS addressed to an absent LUN 0 -- the spec requires it -- but that path
    cannot be exercised via libiscsi for the reason above.
    """
    cfg = iscsi_config['targets']['nolun0']
    with iscsi_scsi_connection(iscsi_config['ip'], cfg['iqn'], lun=cfg['lun_id']) as s:
        verify_luns(s, [cfg['lun_id']])


def test_nolun0_capacity(iscsi_config, active_mode):
    """READ CAPACITY on the non-zero LUN must reflect the configured size."""
    cfg = iscsi_config['targets']['nolun0']
    with iscsi_scsi_connection(iscsi_config['ip'], cfg['iqn'], lun=cfg['lun_id']) as s:
        verify_capacity(s, cfg['size_mb'] * MB)


# ---------------------------------------------------------------------------
# t_acl -- initiator ACL filtering
# ---------------------------------------------------------------------------


def test_acl_permitted_login(iscsi_config, active_mode):
    """An initiator whose IQN is listed in the initiator group must be allowed in."""
    cfg = iscsi_config['targets']['acl']
    with iscsi_scsi_connection(
        iscsi_config['ip'],
        cfg['iqn'],
        initiator_name=ACL_INITIATOR_IQN,
    ) as s:
        TUR(s)


def test_acl_denied_login(iscsi_config, active_mode):
    """An initiator whose IQN is not in the initiator group must be rejected."""
    cfg = iscsi_config['targets']['acl']
    with pytest.raises(RuntimeError) as exc:
        with iscsi_scsi_connection(
            iscsi_config['ip'],
            cfg['iqn'],
            initiator_name=ACL_UNLISTED_IQN,
        ) as s:
            TUR(s)
    assert 'Unable to connect to' in str(exc), exc


# ---------------------------------------------------------------------------
# Service lifecycle -- restart and reconnect
# ---------------------------------------------------------------------------


def test_service_restart_reconnects(iscsi_config, active_mode):
    """iSCSI service restart must preserve target config and data accessibility.

    Stops and starts the service in the current mode.  Both SCST and LIO must
    re-apply the full configuration on startup.  Verifies:

    - A connection to the basic (no-auth) target can be re-established.
    - Data written before the restart is readable afterwards (zvol not affected).
    - A CHAP-protected target still accepts correct credentials (auth config
      survives restart).
    """
    ip = iscsi_config['ip']
    pattern = bytearray.fromhex('cafebabe') * 128

    # Write a known pattern before the restart.
    with iscsi_scsi_connection(ip, iscsi_config['targets']['basic']['iqn']) as s:
        TUR(s)
        s.write16(0, 1, pattern)

    call('service.control', 'STOP', SERVICE_NAME, job=True)
    call('service.control', 'START', SERVICE_NAME, job=True)
    sleep(5)

    # Basic target must be reachable and the pre-restart write must survive.
    with iscsi_scsi_connection(ip, iscsi_config['targets']['basic']['iqn']) as s:
        TUR(s)
        assert s.read16(0, 1).datain == pattern, (
            f'mode={active_mode}: data not preserved through service restart'
        )

    # CHAP-protected target must still accept correct credentials after restart.
    with iscsi_scsi_connection(
        ip,
        iscsi_config['targets']['chap']['iqn'],
        user=CHAP_USER,
        secret=CHAP_SECRET,
        initiator_name=CHAP_INITIATOR_IQN,
    ) as s:
        TUR(s)


# ---------------------------------------------------------------------------
# Discovery -- SendTargets with and without authentication
# ---------------------------------------------------------------------------


def test_discovery_no_auth_sees_nothing(iscsi_config, active_mode):
    """SendTargets without credentials must be rejected when discovery auth is enforced."""
    with ISCSIDiscover(iscsi_config['ip']) as disc:
        result = disc.discover()
    assert result == {}, (
        f'mode={active_mode}: expected empty discovery without credentials, got {result!r}'
    )


def test_discovery_auth_valid(iscsi_config, active_mode):
    """SendTargets with correct discovery credentials must return targets visible to the
    discovery initiator.

    Only targets whose initiator group is open (any IQN permitted) appear in the
    SendTargets response for an arbitrary discovery initiator IQN.  Targets with named
    initiator groups (t_chap, t_mutual, t_acl) are correctly filtered out because the
    discovery initiator's IQN is not listed in those groups.
    """
    with ISCSIDiscover(
        iscsi_config['ip'],
        initiator_username=DISC_USER,
        initiator_password=DISC_SECRET,
    ) as disc:
        result = disc.discover()
    discovered = set(result.keys())
    # Only open-initiator-group targets are discoverable by an arbitrary IQN.
    expected = {IQN_BASIC, IQN_MULTILUN, IQN_NOLUN0}
    assert expected.issubset(discovered), (
        f'mode={active_mode}: expected IQNs not found in discovery -- '
        f'missing={(expected - discovered)!r}  got={discovered!r}'
    )


def test_discovery_auth_invalid(iscsi_config, active_mode):
    """SendTargets with wrong credentials must be rejected."""
    with ISCSIDiscover(
        iscsi_config['ip'],
        initiator_username=DISC_USER,
        initiator_password='wrongsecret12',
    ) as disc:
        result = disc.discover()
    assert result == {}, (
        f'mode={active_mode}: expected rejection with wrong credentials, got {result!r}'
    )
