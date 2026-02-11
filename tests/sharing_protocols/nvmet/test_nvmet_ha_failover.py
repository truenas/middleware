"""
NVMe-oF HA Basic Failover Testing

Tests basic failover scenarios across multiple dimensions:
- Target implementation: kernel vs SPDK
- Failover mode: ANA vs IP takeover
- I/O state: active vs idle
- Namespace count: 1 vs 3

Quick subset (4 tests - runs by default):
- All implementations and modes
- namespace_count=1, io_active=True

Full matrix (16 tests - requires extended_tests=True in auto_config):
- All parameter combinations (2 x 2 x 2 x 2 = 16 tests)
"""

import contextlib
import time
from typing import Any, Iterator

import pytest

from nvmeof_client import NVMeoFClient
from assets.websocket.pool import zvol
from auto_config import ha, pool_name, extended_tests
from middlewared.test.integration.assets.nvmet import (
    NVME_DEFAULT_TCP_PORT,
    nvmet_namespace,
    nvmet_port,
    nvmet_port_subsys,
    nvmet_subsys,
)
from middlewared.test.integration.utils import call
from middlewared.test.integration.utils.client import truenas_server

# Import shared utilities
from nvmet_ha_utils import (
    ZVOL_MB,
    NVME_KEEPALIVE_MS,
    QUICK_RETRY_ATTEMPTS,
    IP_MOVE_SETTLE_TIME,
    RESOURCE_CLEANUP_SLEEP,
    WORKER_THREAD_JOIN_TIMEOUT,
    RECONNECT_WORKER_JOIN_TIMEOUT,
    ANA_CHANGE_TIMEOUT,
    HA_SETTLE_SLEEP,
    basenqn,
    is_ana_state_optimized,
    connect_with_retry,
    get_node_ips,
    safe_disconnect,
    print_test_config,
    double_settle_ha,
    trigger_failover_with_checks,
    ANAChangeMonitor,
    MultipathClient,
    IOWorker,
    ReconnectingIOWorker,
)

pytestmark = pytest.mark.skipif(not ha, reason='Failover tests require HA')

# ============================================================================
# Constants
# ============================================================================

ZVOL_COUNT = 3
SUBSYS_NAME = 'ha_failover_test'

# ============================================================================
# Helper Functions
# ============================================================================


def settle_and_verify_failover(
    orig_master_node: str, sleep_seconds: int = HA_SETTLE_SLEEP
) -> str:
    """Settle HA and verify failover occurred.

    Uses double settle pattern for stability, then verifies the active node changed.

    Args:
        orig_master_node: Original master node name ('A' or 'B')
        sleep_seconds: Seconds to sleep between settle calls

    Returns:
        New master node name after failover

    Raises:
        AssertionError: If failover did not occur (node unchanged)
    """
    double_settle_ha(sleep_seconds)
    new_master_node = call('failover.node')
    assert new_master_node != orig_master_node, (
        f'Failover failed: master node unchanged ({orig_master_node})'
    )
    return new_master_node


# ============================================================================
# Parameter Selection
# ============================================================================
# Quick subset minimizes test time while covering all implementation/mode combos
# Extended tests add namespace count and I/O state variations for thorough coverage

# Quick subset runs by default, extended tests require extended_tests=True
io_states = [True, False] if extended_tests else [True]
namespace_counts = [1, 3] if extended_tests else [1]


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(scope='module')
def many_zvols() -> Iterator[dict[int, dict[str, str]]]:
    """Create multiple ZVOLs for namespace testing."""
    config = {}
    with contextlib.ExitStack() as es:
        for i in range(ZVOL_COUNT):
            zvol_name = f'nvmetvol_ha_{i:03d}'
            config[i] = {'zvol': f'{pool_name}/{zvol_name}'}
            es.enter_context(zvol(zvol_name, ZVOL_MB, pool_name))
        yield config


