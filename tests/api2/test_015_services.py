import time
import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)

import pytest

from truenas_api_client import ClientException
from middlewared.test.integration.utils import call, ssh
from middlewared.test.integration.utils.mock import mock


UPS_NUT_UNITS = 'nut-driver@ups nut-server nut-driver-enumerator nut-monitor'


def cleanup_ups():
    """Stop NUT units, reset failed state, and restore default UPS config."""
    ssh(f'systemctl stop {UPS_NUT_UNITS} || true')
    ssh(f'systemctl reset-failed {UPS_NUT_UNITS} || true')
    call('service.control', 'STOP', 'ups', job=True)


def set_fake_ups_driver():
    """Configure UPS with a nonexistent driver that passes check_configuration
    but crashes at the systemd level (nut-driver@ups fails).

    Uses mock to bypass driver_choices validation.
    """
    with mock('ups.driver_choices', return_value={
        'fake-nonexistent-driver': 'Fake driver for testing'
    }):
        call('ups.update', {
            'mode': 'MASTER',
            'driver': 'fake-nonexistent-driver',
            'port': '/dev/null',
            'monpwd': 'testpass',
        })


def restore_default_ups_config():
    """Restore default UPS config via datastore.sql to bypass validation."""
    call(
        'datastore.sql',
        "UPDATE services_ups SET "
        "ups_driver='', ups_port='', ups_mode='MASTER', ups_monpwd='secretpwd'"
    )


def test_001_oom_check():
    pid = call('core.get_pid')
    assert call('core.get_oom_score_adj', pid) == -1000


def test_non_silent_service_start_failure():
    """
    Test that starting a service with invalid configuration raises a
    non-empty CallError when silent=False. UPS with no driver configured
    in MASTER mode should fail in check_configuration before starting.
    """
    restore_default_ups_config()
    cleanup_ups()

    with pytest.raises(ClientException) as e:
        call('service.control', 'START', 'ups', {'silent': False}, job=True)

    assert e.value.error, 'Error message should not be empty'
    assert 'cannot start' in e.value.error.lower()


def test_systemd_failure_produces_journal_output():
    """
    When check_configuration passes but the service crashes at the
    systemd level, the error should contain actual journalctl output
    from the failed sub-unit (nut-driver@ups).

    This tests that failure_logs() walks the Wants dependency tree
    and collects logs from failed transitive dependencies.

    Configure UPS with a non-empty but nonexistent driver so
    check_configuration() passes but nut-driver@ups crashes.
    """
    try:
        set_fake_ups_driver()

        with pytest.raises(ClientException) as exc_info:
            call('service.control', 'START', 'ups', {'silent': False}, job=True)

        error = exc_info.value.error
        assert error, 'Error message should not be empty'

        # Should NOT be the check_configuration static message
        assert 'cannot start' not in error.lower(), (
            f'Got check_configuration error instead of journal output: {error!r}'
        )

        # Should contain journalctl content from nut-driver@ups
        lines = error.splitlines()
        assert any('nut-' in line for line in lines), (
            f'Expected NUT-related journal entries in error, got: {error!r}'
        )
        assert any('systemd[' in line for line in lines), (
            f'Expected systemd journal entries in error, got: {error!r}'
        )
    finally:
        cleanup_ups()
        restore_default_ups_config()


def test_systemd_failure_timestamps_change():
    """
    Each start attempt should produce fresh journal output with
    different timestamps, proving the logs are re-queried each time.

    Uses the same fake-driver approach as test_systemd_failure_produces_journal_output.
    """
    try:
        set_fake_ups_driver()

        # First attempt
        with pytest.raises(ClientException) as exc1:
            call('service.control', 'START', 'ups', {'silent': False}, job=True)

        # Fully stop all NUT units and clear failed state before retrying.
        # reset-failed alone doesn't stop a crash-looping unit.
        cleanup_ups()
        time.sleep(2)

        # Second attempt
        with pytest.raises(ClientException) as exc2:
            call('service.control', 'START', 'ups', {'silent': False}, job=True)

        # Extract first journal timestamp from each error
        # Journal lines: "Apr 08 10:29:13 syslog_id[pid]: message"
        # The error string starts with "[EFAULT] " prefix — strip it
        def first_timestamp(error_str):
            first_line = error_str.splitlines()[0]
            if first_line.startswith('['):
                first_line = first_line.split('] ', 1)[-1]
            return ' '.join(first_line.split()[:3])

        ts1 = first_timestamp(exc1.value.error)
        ts2 = first_timestamp(exc2.value.error)
        assert ts1 != ts2, (
            f'Timestamps should differ between attempts: {ts1!r} == {ts2!r}'
        )
    finally:
        cleanup_ups()
        restore_default_ups_config()


def test_systemd_failure_silent_returns_false():
    """
    When a service crashes at the systemd level with silent=True,
    it should return False (not True, not raise).
    """
    try:
        set_fake_ups_driver()

        result = call('service.control', 'START', 'ups', {'silent': True}, job=True)
        assert result is False, (
            f'Expected False for failed silent start, got: {result!r}'
        )
    finally:
        cleanup_ups()
        restore_default_ups_config()
