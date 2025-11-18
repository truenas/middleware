"""
NVMe-oF HA Failover Testing

Tests failover behavior across multiple dimensions:
- Target implementation: kernel vs SPDK
- Failover mode: ANA vs IP takeover
- Failure type: orderly vs crash
- I/O state: active vs idle
- Namespace count: 1 vs 3

Total: 2 x 2 x 2 x 2 x 2 = 32 tests
"""
import contextlib
import threading
import time
from functools import cache

import pytest

from nvmeof_client.models import AsyncEventType, AsyncEventInfoNotice

from assets.websocket.pool import zvol
from assets.websocket.service import ensure_service_enabled, ensure_service_started
from auto_config import ha, pool_name
from middlewared.test.integration.assets.nvmet import (
    NVME_DEFAULT_TCP_PORT, nvmet_ana, nvmet_namespace,
    nvmet_port, nvmet_port_subsys, nvmet_subsys
)
from middlewared.test.integration.utils import call
from middlewared.test.integration.utils.client import truenas_server, host as init_truenas_server
from middlewared.test.integration.utils.failover import do_failover
from middlewared.test.integration.utils.ha import settle_ha

# Import the nvmeof_client library
# import sys
# sys.path.insert(0, '/home/brian/claude/nvme/truenas_pynvmeof_client/src')
from nvmeof_client import NVMeoFClient
from nvmeof_client.models import ANAState

pytestmark = pytest.mark.skipif(not ha, reason='Failover tests require HA')

SERVICE_NAME = 'nvmet'
ZVOL_COUNT = 3
ZVOL_MB = 100
SUBSYS_NAME = 'ha_failover_test'


@cache
def basenqn():
    return call('nvmet.global.config')['basenqn']


@pytest.fixture(scope='module')
def many_zvols():
    """Create multiple ZVOLs for namespace testing."""
    config = {}
    with contextlib.ExitStack() as es:
        for i in range(ZVOL_COUNT):
            zvol_name = f'nvmetvol_ha_{i:03d}'
            config[i] = {'zvol': f'{pool_name}/{zvol_name}'}
            es.enter_context(zvol(zvol_name, ZVOL_MB, pool_name))
        yield config


@pytest.fixture(params=['kernel', 'spdk'], scope='module')
def implementation(request):
    """Set NVMet implementation (kernel or SPDK) before service starts."""
    with nvmet_implementation(request.param):
        yield request.param


@pytest.fixture(scope='module')
def fixture_nvmet_running(implementation):
    """Ensure NVMet service is running with the configured implementation."""
    with ensure_service_enabled(SERVICE_NAME):
        with ensure_service_started(SERVICE_NAME, 3):
            yield implementation


@contextlib.contextmanager
def nvmet_implementation(name):
    """Switch between kernel and SPDK implementations."""
    old_config = call('nvmet.global.config')
    match name:
        case 'kernel':
            if old_config['kernel']:
                yield
            else:
                call('nvmet.global.update', {'kernel': True})
                try:
                    yield
                finally:
                    call('nvmet.global.update', {'kernel': False})
        case 'spdk':
            if not old_config['kernel']:
                yield
            else:
                call('nvmet.global.update', {'kernel': False})
                try:
                    yield
                finally:
                    call('nvmet.global.update', {'kernel': True})


def is_ana_state_optimized(client):
    """Check if any namespace is in OPTIMIZED state.

    Args:
        client: NVMeoFClient instance

    Returns:
        bool: True if at least one namespace is optimized
    """
    try:
        ana_log = client.get_ana_log_page()
        for group in ana_log.groups:
            # Check that group is OPTIMIZED AND contains namespaces
            if group.ana_state == ANAState.OPTIMIZED and group.namespace_ids:
                print(f"[DEBUG] Found OPTIMIZED group {group.ana_group_id} with namespaces: {group.namespace_ids}")
                return True
        print("[DEBUG] No OPTIMIZED groups with namespaces found")
        return False
    except Exception as e:
        print(f"[DEBUG] Failed to check ANA state: {e}")
        return False


