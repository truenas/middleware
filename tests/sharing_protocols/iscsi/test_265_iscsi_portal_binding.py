"""
test_265_iscsi_portal_binding.py

Validates iSCSI portal binding behaviour across ISCSIMODEs.

This module is deliberately separate from test_264_iscsi_mode_compat.py so
that it can control portal setup independently.  test_264 keeps a wildcard
portal (0.0.0.0:3260) alive for its entire run; since the portal API only
supports port 3260, creating a second portal on the same port alongside the
wildcard would be ambiguous.  This module runs with only a specific-IP portal
and no wildcard, giving a clean test environment.

Two LUNs are configured on the target to broaden coverage:

  LUN 0 -- zvol (DISK extent)
  LUN 1 -- file (FILE extent)

This exercises both backend types through a specific-IP portal in a single
module run.
"""

import contextlib
import ipaddress
import random
import string
from time import sleep

import pytest

from assets.websocket.iscsi import (
    TUR,
    initiator,
    portal,
    target,
    target_extent_associate,
    verify_capacity,
    verify_luns,
    zvol_extent,
)
from assets.websocket.pool import zvol as zvol_dataset
from auto_config import pool_name
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call
from protocols import ISCSIDiscover, iscsi_scsi_connection
from assets.websocket.service import ensure_service_enabled


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

_rnd = ''.join(random.choices(string.digits, k=4))

# pb = portal-binding prefix, keeps names distinct from test_264
T_SPECIFIC = f'pb{_rnd}spec'
IQN_SPECIFIC = f'{basename}:{T_SPECIFIC}'

SIZE_ZVOL = 64  # MB -- LUN 0
SIZE_FILE = 96  # MB -- LUN 1 (distinct size for unambiguous capacity assertions)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _first_nonloopback_ipv4():
    """Return the first non-loopback, non-wildcard IPv4 from portal choices."""
    choices = call('iscsi.portal.listen_ip_choices')
    for ip in choices:
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            continue
        if addr.version == 4 and not addr.is_loopback and not addr.is_unspecified:
            return ip
    raise RuntimeError(
        'No suitable specific IPv4 address available from iscsi.portal.listen_ip_choices'
    )


@contextlib.contextmanager
def file_extent(dataset_path, filename, filesize_mb, extent_name):
    """Create a FILE-type iSCSI extent backed by a file in an existing dataset."""
    config = call(
        'iscsi.extent.create',
        {
            'type': 'FILE',
            'name': extent_name,
            'filesize': filesize_mb * MB,
            'path': f'/mnt/{dataset_path}/{filename}',
        },
    )
    try:
        yield config
    finally:
        call('iscsi.extent.delete', config['id'], True, True)


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
def portal_config(saved_iscsi_mode):
    """Create a specific-IP portal with a two-LUN target (zvol + file)."""
    with contextlib.ExitStack() as stack:
        stack.enter_context(ensure_service_enabled(SERVICE_NAME))

        specific_ip = _first_nonloopback_ipv4()

        p_specific = stack.enter_context(
            portal(listen=[{'ip': specific_ip}], comment=f'pb{_rnd}-specific')
        )
        init_open = stack.enter_context(initiator(comment=f'pb{_rnd}-open'))

        # LUN 0 -- zvol (DISK extent)
        stack.enter_context(zvol_dataset(f'{pool_name}/pb{_rnd}zv', SIZE_ZVOL))
        ext_zvol = stack.enter_context(
            zvol_extent(f'{pool_name}/pb{_rnd}zv', f'pbext{_rnd}zv')
        )

        # LUN 1 -- file (FILE extent)
        ds_path = stack.enter_context(dataset(f'pb{_rnd}ds'))
        ext_file = stack.enter_context(
            file_extent(ds_path, f'pb{_rnd}.img', SIZE_FILE, f'pbext{_rnd}fi')
        )

        t = stack.enter_context(
            target(
                T_SPECIFIC, [{'portal': p_specific['id'], 'initiator': init_open['id']}]
            )
        )
        stack.enter_context(target_extent_associate(t['id'], ext_zvol['id'], 0))
        stack.enter_context(target_extent_associate(t['id'], ext_file['id'], 1))

        try:
            yield {
                'specific_ip': specific_ip,
                'iqn': IQN_SPECIFIC,
                'size_zvol_mb': SIZE_ZVOL,
                'size_file_mb': SIZE_FILE,
            }
        finally:
            call('service.control', 'STOP', SERVICE_NAME, job=True)


@pytest.fixture(
    scope='module',
    params=MODES_UNDER_TEST,
    ids=[MODE_IDS[m] for m in MODES_UNDER_TEST],
)
def active_mode(request, portal_config):
    """Switch ISCSIMODE and restart the service. One restart per mode value."""
    mode = request.param
    call('service.control', 'STOP', SERVICE_NAME, job=True)
    call('iscsi.global.update', {'mode': mode})
    call('service.control', 'START', SERVICE_NAME, job=True)
    sleep(5)
    yield mode


# ---------------------------------------------------------------------------
# t_specific_ip -- specific-IP portal binding
# ---------------------------------------------------------------------------


def test_specific_ip_portal_reachable(portal_config, active_mode):
    """Login via the specific-IP portal must succeed and LUN 0 (zvol) must be accessible.

    Verifies that the iSCSI stack correctly binds to and listens on the
    specific IP address configured in the portal.
    """
    with iscsi_scsi_connection(portal_config['specific_ip'], portal_config['iqn']) as s:
        TUR(s)
        verify_capacity(s, portal_config['size_zvol_mb'] * MB)


def test_specific_ip_file_lun_capacity(portal_config, active_mode):
    """LUN 1 (file extent) must report the correct capacity."""
    with iscsi_scsi_connection(
        portal_config['specific_ip'], portal_config['iqn'], lun=1
    ) as s:
        verify_capacity(s, portal_config['size_file_mb'] * MB)


def test_specific_ip_report_luns(portal_config, active_mode):
    """REPORT LUNS must enumerate both LUN 0 (zvol) and LUN 1 (file)."""
    with iscsi_scsi_connection(portal_config['specific_ip'], portal_config['iqn']) as s:
        verify_luns(s, [0, 1])


def test_specific_ip_discovery_shows_target(portal_config, active_mode):
    """SendTargets discovery via the specific IP must return the bound target."""
    with ISCSIDiscover(portal_config['specific_ip']) as disc:
        result = disc.discover()
    discovered = set(result.keys())

    assert IQN_SPECIFIC in discovered, (
        f'mode={active_mode}: {IQN_SPECIFIC!r} not found in specific-IP discovery '
        f'-- got {discovered!r}'
    )