@pytest.fixture(params=namespace_counts, scope='module')
def configured_subsystem(
    request: Any, many_zvols: dict[int, dict[str, str]], fixture_failover_mode: str
) -> Iterator[dict[str, Any]]:
    """Set up subsystem with specified number of namespaces for testing."""
    # Create port, subsystem, and namespaces
    # Same setup for both ANA and IP takeover modes
    with nvmet_port(truenas_server.ip) as port:
        with nvmet_subsys(SUBSYS_NAME, allow_any_host=True) as subsys:
            with nvmet_port_subsys(subsys['id'], port['id']):
                # Add requested number of namespaces
                with contextlib.ExitStack() as es:
                    namespace_contexts = []
                    for i in range(request.param):
                        zvol_path = f'zvol/{many_zvols[i]["zvol"]}'
                        ns = es.enter_context(nvmet_namespace(subsys['id'], zvol_path))
                        namespace_contexts.append(ns)

                    # Give NVMe-oF services time to initialize new subsystem/namespaces
                    print('[FIXTURE] Sleeping 5s for subsystem initialization...')
                    time.sleep(5)

                    yield {
                        'subsys': subsys,
                        'port': port,
                        'namespaces': namespace_contexts,
                        'nqn': f'{basenqn()}:{SUBSYS_NAME}',
                        'namespace_count': request.param,
                        'mode': fixture_failover_mode,
                    }

                    # Give connections time to close before fixture teardown
                    print('[FIXTURE] Sleeping 3s before teardown...')
                    time.sleep(3)

    # After all context managers have exited (teardown complete)
    print('[FIXTURE] Sleeping 5s after teardown for services to settle...')
    time.sleep(5)


# ============================================================================
# Test Functions
# ============================================================================


@pytest.mark.parametrize('io_active', io_states)
def test_failover(
    fixture_nvmet_running: str,
    fixture_failover_mode: str,
    configured_subsystem: dict[str, Any],
    io_active: bool,
) -> None:
    """
    Test failover behavior across all configurations.

    This is a dispatcher function that routes to mode-specific implementations:
    - ANA mode -> _test_ana_failover() - uses dual paths with ANA monitoring
    - IP takeover mode -> _test_ip_takeover_failover() - uses single VIP

    Test matrix:
    - 2 target implementations (kernel, spdk)
    - 2 failover modes (ana, ip_takeover)
    - 2 namespace counts (1, 3)
    - 2 I/O states (active, idle)

    Total: 16 test combinations

    Quick subset (4 tests - runs by default):
    - All implementations and modes
    - namespace_count=1, io_active=True

    Full matrix (16 tests - requires extended_tests=True):
    - All parameter combinations
    """
    subsys_nqn = configured_subsystem['nqn']
    namespace_count = configured_subsystem['namespace_count']

    print_test_config(
        'Test Configuration',
        Implementation=fixture_nvmet_running,
        Mode=fixture_failover_mode,
        Namespaces=namespace_count,
        IO_Active=io_active,
    )

    if fixture_failover_mode == 'ana':
        _test_ana_failover(subsys_nqn, namespace_count, io_active)
    else:
        _test_ip_takeover_failover(subsys_nqn, namespace_count, io_active)