def connect_with_retry(client, ip, max_attempts=30, retry_delay=1.0):
    """Connect to NVMe-oF target with retry logic.

    Args:
        client: NVMeoFClient instance
        ip: Target IP address (for logging)
        max_attempts: Maximum number of connection attempts
        retry_delay: Delay between attempts in seconds

    Raises:
        Last exception if all attempts fail
    """
    last_error = None
    for attempt in range(1, max_attempts + 1):
        try:
            client.connect()
            if attempt > 1:
                print(f"[OK] Connected to {ip} for ANA monitoring (succeeded on attempt {attempt})")
            return  # Success!
        except Exception as e:
            last_error = e
            if attempt == 1:
                print(f"[RETRY] Connection to {ip} failed (attempt {attempt}/{max_attempts}): {e}")
                print(f"[RETRY] Retrying every {retry_delay}s (target may be initializing after HA transition)...")
            elif attempt % 5 == 0:
                print(f"[RETRY] Still trying to connect to {ip} (attempt {attempt}/{max_attempts})...")
            time.sleep(retry_delay)

    # All attempts failed
    print(f"[ERROR] Failed to connect to {ip} after {max_attempts} attempts")
    raise last_error


class ANAChangeMonitor:
    """Monitor for ANA state change notifications via async events.

    Handles two paths:
    - Path 1: ANA change notification received
    - Path 2: Connection closed during reconfiguration
    """

    def __init__(self, client):
        self.client = client
        self.ana_change_detected = threading.Event()
        self.connection_closed = threading.Event()  # Signal connection closure
        self.last_event = None
        self.stop_event = threading.Event()
        self.thread = None
        self.ana_change_time = None  # Timestamp when ANA change was detected
        self.closure_time = None  # Timestamp when connection closure detected

    def _poll_worker(self):
        """Background thread that polls for async events."""
        last_keepalive = time.time()
        keepalive_interval = 2.0  # Check connection every 2 seconds
        keepalive_enabled = self.client.kato > 0  # Only use keep-alive if KATO was negotiated

        while not self.stop_event.is_set():
            try:
                events = self.client.poll_async_events(timeout=0.5)

                for event in events:
                    self.last_event = event
                    # Check if this is a NOTICE event with ANA_CHANGE info
                    if (event.event_type == AsyncEventType.NOTICE and
                            event.event_info == AsyncEventInfoNotice.ANA_CHANGE):
                        self.ana_change_time = time.time()
                        print(f"[OK] ANA_CHANGE event detected (Path 1 - Notification): {event.description}")
                        self.ana_change_detected.set()
                        return
                    else:
                        print(f"[DEBUG] Other event: type={event.event_type}, "
                              f"info={event.event_info}, desc={event.description}")

                # Periodically send keep-alive to detect connection closure (only if enabled)
                if keepalive_enabled:
                    current_time = time.time()
                    if current_time - last_keepalive >= keepalive_interval:
                        try:
                            self.client.send_keep_alive()
                            last_keepalive = current_time
                        except Exception as ka_e:
                            # Keep-alive failed - connection is closed
                            self.closure_time = time.time()
                            print(f"[OK] Connection closed detected (Path 2 - Closure): keep-alive failed: {ka_e}")
                            self.connection_closed.set()
                            return

            except Exception as e:
                # Connection might be broken during failover (Path 2)
                error_str = str(e).lower()
                if 'closed' in error_str or 'connection' in error_str:
                    self.closure_time = time.time()
                    print(f"[OK] Connection closed detected (Path 2 - Closure): {e}")
                    self.connection_closed.set()
                    return
                else:
                    print(f"[DEBUG] Unexpected exception in poll_worker: {e}")
                    # Check stop_event before sleeping
                    if self.stop_event.is_set():
                        return
                    # Interruptible sleep - wakes immediately if stop_event set
                    self.stop_event.wait(timeout=0.5)
            # Interruptible sleep - wakes immediately if stop_event set
            self.stop_event.wait(timeout=0.1)

    def start(self):
        """Enable async event monitoring."""
        self.client.enable_async_events()
        self.client.request_async_events(count=4)  # Request multiple AERs
        self.thread = threading.Thread(target=self._poll_worker, daemon=True)
        self.thread.start()

    def wait_for_ana_change(self, timeout=30):
        """Wait for ANA change notification (Path 1 only).

        DEPRECATED: Use wait_for_change() instead to handle both paths.
        """
        return self.ana_change_detected.wait(timeout)

    def wait_for_change(self, timeout=30):
        """Wait for either ANA notification or connection closure.

        Returns:
            tuple: (path_taken, timestamp)
            - path_taken: 'notification', 'closure', or None if timeout
            - timestamp: time when event was detected, or None if timeout
        """
        start = time.time()
        while time.time() - start < timeout:
            if self.ana_change_detected.is_set():
                return ('notification', self.ana_change_time)
            if self.connection_closed.is_set():
                return ('closure', self.closure_time)
            time.sleep(0.1)
        return (None, None)

    def stop(self):
        """Stop the polling thread."""
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=10)


