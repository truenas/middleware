"""
Unit tests for is_external_call() function and method stats tracking logic.

These tests verify that the is_external_call() function correctly identifies
which API calls should be tracked in usage statistics.
"""
from unittest.mock import Mock
from socket import AF_INET, AF_UNIX

from middlewared.utils.origin import is_external_call, ConnectionOrigin
from middlewared.utils.auth import AUID_UNSET


def test_is_external_call_none_app():
    """
    When app is None, the call is internal and should not be tracked.
    """
    assert is_external_call(None) is False


def test_is_external_call_none_origin():
    """
    When app.origin is None, the call is internal (middleware.call) and should not be tracked.
    """
    app = Mock()
    app.origin = None
    assert is_external_call(app) is False


def test_is_external_call_ha_connection():
    """
    HA heartbeat connections should not be tracked as external calls.

    These are internal communications between HA nodes.
    """
    app = Mock()
    app.origin = Mock(spec=ConnectionOrigin)
    app.origin.is_ha_connection = True
    app.origin.session_is_interactive = True

    assert is_external_call(app) is False


def test_is_external_call_tcp_connection():
    """
    TCP/IP connections (non-HA) are considered external and should be tracked.

    These include WebSocket connections from browsers or API clients.
    """
    app = Mock()
    app.origin = Mock(spec=ConnectionOrigin)
    app.origin.is_ha_connection = False
    app.origin.session_is_interactive = True

    assert is_external_call(app) is True


def test_is_external_call_unix_socket_interactive():
    """
    Unix socket connections with interactive session (loginuid set) should be tracked.

    This represents midclt calls from an SSH session where a user has logged in.
    """
    app = Mock()
    app.origin = Mock(spec=ConnectionOrigin)
    app.origin.is_ha_connection = False
    app.origin.session_is_interactive = True

    assert is_external_call(app) is True


def test_is_external_call_unix_socket_non_interactive():
    """
    Unix socket connections without interactive session should not be tracked.

    This represents internal scripts or system services calling via midclt.
    """
    app = Mock()
    app.origin = Mock(spec=ConnectionOrigin)
    app.origin.is_ha_connection = False
    app.origin.session_is_interactive = False

    assert is_external_call(app) is False


def test_connection_origin_session_is_interactive_tcp():
    """
    TCP/IP connections should always be considered interactive.

    For TCP/IP connections, loginuid is None, so session_is_interactive returns True.
    """
    origin = ConnectionOrigin(
        family=AF_INET,
        loc_addr='127.0.0.1',
        loc_port=6000,
        rem_addr='192.168.1.100',
        rem_port=54321,
        loginuid=None,
    )

    assert origin.session_is_interactive is True


def test_connection_origin_session_is_interactive_unix_with_loginuid():
    """
    Unix socket connections with loginuid set (not AUID_UNSET) are interactive.

    This represents a user who has logged in via SSH and is using midclt.
    """
    origin = ConnectionOrigin(
        family=AF_UNIX,
        pid=12345,
        uid=1000,
        gid=1000,
        loginuid=1000,  # loginuid is set, indicating interactive session
    )

    assert origin.session_is_interactive is True


def test_connection_origin_session_is_interactive_unix_without_loginuid():
    """
    Unix socket connections with loginuid = AUID_UNSET are not interactive.

    This represents system services or scripts calling middleware internally.
    """
    origin = ConnectionOrigin(
        family=AF_UNIX,
        pid=12345,
        uid=0,
        gid=0,
        loginuid=AUID_UNSET,  # No login session
    )

    assert origin.session_is_interactive is False


def test_connection_origin_is_ha_connection_heartbeat_ip():
    """
    Connections from HA heartbeat IPs with privileged ports are HA connections.
    """
    # Test both heartbeat IPs
    for heartbeat_ip in ('169.254.10.1', '169.254.10.2'):
        origin = ConnectionOrigin(
            family=AF_INET,
            loc_addr='169.254.10.1',
            loc_port=6000,
            rem_addr=heartbeat_ip,
            rem_port=1024,  # Privileged port
        )

        assert origin.is_ha_connection is True, (
            f"Expected {heartbeat_ip} with port 1024 to be HA connection"
        )


def test_connection_origin_is_ha_connection_non_privileged_port():
    """
    Connections from HA heartbeat IPs with non-privileged ports are not HA connections.

    This prevents spoofing from user processes.
    """
    origin = ConnectionOrigin(
        family=AF_INET,
        loc_addr='169.254.10.1',
        loc_port=6000,
        rem_addr='169.254.10.1',
        rem_port=1025,  # Non-privileged port
    )

    assert origin.is_ha_connection is False


def test_connection_origin_is_ha_connection_non_heartbeat_ip():
    """
    Connections from non-heartbeat IPs are not HA connections.
    """
    origin = ConnectionOrigin(
        family=AF_INET,
        loc_addr='127.0.0.1',
        loc_port=6000,
        rem_addr='192.168.1.100',
        rem_port=1024,
    )

    assert origin.is_ha_connection is False


def test_connection_origin_is_ha_connection_unix_socket():
    """
    Unix socket connections cannot be HA connections.
    """
    origin = ConnectionOrigin(
        family=AF_UNIX,
        pid=12345,
        uid=0,
        gid=0,
        loginuid=AUID_UNSET,
    )

    assert origin.is_ha_connection is False


def test_integration_external_call_decision_tree():
    """
    Integration test verifying the complete decision tree for is_external_call().

    This tests all the major paths through the function.
    """
    # Path 1: app is None -> False
    assert is_external_call(None) is False

    # Path 2: app.origin is None -> False
    app = Mock()
    app.origin = None
    assert is_external_call(app) is False

    # Path 3: HA connection -> False (even if interactive)
    app.origin = Mock(spec=ConnectionOrigin)
    app.origin.is_ha_connection = True
    app.origin.session_is_interactive = True
    assert is_external_call(app) is False

    # Path 4: Not HA, interactive session -> True
    app.origin.is_ha_connection = False
    app.origin.session_is_interactive = True
    assert is_external_call(app) is True

    # Path 5: Not HA, non-interactive session -> False
    app.origin.is_ha_connection = False
    app.origin.session_is_interactive = False
    assert is_external_call(app) is False
