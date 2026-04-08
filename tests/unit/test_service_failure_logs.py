"""
Unit tests for service failure log collection.

Tests the end-to-end pipeline: service start failure at the systemd level
produces a CallError whose message contains journalctl output from the
actual failed unit(s), including transitive Wants dependencies.

These tests run directly on a TrueNAS system and exercise real systemd
units via the middleware API.
"""
import subprocess
import time

import pytest
from truenas_api_client import Client, ClientException


@pytest.fixture(autouse=True, scope='module')
def _client():
    """Single client connection for the entire module."""
    with Client() as c:
        yield c


def systemctl(*args):
    subprocess.run(['systemctl', *args], capture_output=True, timeout=30)


def reset_nut_failed_state():
    systemctl('reset-failed', 'nut-monitor', 'nut-server',
              'nut-driver@ups', 'nut-driver-enumerator')


def stop_ups(client):
    try:
        client.call('service.control', 'STOP', 'ups', job=True)
    except Exception:
        pass


@pytest.fixture(autouse=True, scope='module')
def _ensure_default_ups_config(_client):
    """Ensure UPS starts with default config (no driver) and is cleaned up."""
    _client.call(
        'datastore.sql',
        "UPDATE services_ups SET ups_driver='', ups_port='', ups_mode='MASTER'"
    )
    reset_nut_failed_state()
    stop_ups(_client)
    yield
    reset_nut_failed_state()
    stop_ups(_client)


@pytest.fixture(autouse=True)
def _cleanup_nut(_client):
    """Ensure NUT units are cleaned up after each test."""
    yield
    reset_nut_failed_state()
    stop_ups(_client)


@pytest.fixture()
def ups_with_fake_driver(_client):
    """Configure UPS with a nonexistent driver that passes check_configuration
    but crashes at the systemd level (nut-driver@ups fails).

    Writes directly to the datastore to bypass driver_choices validation,
    then restores the original config on teardown.
    """
    old = _client.call('ups.config')
    _client.call(
        'datastore.sql',
        "UPDATE services_ups SET "
        "ups_driver='fake-nonexistent-driver', "
        "ups_port='/dev/null', "
        "ups_mode='MASTER'"
    )
    yield
    _client.call(
        'datastore.sql',
        f"UPDATE services_ups SET "
        f"ups_driver='{old.get('driver', '')}', "
        f"ups_port='{old.get('port', '')}', "
        f"ups_mode='{old.get('mode', 'MASTER')}'"
    )


class TestServiceFailureLogs:
    """Test that service start failures produce journalctl output."""

    def test_systemd_failure_produces_journal_output(self, _client, ups_with_fake_driver):
        """When check_configuration passes but the service crashes at the
        systemd level, the error should contain actual journalctl output
        from the failed sub-unit (nut-driver@ups).

        This tests that failure_logs() walks the Wants dependency tree
        and collects logs from failed transitive dependencies.
        """
        with pytest.raises(ClientException) as exc_info:
            _client.call('service.control', 'START', 'ups', {'silent': False}, job=True)

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

    def test_systemd_failure_timestamps_change(self, _client, ups_with_fake_driver):
        """Each start attempt should produce fresh journal output with
        different timestamps, proving the logs are re-queried each time."""
        # First attempt
        with pytest.raises(ClientException) as exc1:
            _client.call('service.control', 'START', 'ups', {'silent': False}, job=True)

        # Fully stop all NUT units and clear failed state before retrying.
        # reset-failed alone doesn't stop a crash-looping unit.
        stop_ups(_client)
        systemctl('stop', 'nut-driver@ups', 'nut-server',
                  'nut-driver-enumerator', 'nut-monitor')
        reset_nut_failed_state()
        time.sleep(2)

        # Second attempt
        with pytest.raises(ClientException) as exc2:
            _client.call('service.control', 'START', 'ups', {'silent': False}, job=True)

        # Extract first journal timestamp from each error
        # Journal lines: "Apr 08 10:29:13 syslog_id[pid]: message"
        # The error string starts with "[EFAULT] " prefix — strip it
        def first_timestamp(error_str):
            first_line = error_str.splitlines()[0]
            # Remove "[EFAULT] " or similar prefix
            if first_line.startswith('['):
                first_line = first_line.split('] ', 1)[-1]
            return ' '.join(first_line.split()[:3])

        ts1 = first_timestamp(exc1.value.error)
        ts2 = first_timestamp(exc2.value.error)
        assert ts1 != ts2, (
            f'Timestamps should differ between attempts: {ts1!r} == {ts2!r}'
        )

    def test_systemd_failure_silent_returns_false(self, _client, ups_with_fake_driver):
        """When a service crashes at the systemd level with silent=True,
        it should return False (not True, not raise)."""
        result = _client.call('service.control', 'START', 'ups', {'silent': True}, job=True)
        assert result is False, (
            f'Expected False for failed silent start, got: {result!r}'
        )