def _test_ana_failover(subsys_nqn: str, namespace_count: int, io_active: bool) -> None:
    """Test ANA-based failover with multiple controller paths.

    Uses separate client connections for monitoring and I/O to avoid race conditions:
    - monitor_client: dedicated connection for ANAChangeMonitor
    - multipath: separate connections for IOWorker

    This ensures thread-safe operation during failover with concurrent I/O.
    """
    # ========================================================================
    # SETUP: Initialize clients and monitoring
    # ========================================================================
    # - Get node IPs (active and standby)
    # - Create multipath for I/O (used by IOWorker if active, manual I/O if idle)
    # - Verify initial OPTIMIZED state
    # - Create monitor_client for ANA change detection
    # - Start ANA change monitor
    # - Optionally start I/O worker

    orig_master_node, orig_active_ip, orig_standby_ip = get_node_ips()

    print(
        f'Active node: {orig_master_node}, Active IP: {orig_active_ip}, Standby IP: {orig_standby_ip}'
    )

    monitor_client = None
    multipath = None
    ana_monitor = None
    try:
        # Connect to both controllers for I/O (independent connections)
        multipath = MultipathClient(
            [
                (orig_active_ip, NVME_DEFAULT_TCP_PORT),
                (orig_standby_ip, NVME_DEFAULT_TCP_PORT),
            ],
            subsys_nqn,
        )
        # Verify initial state - active node should be OPTIMIZED
        active_client, active_ip = multipath.get_active_client()
        assert active_ip == orig_active_ip, (
            f'Expected orig_active {orig_active_ip} to be OPTIMIZED, got {active_ip}'
        )
        print(f'[OK] Initial state: {active_ip} is OPTIMIZED')

        # Create separate client for ANA monitoring (independent connection)
        # This ensures no race conditions between monitoring and I/O threads
        monitor_client = NVMeoFClient(
            orig_standby_ip, subsys_nqn, NVME_DEFAULT_TCP_PORT, kato=NVME_KEEPALIVE_MS
        )
        connect_with_retry(monitor_client, orig_standby_ip)
        print(f'[OK] Connected to {orig_standby_ip} for ANA monitoring')

        # Set up ANA change monitoring on standby (will become active)
        # Uses independent monitor_client, not multipath's client
        ana_monitor = ANAChangeMonitor(monitor_client)
        ana_monitor.start()
        print(f'[OK] Monitoring ANA changes on {orig_standby_ip}')

        # Start I/O if requested
        io_worker = None
        if io_active:
            io_worker = IOWorker(multipath, namespace_count)
            io_worker.start()
            print(f'[OK] Started background I/O on {namespace_count} namespace(s)')

        # ====================================================================
        # FAILOVER: Trigger failover event
        # ====================================================================

        failover_start_time = trigger_failover_with_checks('NVMe-oF failover test')

        # ====================================================================
        # DETECT & HANDLE ANA CHANGE: Wait for failover to complete
        # ====================================================================
        # - Wait for ANA change event (Path 1: notification OR Path 2: closure)
        # - If Path 2: reconnect to standby controller
        # - Verify standby controller is now OPTIMIZED

        # Wait for ANA change (either notification or connection closure)
        print('Waiting for ANA change (notification or connection closure)...')
        path_taken, event_time = ana_monitor.wait_for_change(timeout=ANA_CHANGE_TIMEOUT)

        if path_taken is None:
            raise AssertionError(
                'ANA change not detected: no notification and no connection closure within 45 seconds'
            )

        time_to_event = event_time - failover_start_time

        if path_taken == 'notification':
            # Path 1: Notification received
            print(
                f'[OK] ANA change detected via notification (Path 1) '
                f'(took {time_to_event:.2f}s from failover trigger)'
            )
        elif path_taken == 'closure':
            # Path 2: Connection closed
            print(
                f'[OK] Connection closure detected (Path 2) '
                f'(took {time_to_event:.2f}s from failover trigger)'
            )
            print('Waiting for target reconfiguration to complete...')
            time.sleep(2)  # Give target time to complete namespace addition

            # Reconnect monitoring client to standby controller (now becoming active)
            print(f'Reconnecting to standby controller ({orig_standby_ip})...')
            monitor_client.disconnect()
            # Enable keep-alive for connection health monitoring
            monitor_client = NVMeoFClient(
                orig_standby_ip,
                subsys_nqn,
                NVME_DEFAULT_TCP_PORT,
                kato=NVME_KEEPALIVE_MS,
            )

            # Retry connection with extended timeout for Path 2
            connect_with_retry(monitor_client, orig_standby_ip)
            print(f'[OK] Reconnected to {orig_standby_ip}')

        # Use the event time for subsequent timing calculations
        ana_change_time = event_time

        # Verify standby is now OPTIMIZED
        if not is_ana_state_optimized(monitor_client):
            raise AssertionError(
                f'Standby {orig_standby_ip} not OPTIMIZED after ANA change'
            )
        print(f'[OK] Failover complete: {orig_standby_ip} is now OPTIMIZED')

        # ====================================================================
        # VERIFY I/O: Ensure I/O operations work on new controller
        # ====================================================================
        # - If io_active: stop I/O worker and check statistics
        # - If idle: perform manual I/O test (with reconnection if needed)

        # Stop I/O worker to collect statistics
        if io_active and io_worker:
            print('[DEBUG] Setting I/O worker stop_event...')
            io_worker.stop_event.set()
            if io_worker.thread:
                print(
                    f'[DEBUG] Waiting for I/O worker thread to exit (is_alive={io_worker.thread.is_alive()})...'
                )
                io_worker.thread.join(timeout=WORKER_THREAD_JOIN_TIMEOUT)
                print(
                    f'[DEBUG] I/O worker thread join complete (is_alive={io_worker.thread.is_alive()})'
                )
            stats = io_worker.stop()
            io_verified_time = time.time()
            time_to_io = io_verified_time - ana_change_time
            print(
                f'[OK] I/O statistics: {stats["successes"]} successes, {stats["errors"]} errors'
            )
            print(f'[OK] I/O verified (took {time_to_io:.2f}s from ANA change)')
            # Errors are expected during transition
            assert stats['successes'] > 0, 'No successful I/O operations'
        else:
            # Verify we can do I/O after failover
            try:
                data = multipath.read_data(nsid=1, lba=0, block_count=1)
            except Exception as e:
                # If I/O fails, reconnect to new primary (orig_standby_ip is now optimized)
                print(
                    f'[DEBUG] I/O failed ({e}), reconnecting to new primary {orig_standby_ip}...'
                )

                # Reconnect client pointing to the new primary
                if orig_standby_ip in multipath.clients:
                    client = multipath.clients[orig_standby_ip]
                    safe_disconnect(client)
                    # Short retry since new primary should be ready (monitor_client already verified it)
                    connect_with_retry(
                        client, orig_standby_ip, max_attempts=QUICK_RETRY_ATTEMPTS
                    )
                    print(f'[OK] Reconnected to new primary {orig_standby_ip}')

                # Retry I/O (should now use the reconnected client)
                data = multipath.read_data(nsid=1, lba=0, block_count=1)

            assert len(data) == 512
            io_verified_time = time.time()
            time_to_io = io_verified_time - ana_change_time
            print(f'[OK] I/O verified (took {time_to_io:.2f}s from ANA change)')

        # ====================================================================
        # TIMING SUMMARY: Report performance metrics
        # ====================================================================

        total_time = io_verified_time - failover_start_time
        print(f'\n[TIMING] Failover trigger -> ANA change: {time_to_event:.2f}s')
        print(f'[TIMING] ANA change -> I/O verified: {time_to_io:.2f}s')
        print(f'[TIMING] Total time: {total_time:.2f}s')

    finally:
        # ====================================================================
        # CLEANUP: Release resources and disconnect clients
        # ====================================================================
        # - Stop ANA monitor thread
        # - Disconnect monitor_client
        # - Disconnect multipath clients
        # - Sleep for ZVOL resource cleanup

        if ana_monitor:
            ana_monitor.stop()
            print('[DEBUG] ANA monitor stopped')
        # Disconnect monitoring client
        if monitor_client:
            print(
                f'[DEBUG] monitor_client.is_connected = {monitor_client.is_connected}'
            )
            if monitor_client.is_connected:
                print('[DEBUG] Calling monitor_client.disconnect()...')
                monitor_client.disconnect()
                print(
                    f'[DEBUG] monitor_client.disconnect() returned, is_connected = {monitor_client.is_connected}'
                )
            else:
                print('[DEBUG] monitor_client already disconnected')
        # Disconnect I/O clients
        if multipath:
            print('[DEBUG] Disconnecting multipath clients...')
            for ip, client in multipath.clients.items():
                print(f'[DEBUG]   {ip}: is_connected = {client.is_connected}')
            multipath.disconnect_all()
            print('[DEBUG] multipath.disconnect_all() completed')
        # Give system time to fully release ZVOL resources
        # After failover, the new master needs time to release the namespace
        print('[DEBUG] Sleeping for resource cleanup...')
        time.sleep(RESOURCE_CLEANUP_SLEEP)
        print('[DEBUG] Cleanup complete')

    # ========================================================================
    # SETTLE: Wait for HA to reach stable state
    # ========================================================================

    settle_and_verify_failover(orig_master_node)