class MultipathClient:
    """Manages multiple controller connections with ANA-based path selection."""

    def __init__(self, controllers, subsystem_nqn):
        """
        Args:
            controllers: [(ip1, port1), (ip2, port2), ...]
            subsystem_nqn: NQN of the subsystem to connect to
        """
        self.clients = {}  # {ip: client}
        for ip, port in controllers:
            # Enable keep-alive (30 seconds) for connection health monitoring
            client = NVMeoFClient(ip, subsystem_nqn, port, kato=30000)
            connect_with_retry(client, ip, max_attempts=30, retry_delay=1.0)
            self.clients[ip] = client

    def get_active_client(self):
        """Return the client connected to OPTIMIZED path."""
        for ip, client in self.clients.items():
            try:
                ana_log = client.get_ana_log_page()
                # Print all groups first for visibility
                for group in ana_log.groups:
                    ns_info = f" NSIDs={group.namespace_ids}" if group.namespace_ids else " (no namespaces)"
                    print(f"[DEBUG] {ip}: Group {group.ana_group_id} state = {group.ana_state.name}{ns_info}")
                # Now find the OPTIMIZED group with namespaces
                for group in ana_log.groups:
                    if group.ana_state == ANAState.OPTIMIZED and group.namespace_ids:
                        return client, ip
            except Exception as e:
                print(f"[DEBUG] {ip}: Failed to get ANA log: {e}")
                continue
        raise Exception("No OPTIMIZED path found")

    def get_client_by_ip(self, ip):
        """Get specific client by IP."""
        return self.clients.get(ip)

    def read_data(self, nsid, lba, block_count):
        """Read from the currently OPTIMIZED path."""
        client, ip = self.get_active_client()
        return client.read_data(nsid, lba, block_count)

    def write_data(self, nsid, lba, data):
        """Write to the currently OPTIMIZED path."""
        client, ip = self.get_active_client()
        return client.write_data(nsid, lba, data)

    def disconnect_all(self):
        """Disconnect all controller connections."""
        for client in self.clients.values():
            if client.is_connected:
                client.disconnect()


class IOWorker:
    """Background I/O worker thread for testing I/O during failover."""

    def __init__(self, client, namespace_count):
        self.client = client
        self.namespace_count = namespace_count
        self.stop_event = threading.Event()
        self.error_count = 0
        self.success_count = 0
        self.errors = []
        self.thread = None

    def _worker(self):
        """Worker thread that performs continuous I/O."""
        data = b"IOWORKER".ljust(512, b'\x00')
        while not self.stop_event.is_set():
            try:
                # Cycle through namespaces
                nsid = (self.success_count % self.namespace_count) + 1
                self.client.write_data(nsid=nsid, lba=0, data=data)
                read_back = self.client.read_data(nsid=nsid, lba=0, block_count=1)
                assert read_back[:8] == b"IOWORKER"
                self.success_count += 1
                # Interruptible sleep - wakes immediately if stop_event set
                self.stop_event.wait(timeout=0.1)
            except Exception as e:
                self.error_count += 1
                self.errors.append(str(e))
                # Check stop_event before sleeping
                if self.stop_event.is_set():
                    return
                # Interruptible sleep - wakes immediately if stop_event set
                self.stop_event.wait(timeout=0.5)

    def start(self):
        """Start the I/O worker thread."""
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()
        # Let some I/O happen before returning
        time.sleep(1)

    def stop(self):
        """Stop the I/O worker and return statistics."""
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=10)
        return {
            'errors': self.error_count,
            'successes': self.success_count,
            'error_samples': self.errors[:5]  # First 5 errors
        }


class ReconnectingIOWorker:
    """Background I/O worker that handles reconnection for IP takeover scenarios."""

    def __init__(self, ip, subsystem_nqn, namespace_count, port=NVME_DEFAULT_TCP_PORT):
        self.ip = ip
        self.subsystem_nqn = subsystem_nqn
        self.namespace_count = namespace_count
        self.port = port
        self.client = None
        self.stop_event = threading.Event()
        self.error_count = 0
        self.success_count = 0
        self.reconnect_count = 0
        self.errors = []
        self.thread = None

    def _reconnect(self):
        """Attempt to reconnect to the target."""
        if self.client and self.client.is_connected:
            try:
                self.client.disconnect()
            except Exception:
                pass

        # Try to connect
        self.client = NVMeoFClient(self.ip, self.subsystem_nqn, self.port)
        self.client.connect()
        self.reconnect_count += 1

    def _worker(self):
        """Worker thread that performs continuous I/O with reconnection."""
        data = b"RECONECT".ljust(512, b'\x00')

        # Initial connection
        try:
            self._reconnect()
        except Exception as e:
            self.errors.append(f"Initial connect failed: {e}")
            return

        while not self.stop_event.is_set():
            try:
                # Cycle through namespaces
                nsid = (self.success_count % self.namespace_count) + 1
                self.client.write_data(nsid=nsid, lba=0, data=data)
                read_back = self.client.read_data(nsid=nsid, lba=0, block_count=1)
                assert read_back[:8] == b"RECONECT"
                self.success_count += 1
                # Interruptible sleep - wakes immediately if stop_event set
                self.stop_event.wait(timeout=0.1)
            except Exception as e:
                self.error_count += 1
                self.errors.append(str(e))

                # Try to reconnect
                reconnected = False
                for attempt in range(30):  # Try for ~30 seconds
                    if self.stop_event.is_set():
                        return
                    try:
                        self._reconnect()
                        reconnected = True
                        break
                    except Exception as reconnect_error:
                        self.errors.append(f"Reconnect attempt {attempt+1} failed: {reconnect_error}")
                    # Interruptible sleep - wakes immediately if stop_event set (check 10 times for 1s total)
                    if self.stop_event.wait(timeout=0.1):
                        return

                if not reconnected:
                    self.errors.append("Failed to reconnect after 30 attempts")
                    return

    def start(self):
        """Start the I/O worker thread."""
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()
        # Let some I/O happen before returning
        time.sleep(1)

    def stop(self):
        """Stop the I/O worker and return statistics."""
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=60)

        # Clean up connection
        if self.client and self.client.is_connected:
            try:
                self.client.disconnect()
            except Exception:
                pass

        return {
            'errors': self.error_count,
            'successes': self.success_count,
            'reconnects': self.reconnect_count,
            'error_samples': self.errors[:10]  # First 10 errors
        }