def _test_ip_takeover_failover(
    subsys_nqn: str, namespace_count: int, io_active: bool
) -> None:
    """Test IP takeover failover with single Virtual IP (VIP)."""
    # ========================================================================
    # SETUP: Initialize connection to VIP
    # ========================================================================
    # - Get original master node and VIP
    # - If io_active: start ReconnectingIOWorker (handles auto-reconnect)
    # - If idle: connect manually to VIP

    orig_master_node = call('failover.node')
    vip = truenas_server.ip

    print(f'VIP: {vip}')

    io_worker = None
    if io_active:
        # Use reconnecting I/O worker for IP takeover
        io_worker = ReconnectingIOWorker(vip, subsys_nqn, namespace_count)
        io_worker.start()
        print(f'[OK] Started reconnecting I/O worker on {namespace_count} namespace(s)')
    else:
        # Connect manually if no I/O active
        client = NVMeoFClient(vip, subsys_nqn)
        connect_with_retry(client, vip)
        print(f'[OK] Connected to {vip}')

    try:
        # ====================================================================
        # FAILOVER: Trigger failover event (VIP will move to other node)
        # ====================================================================

        failover_start_time = trigger_failover_with_checks('NVMe-oF IP takeover test')

        # ====================================================================
        # WAIT & VERIFY: VIP moves, reconnect, and verify I/O
        # ====================================================================
        # - If io_active: ReconnectingIOWorker auto-reconnects, check stats
        # - If idle: manual disconnect, wait, reconnect, verify I/O

        if io_active:
            # I/O worker handles reconnection automatically
            # Just wait a bit for failover to stabilize
            time.sleep(RESOURCE_CLEANUP_SLEEP)

            # Verify I/O worker is still running and has recovered
            stats = io_worker.stop()
            io_verified_time = time.time()

            print(
                f'[OK] I/O statistics: {stats["successes"]} successes, {stats["errors"]} errors, '
                f'{stats["reconnects"]} reconnects'
            )
            assert stats['reconnects'] >= 1, (
                'Expected at least one reconnection during failover'
            )
            assert stats['successes'] > 0, 'No successful I/O operations after failover'

            # ================================================================
            # TIMING SUMMARY: Report performance metrics (io_active branch)
            # ================================================================

            total_time = io_verified_time - failover_start_time
            print(f'\n[TIMING] Total time (trigger to I/O verified): {total_time:.2f}s')
        else:
            # Manual reconnection test
            print('Waiting for IP to move...')
            if client.is_connected:
                client.disconnect()

            # Wait for system to settle and IP to be available
            time.sleep(IP_MOVE_SETTLE_TIME)

            # Reconnect to same IP (now on new controller)
            client = NVMeoFClient(vip, subsys_nqn)
            connect_with_retry(client, vip)
            reconnect_time = time.time()
            time_to_reconnect = reconnect_time - failover_start_time
            print(
                f'[OK] Reconnected to {vip} on new controller '
                f'(took {time_to_reconnect:.2f}s from failover trigger)'
            )

            # Verify I/O works
            test_data = b'testdata'.ljust(512, b'\x00')
            client.write_data(nsid=1, lba=0, data=test_data)
            read_data = client.read_data(nsid=1, lba=0, block_count=1)
            assert read_data[:8] == b'testdata'
            io_verified_time = time.time()
            time_to_io = io_verified_time - reconnect_time
            print(f'[OK] I/O verified (took {time_to_io:.2f}s from reconnection)')

            # ================================================================
            # TIMING SUMMARY: Report performance metrics (idle branch)
            # ================================================================

            total_time = io_verified_time - failover_start_time
            print(
                f'\n[TIMING] Failover trigger -> reconnection: {time_to_reconnect:.2f}s'
            )
            print(f'[TIMING] Reconnection -> I/O verified: {time_to_io:.2f}s')
            print(f'[TIMING] Total time: {total_time:.2f}s')

            # Cleanup manual client
            if client.is_connected:
                client.disconnect()

        # ====================================================================
        # SETTLE: Wait for HA to reach stable state
        # ====================================================================

        settle_and_verify_failover(orig_master_node)

    finally:
        # ====================================================================
        # CLEANUP: Release resources and disconnect clients
        # ====================================================================
        # - Stop I/O worker if running
        # - Disconnect worker client or manual client
        # - Sleep for resource cleanup

        if io_active and io_worker:
            io_worker.stop_event.set()
            if io_worker.thread:
                io_worker.thread.join(timeout=RECONNECT_WORKER_JOIN_TIMEOUT)
            if io_worker.client and io_worker.client.is_connected:
                safe_disconnect(io_worker.client)
        elif not io_active and 'client' in locals() and client.is_connected:
            safe_disconnect(client)
        # Give system time to fully release resources
        time.sleep(1)