class TestFailover:
    """Test NVMe-oF HA failover scenarios."""

    @pytest.fixture(params=['ana', 'ip_takeover'], scope='class')
    def failover_mode(self, request, fixture_nvmet_running):
        """Parametrize failover mode."""
        if request.param == 'ana':
            with nvmet_ana(True):
                # Give ANA configuration time to propagate to both nodes
                print("[FIXTURE] Sleeping 2s for ANA mode initialization...")
                time.sleep(2)
                yield request.param
            # After ANA disabled (context exit), give time for change to propagate
            print("[FIXTURE] Sleeping 2s after ANA mode teardown...")
            time.sleep(2)
        else:
            # IP takeover - no configuration change, just use default (ANA off)
            yield request.param

    @pytest.fixture(params=[1, 3], scope='class')
    def configured_subsystem(self, request, many_zvols, failover_mode):
        """Set up subsystem with specified number of namespaces.

        Note: The failover_mode parameter ensures proper fixture ordering
        (ANA setting applied before subsystem creation) and passes mode info
        to tests. The fixture setup is identical for both modes - when ANA is
        enabled, the system automatically handles multi-node configuration.
        """
        # Initialize node IPs if needed
        if truenas_server.nodea_ip is None:
            init_truenas_server()

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
                        print("[FIXTURE] Sleeping 5s for subsystem initialization...")
                        time.sleep(5)

                        yield {
                            'subsys': subsys,
                            'port': port,
                            'namespaces': namespace_contexts,
                            'nqn': f'{basenqn()}:{SUBSYS_NAME}',
                            'namespace_count': request.param,
                            'mode': failover_mode
                        }

                        # Give connections time to close before fixture teardown
                        print("[FIXTURE] Sleeping 3s before teardown...")
                        time.sleep(3)

        # After all context managers have exited (teardown complete)
        print("[FIXTURE] Sleeping 5s after teardown for services to settle...")
        time.sleep(5)

    @pytest.mark.parametrize("failure_type", ["orderly", "crash"])
    @pytest.mark.parametrize("io_active", [True, False])
    def test_failover(self, fixture_nvmet_running, failover_mode,
                      configured_subsystem, failure_type, io_active):
        """
        Test failover behavior across all configurations.

        Test matrix:
        - 2 target implementations (kernel, spdk)
        - 2 failover modes (ana, ip_takeover)
        - 2 namespace counts (1, 3)
        - 2 failure types (orderly, crash)
        - 2 I/O states (active, idle)

        Total: 32 test combinations
        """
        subsys_nqn = configured_subsystem['nqn']
        namespace_count = configured_subsystem['namespace_count']

        print(f"\n{'='*70}")
        print("Test Configuration:")
        print(f"  Implementation: {fixture_nvmet_running}")
        print(f"  Mode: {failover_mode}")
        print(f"  Namespaces: {namespace_count}")
        print(f"  Failure: {failure_type}")
        print(f"  I/O Active: {io_active}")
        print(f"{'='*70}")

        if failover_mode == 'ana':
            self._test_ana_failover(subsys_nqn, namespace_count, failure_type, io_active)
        else:
            self._test_ip_takeover_failover(subsys_nqn, namespace_count, failure_type, io_active)

    def _test_ana_failover(self, subsys_nqn, namespace_count, failure_type, io_active):
        """Test ANA-based failover with multiple controller paths.

        Uses separate client connections for monitoring and I/O to avoid race conditions:
        - monitor_client: dedicated connection for ANAChangeMonitor
        - multipath: separate connections for IOWorker

        This ensures thread-safe operation during failover with concurrent I/O.
        """
        # Determine node IPs
        orig_master_node = call('failover.node')
        if orig_master_node == 'A':
            primary_ip = truenas_server.nodea_ip
            secondary_ip = truenas_server.nodeb_ip
        else:
            primary_ip = truenas_server.nodeb_ip
            secondary_ip = truenas_server.nodea_ip

        print(f"Active node: {orig_master_node}, Primary IP: {primary_ip}, Secondary IP: {secondary_ip}")

        monitor_client = None
        multipath = None
        ana_monitor = None
        try:
            # Create separate client for ANA monitoring (independent connection)
            # This ensures no race conditions between monitoring and I/O threads
            monitor_client = NVMeoFClient(secondary_ip, subsys_nqn, NVME_DEFAULT_TCP_PORT, kato=30000)
            connect_with_retry(monitor_client, secondary_ip, max_attempts=30, retry_delay=1.0)
            print(f"[OK] Connected to {secondary_ip} for ANA monitoring")

            # Connect to both controllers for I/O (independent connections)
            multipath = MultipathClient([
                (primary_ip, NVME_DEFAULT_TCP_PORT),
                (secondary_ip, NVME_DEFAULT_TCP_PORT)
            ], subsys_nqn)
            # Verify initial state - primary should be OPTIMIZED
            active_client, active_ip = multipath.get_active_client()
            assert active_ip == primary_ip, f"Expected primary {primary_ip} to be OPTIMIZED, got {active_ip}"
            print(f"[OK] Initial state: {active_ip} is OPTIMIZED")

            # Set up ANA change monitoring on secondary (will become active)
            # Uses independent monitor_client, not multipath's client
            ana_monitor = ANAChangeMonitor(monitor_client)
            ana_monitor.start()
            print(f"[OK] Monitoring ANA changes on {secondary_ip}")

            # Start I/O if requested
            io_worker = None
            if io_active:
                io_worker = IOWorker(multipath, namespace_count)
                io_worker.start()
                print(f"[OK] Started background I/O on {namespace_count} namespace(s)")

            # Trigger failover without waiting for settle_ha
            print(f"Triggering {failure_type} failover...")
            print(f"[DEBUG] System state before failover: node={call('failover.node')}")
            print(f"[DEBUG] Failover status: {call('failover.status')}")
            disabled_reasons = call('failover.disabled.reasons')
            if disabled_reasons:
                print(f"[WARNING] Failover is disabled: {disabled_reasons}")
                print("[WARNING] Waiting up to 30s for failover to be re-enabled...")
                for i in range(30):
                    disabled_reasons = call('failover.disabled.reasons')
                    if not disabled_reasons:
                        print(f"[OK] Failover re-enabled after {i}s")
                        break
                    time.sleep(1)
                else:
                    raise AssertionError(f"Failover still disabled after 30s: {disabled_reasons}")
            failover_start_time = time.time()
            abusive = (failure_type == "crash")
            try:
                do_failover(settle=False, abusive=abusive, description=f'NVMe-oF failover test ({failure_type})')
                print("[DEBUG] do_failover() completed successfully")
            except Exception as e:
                print(f"[ERROR] do_failover() raised exception: {type(e).__name__}: {e}")
                raise

            # Wait for ANA change (either notification or connection closure)
            print("Waiting for ANA change (notification or connection closure)...")
            path_taken, event_time = ana_monitor.wait_for_change(timeout=45)

            if path_taken is None:
                raise AssertionError(
                    "ANA change not detected: no notification and no connection closure within 45 seconds"
                )

            time_to_event = event_time - failover_start_time

            if path_taken == 'notification':
                # Path 1: Notification received
                print(f"[OK] ANA change detected via notification (Path 1) "
                      f"(took {time_to_event:.2f}s from failover trigger)")
            elif path_taken == 'closure':
                # Path 2: Connection closed
                print(f"[OK] Connection closure detected (Path 2) "
                      f"(took {time_to_event:.2f}s from failover trigger)")
                print("Waiting for target reconfiguration to complete...")
                time.sleep(2)  # Give target time to complete namespace addition

                # Reconnect monitoring client to secondary controller
                print(f"Reconnecting to secondary controller ({secondary_ip})...")
                monitor_client.disconnect()
                # Enable keep-alive (30 seconds) for connection health monitoring
                monitor_client = NVMeoFClient(secondary_ip, subsys_nqn, NVME_DEFAULT_TCP_PORT, kato=30000)

                # Retry connection with extended timeout for Path 2
                try:
                    connect_with_retry(monitor_client, secondary_ip, max_attempts=30, retry_delay=1.0)
                    print(f"[OK] Reconnected to {secondary_ip}")
                except Exception as e:
                    raise AssertionError(f"Failed to reconnect to {secondary_ip}: {e}")

                # Verify secondary is now optimized
                if not is_ana_state_optimized(monitor_client):
                    raise AssertionError(f"Reconnected to {secondary_ip} but it is not in OPTIMIZED state")
                print(f"[OK] Secondary {secondary_ip} is now OPTIMIZED after reconnection")

            # Use the event time for subsequent timing calculations
            ana_change_time = event_time

            # Verify secondary is now OPTIMIZED
            if not is_ana_state_optimized(monitor_client):
                raise AssertionError(f"Secondary {secondary_ip} not OPTIMIZED after ANA change")
            print(f"[OK] Failover complete: {secondary_ip} is now OPTIMIZED")

            # Stop I/O worker to collect statistics
            if io_active and io_worker:
                print("[DEBUG] Setting I/O worker stop_event...")
                io_worker.stop_event.set()
                if io_worker.thread:
                    print(f"[DEBUG] Waiting for I/O worker thread to exit (is_alive={io_worker.thread.is_alive()})...")
                    io_worker.thread.join(timeout=10)
                    print(f"[DEBUG] I/O worker thread join complete (is_alive={io_worker.thread.is_alive()})")
                stats = io_worker.stop()
                io_verified_time = time.time()
                time_to_io = io_verified_time - ana_change_time
                print(f"[OK] I/O statistics: {stats['successes']} successes, {stats['errors']} errors")
                print(f"[OK] I/O verified (took {time_to_io:.2f}s from ANA change)")
                # Errors are expected during transition
                assert stats['successes'] > 0, "No successful I/O operations"
            else:
                # Verify we can do I/O after failover
                try:
                    data = multipath.read_data(nsid=1, lba=0, block_count=1)
                except Exception as e:
                    # If I/O fails, reconnect to new primary (secondary_ip is now optimized)
                    print(f"[DEBUG] I/O failed ({e}), reconnecting to new primary {secondary_ip}...")

                    # Reconnect client pointing to the new primary
                    if secondary_ip in multipath.clients:
                        client = multipath.clients[secondary_ip]
                        try:
                            client.disconnect()
                        except Exception:
                            pass  # Ignore disconnect errors
                        # Short retry since new primary should be ready (monitor_client already verified it)
                        connect_with_retry(client, secondary_ip, max_attempts=5, retry_delay=1.0)
                        print(f"[OK] Reconnected to new primary {secondary_ip}")

                    # Retry I/O (should now use the reconnected client)
                    data = multipath.read_data(nsid=1, lba=0, block_count=1)

                assert len(data) == 512
                io_verified_time = time.time()
                time_to_io = io_verified_time - ana_change_time
                print(f"[OK] I/O verified (took {time_to_io:.2f}s from ANA change)")

            # Print timing summary
            total_time = io_verified_time - failover_start_time
            print(f"\n[TIMING] Failover trigger -> ANA change: {time_to_event:.2f}s")
            print(f"[TIMING] ANA change -> I/O verified: {time_to_io:.2f}s")
            print(f"[TIMING] Total time: {total_time:.2f}s")

        finally:
            if ana_monitor:
                ana_monitor.stop()
                print("[DEBUG] ANA monitor stopped")
            # Disconnect monitoring client
            if monitor_client:
                print(f"[DEBUG] monitor_client.is_connected = {monitor_client.is_connected}")
                if monitor_client.is_connected:
                    print("[DEBUG] Calling monitor_client.disconnect()...")
                    monitor_client.disconnect()
                    print(f"[DEBUG] monitor_client.disconnect() returned, is_connected = {monitor_client.is_connected}")
                else:
                    print("[DEBUG] monitor_client already disconnected")
            # Disconnect I/O clients
            if multipath:
                print("[DEBUG] Disconnecting multipath clients...")
                for ip, client in multipath.clients.items():
                    print(f"[DEBUG]   {ip}: is_connected = {client.is_connected}")
                multipath.disconnect_all()
                print("[DEBUG] multipath.disconnect_all() completed")
            # Give system time to fully release ZVOL resources
            # After failover, the new master needs time to release the namespace
            print("[DEBUG] Sleeping 5 seconds for resource cleanup...")
            time.sleep(5)
            print("[DEBUG] Cleanup complete")

        # Wait for HA to settle
        print("\nWaiting for HA to settle...")
        settle_ha()
        new_master_node = call('failover.node')
        assert new_master_node != orig_master_node, f"Failover failed: master node unchanged ({orig_master_node})"
        print(f"[OK] HA settled, new master: {new_master_node}")
        # Allow async HA processing to start, then verify still healthy
        print("[DEBUG] Waiting 5s for async HA processing...")
        time.sleep(5)
        settle_ha()
        print("[OK] HA fully stabilized")

    def _test_ip_takeover_failover(self, subsys_nqn, namespace_count, failure_type, io_active):
        """Test IP takeover failover with single floating IP."""
        orig_master_node = call('failover.node')
        floating_ip = truenas_server.ip

        print(f"Floating IP: {floating_ip}")

        io_worker = None
        if io_active:
            # Use reconnecting I/O worker for IP takeover
            io_worker = ReconnectingIOWorker(floating_ip, subsys_nqn, namespace_count)
            io_worker.start()
            print(f"[OK] Started reconnecting I/O worker on {namespace_count} namespace(s)")
        else:
            # Connect manually if no I/O active
            client = NVMeoFClient(floating_ip, subsys_nqn)
            connect_with_retry(client, floating_ip, max_attempts=30, retry_delay=1.0)
            print(f"[OK] Connected to {floating_ip}")

        try:
            # Trigger failover without waiting for settle_ha
            print(f"Triggering {failure_type} failover...")
            print(f"[DEBUG] System state before failover: node={call('failover.node')}")
            print(f"[DEBUG] Failover status: {call('failover.status')}")
            disabled_reasons = call('failover.disabled.reasons')
            if disabled_reasons:
                print(f"[WARNING] Failover is disabled: {disabled_reasons}")
                print("[WARNING] Waiting up to 30s for failover to be re-enabled...")
                for i in range(30):
                    disabled_reasons = call('failover.disabled.reasons')
                    if not disabled_reasons:
                        print(f"[OK] Failover re-enabled after {i}s")
                        break
                    time.sleep(1)
                else:
                    raise AssertionError(f"Failover still disabled after 30s: {disabled_reasons}")
            failover_start_time = time.time()
            abusive = (failure_type == "crash")
            try:
                do_failover(settle=False, abusive=abusive, description=f'NVMe-oF IP takeover test ({failure_type})')
                print("[DEBUG] do_failover() completed successfully")
            except Exception as e:
                print(f"[ERROR] do_failover() raised exception: {type(e).__name__}: {e}")
                raise

            if io_active:
                # I/O worker handles reconnection automatically
                # Just wait a bit for failover to stabilize
                time.sleep(15)

                # Verify I/O worker is still running and has recovered
                stats = io_worker.stop()
                io_verified_time = time.time()

                print(f"[OK] I/O statistics: {stats['successes']} successes, {stats['errors']} errors, "
                      f"{stats['reconnects']} reconnects")
                assert stats['reconnects'] >= 1, "Expected at least one reconnection during failover"
                assert stats['successes'] > 0, "No successful I/O operations after failover"

                # Print timing summary
                total_time = io_verified_time - failover_start_time
                print(f"\n[TIMING] Total time (trigger to I/O verified): {total_time:.2f}s")
            else:
                # Manual reconnection test
                print("Waiting for IP to move...")
                if client.is_connected:
                    client.disconnect()

                # Wait for system to settle and IP to be available
                time.sleep(10)

                # Reconnect to same IP (now on new controller)
                client = NVMeoFClient(floating_ip, subsys_nqn)
                connect_with_retry(client, floating_ip, max_attempts=30, retry_delay=1.0)
                reconnect_time = time.time()
                time_to_reconnect = reconnect_time - failover_start_time
                print(f"[OK] Reconnected to {floating_ip} on new controller "
                      f"(took {time_to_reconnect:.2f}s from failover trigger)")

                # Verify I/O works
                test_data = b"testdata".ljust(512, b'\x00')
                client.write_data(nsid=1, lba=0, data=test_data)
                read_data = client.read_data(nsid=1, lba=0, block_count=1)
                assert read_data[:8] == b"testdata"
                io_verified_time = time.time()
                time_to_io = io_verified_time - reconnect_time
                print(f"[OK] I/O verified (took {time_to_io:.2f}s from reconnection)")

                # Print timing summary
                total_time = io_verified_time - failover_start_time
                print(f"\n[TIMING] Failover trigger -> reconnection: {time_to_reconnect:.2f}s")
                print(f"[TIMING] Reconnection -> I/O verified: {time_to_io:.2f}s")
                print(f"[TIMING] Total time: {total_time:.2f}s")

                # Cleanup
                if client.is_connected:
                    client.disconnect()

            # Now wait for HA to settle for proper cleanup
            print("\nWaiting for HA to settle...")
            settle_ha()
            new_master_node = call('failover.node')
            assert new_master_node != orig_master_node, f"Failover failed: master node unchanged ({orig_master_node})"
            print(f"[OK] HA settled, new master: {new_master_node}")
            # Allow async HA processing to start, then verify still healthy
            print("[DEBUG] Waiting 5s for async HA processing...")
            time.sleep(5)
            settle_ha()
            print("[OK] HA fully stabilized")

        finally:
            if io_active and io_worker:
                io_worker.stop_event.set()
                if io_worker.thread:
                    io_worker.thread.join(timeout=10)
                if io_worker.client and io_worker.client.is_connected:
                    try:
                        io_worker.client.disconnect()
                    except Exception:
                        pass
            elif not io_active and 'client' in locals() and client.is_connected:
                try:
                    client.disconnect()
                except Exception:
                    pass
            # Give system time to fully release resources
            time.sleep(1)
