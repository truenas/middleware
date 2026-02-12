"""
Shared utilities for NVMe-oF HA failover tests.

This module contains:
- Constants and configuration
- Helper functions for connection and state checking
- Helper classes for monitoring and I/O operations

Note: Pytest fixtures are in conftest.py for automatic discovery.
"""

import contextlib
import threading
import time
from functools import cache
from typing import Any, Iterator

from nvmeof_client import NVMeoFClient
from nvmeof_client.models import ANAState, AsyncEventType, AsyncEventInfoNotice

from middlewared.test.integration.assets.nvmet import NVME_DEFAULT_TCP_PORT
from middlewared.test.integration.utils import call
from middlewared.test.integration.utils.client import truenas_server
from middlewared.test.integration.utils.failover import do_failover
from middlewared.test.integration.utils.ha import settle_ha

# ============================================================================
# Constants
# ============================================================================

SERVICE_NAME = 'nvmet'
ZVOL_MB = 100
MAX_FAILOVER_TIME = 90  # Maximum acceptable failover time in seconds

# Connection and retry parameters
DEFAULT_CONNECTION_ATTEMPTS = 30  # Standard connection retry attempts
PATH_WAIT_MAX_ATTEMPTS = (
    60  # Maximum attempts when waiting for path to become accessible
)
QUICK_RETRY_ATTEMPTS = 5  # Quick retry for already-initialized connections
CONNECTION_RETRY_DELAY = 1.0  # Seconds between connection retry attempts

# NVMe parameters
NVME_KEEPALIVE_MS = 30000  # Keep-alive timeout in milliseconds (30 seconds)

# System settle times
HA_SETTLE_SLEEP = 5  # Seconds to sleep between HA settle calls
IP_MOVE_SETTLE_TIME = 10  # Seconds to wait for IP to move between nodes
RESOURCE_CLEANUP_SLEEP = 15  # Seconds for backend to release ZVOL resources

# Thread timeouts
WORKER_THREAD_JOIN_TIMEOUT = 10  # Seconds to wait for worker thread to exit
RECONNECT_WORKER_JOIN_TIMEOUT = (
    60  # Seconds for reconnecting worker (longer for failover)
)
ANA_CHANGE_TIMEOUT = 45  # Seconds to wait for ANA state change notification


# ============================================================================
# Helper Functions
# ============================================================================


@cache
def basenqn() -> str:
    return call('nvmet.global.config')['basenqn']


@contextlib.contextmanager
def nvmet_implementation(name: str) -> Iterator[None]:
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


def is_ana_state_optimized(client: NVMeoFClient) -> bool:
    """Check if any namespace is in OPTIMIZED state.

    Args:
        client: NVMeoFClient instance

    Returns:
        True if at least one namespace is optimized
    """
    try:
        ana_log = client.get_ana_log_page()
        for group in ana_log.groups:
            # Check that group is OPTIMIZED AND contains namespaces
            if group.ana_state == ANAState.OPTIMIZED and group.namespace_ids:
                print(
                    f'[DEBUG] Found OPTIMIZED group {group.ana_group_id} with namespaces: {group.namespace_ids}'
                )
                return True
        print('[DEBUG] No OPTIMIZED groups with namespaces found')
        return False
    except Exception as e:
        print(f'[DEBUG] Failed to check ANA state: {e}')
        return False


def safe_disconnect(client: NVMeoFClient | None) -> None:
    """Safely disconnect NVMe-oF client, ignoring any errors.

    Args:
        client: NVMeoFClient instance or None
    """
    if client:
        try:
            client.disconnect()
        except Exception:
            pass


def print_test_config(title: str, **config: Any) -> None:
    """Print test configuration banner with consistent formatting.

    Args:
        title: Banner title
        **config: Configuration key-value pairs to display
    """
    print(f'\n{"=" * 70}')
    print(f'{title}:')
    for key, value in config.items():
        display_key = key.replace('_', ' ')
        print(f'  {display_key}: {value}')
    print(f'{"=" * 70}')


def connect_with_retry(
    client: NVMeoFClient,
    ip: str,
    max_attempts: int = DEFAULT_CONNECTION_ATTEMPTS,
    retry_delay: float = CONNECTION_RETRY_DELAY,
) -> None:
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
                print(
                    f'[OK] Connected to {ip} for ANA monitoring (succeeded on attempt {attempt})'
                )
            return  # Success!
        except Exception as e:
            last_error = e
            if attempt == 1:
                print(
                    f'[RETRY] Connection to {ip} failed (attempt {attempt}/{max_attempts}): {e}'
                )
                print(
                    f'[RETRY] Retrying every {retry_delay}s (target may be initializing after HA transition)...'
                )
            elif attempt % 5 == 0:
                print(
                    f'[RETRY] Still trying to connect to {ip} (attempt {attempt}/{max_attempts})...'
                )
            time.sleep(retry_delay)

    # All attempts failed
    print(f'[ERROR] Failed to connect to {ip} after {max_attempts} attempts')
    raise last_error


def get_node_ips() -> tuple[str, str, str]:
    """Get original active and standby node IPs based on current failover state.

    Determines which node is currently active and returns the IP addresses
    in a semantically meaningful order. The "orig_" prefix indicates these
    represent the state at the time this function is called (before any failover).

    Returns:
        Tuple of (orig_master_node, orig_active_ip, orig_standby_ip):
            - orig_master_node: 'A' or 'B' indicating current active node
            - orig_active_ip: IP of currently active node
            - orig_standby_ip: IP of currently standby node
    """
    orig_master_node = call('failover.node')
    if orig_master_node == 'A':
        orig_active_ip = truenas_server.nodea_ip
        orig_standby_ip = truenas_server.nodeb_ip
    else:
        orig_active_ip = truenas_server.nodeb_ip
        orig_standby_ip = truenas_server.nodea_ip

    return orig_master_node, orig_active_ip, orig_standby_ip


def wait_for_ana_path_optimized(
    ip: str,
    subsys_nqn: str,
    start_time: float,
    max_attempts: int = PATH_WAIT_MAX_ATTEMPTS,
) -> float:
    """Wait for ANA path to become OPTIMIZED with retry logic.

    Creates a new client connection on each attempt to handle cases where
    the target closes connections during reconfiguration (e.g., SPDK).

    Args:
        ip: Target IP address to connect to
        subsys_nqn: NVMe subsystem NQN
        start_time: Reference timestamp for elapsed time calculation
        max_attempts: Maximum number of retry attempts

    Returns:
        Unix timestamp when path became accessible

    Raises:
        AssertionError: If path doesn't become OPTIMIZED within timeout
    """
    test_client = None
    try:
        for attempt in range(max_attempts):
            try:
                # Disconnect previous client if exists
                safe_disconnect(test_client)

                # Create fresh client and connect
                test_client = NVMeoFClient(ip, subsys_nqn)
                test_client.connect()

                # Check if path is OPTIMIZED
                if is_ana_state_optimized(test_client):
                    path_accessible_time = time.time()
                    elapsed = path_accessible_time - start_time
                    print(f'[OK] ANA path became OPTIMIZED after {elapsed:.2f}s')
                    return path_accessible_time

                # Not optimized yet - disconnect immediately for explicit resource cleanup
                # (next iteration will also disconnect, but this is clearer and releases sooner)
                test_client.disconnect()
                time.sleep(1)
            except Exception as e:
                if attempt < max_attempts - 1:
                    time.sleep(1)
                else:
                    raise AssertionError(
                        f'ANA path did not become OPTIMIZED after {max_attempts}s: {e}'
                    )
    finally:
        # Cleanup: ensure client is disconnected
        safe_disconnect(test_client)


def wait_for_ip_takeover(
    vip: str,
    subsys_nqn: str,
    start_time: float,
    max_attempts: int = PATH_WAIT_MAX_ATTEMPTS,
) -> float:
    """Wait for Virtual IP (VIP) to become accessible after IP takeover.

    Includes an initial sleep to allow the VIP to move between nodes
    before attempting connection.

    Args:
        vip: Virtual IP address
        subsys_nqn: NVMe subsystem NQN
        start_time: Reference timestamp for elapsed time calculation
        max_attempts: Maximum connection retry attempts

    Returns:
        Unix timestamp when VIP became accessible

    Raises:
        AssertionError: If VIP doesn't become accessible within timeout
    """
    # Wait for VIP to move between nodes
    print('[INFO] Waiting for VIP to move...')
    time.sleep(IP_MOVE_SETTLE_TIME)

    test_client = NVMeoFClient(vip, subsys_nqn)
    try:
        connect_with_retry(test_client, vip, max_attempts=max_attempts)
        path_accessible_time = time.time()
        elapsed = path_accessible_time - start_time
        print(f'[OK] VIP reconnected after {elapsed:.2f}s')
        return path_accessible_time
    except Exception as e:
        raise AssertionError(f'Failed to reconnect to VIP after {max_attempts}s: {e}')
    finally:
        test_client.disconnect()


def double_settle_ha(sleep_seconds: int = HA_SETTLE_SLEEP) -> None:
    """Settle HA twice with sleep in between for stability.

    This pattern ensures HA reaches a stable state by:
    1. Initial settle to let HA quiesce
    2. Sleep to allow async processing
    3. Final settle to confirm stability

    Args:
        sleep_seconds: Seconds to sleep between settle calls
    """
    settle_ha()
    time.sleep(sleep_seconds)
    settle_ha()


def trigger_failover_with_checks(description: str, settle: bool = False) -> float:
    """Trigger failover with pre-flight checks and error handling.

    Checks if failover is currently disabled and waits up to 30s for it to be
    re-enabled before triggering the failover operation.

    Args:
        description: Description string for the failover operation
        settle: Whether to wait for HA to settle after failover

    Returns:
        Unix timestamp when failover was triggered

    Raises:
        AssertionError: If failover is disabled and doesn't re-enable within 30s
        Exception: Any exception raised by do_failover()
    """
    print('Triggering failover...')
    print(f'[DEBUG] System state before failover: node={call("failover.node")}')
    print(f'[DEBUG] Failover status: {call("failover.status")}')

    # Check if failover is currently disabled
    disabled_reasons = call('failover.disabled.reasons')
    if disabled_reasons:
        print(f'[WARNING] Failover is disabled: {disabled_reasons}')
        print('[WARNING] Waiting up to 30s for failover to be re-enabled...')
        for i in range(30):
            disabled_reasons = call('failover.disabled.reasons')
            if not disabled_reasons:
                print(f'[OK] Failover re-enabled after {i}s')
                break
            time.sleep(1)
        else:
            raise AssertionError(
                f'Failover still disabled after 30s: {disabled_reasons}'
            )

    # Trigger the failover
    failover_start_time = time.time()
    try:
        do_failover(settle=settle, abusive=False, description=description)
        print('[DEBUG] do_failover() completed successfully')
    except Exception as e:
        print(f'[ERROR] do_failover() raised exception: {type(e).__name__}: {e}')
        raise

    return failover_start_time


# ============================================================================
# Helper Classes
# ============================================================================

"""
Threading Architecture for HA Failover Tests

These tests use background threads to simulate real-world scenarios where I/O and
monitoring happen concurrently with failover events. The architecture follows a
strict "one thread, one client" principle to avoid thread-safety issues.

Core Principle: ONE THREAD = ONE CLIENT INSTANCE
    Each thread uses its own dedicated NVMeoFClient or MultipathClient instance.
    Clients are NOT shared across threads. This design:
    - Avoids need for locks and synchronization
    - Mirrors real NVMe-oF multipath behavior (separate connections per path)
    - Keeps code simple and tests easy to reason about
    - Ensures thread failures don't affect other threads

Worker Classes (all run in background threads):

1. ANAChangeMonitor
   - Monitors for ANA state change notifications during failover
   - Runs in background thread polling for async events
   - Uses its own dedicated NVMeoFClient instance
   - Detects when failover triggers ANA path state changes

2. IOWorker
   - Performs continuous I/O operations during failover
   - Tests that I/O can continue (with expected errors) during transition
   - Uses its own MultipathClient or NVMeoFClient instance
   - Tracks success/error counts to verify failover behavior

3. ReconnectingIOWorker
   - Like IOWorker but handles automatic reconnection
   - Used for IP takeover scenarios where VIP moves between nodes
   - Creates and manages its own NVMeoFClient instance
   - Automatically reconnects when connection is lost

Proper Usage Pattern:

    # Main test thread
    orig_master_node, orig_active_ip, orig_standby_ip = get_node_ips()

    # Create SEPARATE client for ANA monitoring (dedicated to monitor thread)
    monitor_client = NVMeoFClient(orig_standby_ip, subsys_nqn, ...)
    connect_with_retry(monitor_client, orig_standby_ip)

    # Create SEPARATE multipath for I/O (dedicated to I/O worker thread)
    multipath = MultipathClient(
        [(orig_active_ip, port), (orig_standby_ip, port)],
        subsys_nqn
    )

    # Each worker gets its own client - NO SHARING
    ana_monitor = ANAChangeMonitor(monitor_client)  # Uses monitor_client
    io_worker = IOWorker(multipath, namespace_count)  # Uses multipath

    # Start workers (each runs in its own thread with its own client)
    ana_monitor.start()
    io_worker.start()

    # Trigger failover while workers run concurrently
    trigger_failover_with_checks(...)

    # Workers operate independently with their own connections
    # No race conditions because no shared client state

Thread Safety Notes:
    - MultipathClient is NOT thread-safe (no locks on internal state)
    - NVMeoFClient is assumed NOT thread-safe for concurrent operations
    - Worker classes manage their own threads and are safe to use from main thread
    - Never share a client instance across multiple threads
"""


class ANAChangeMonitor:
    """Monitor for ANA state change notifications during failover.

    Runs in background thread to detect when failover triggers ANA state changes,
    measuring the timing of the event. This is critical for testing failover
    performance - we need to know when the standby controller becomes OPTIMIZED.

    Two Detection Paths:
        Path 1 (Notification): Controller sends ANA_CHANGE async event notification
            - Fast detection (controller proactively notifies us)
            - Preferred path when controller supports it

        Path 2 (Connection Closure): Connection closes during reconfiguration
            - Detected via keep-alive failure
            - Fallback when controller doesn't send notification
            - Requires reconnection after detection

    Usage:
        monitor_client = NVMeoFClient(standby_ip, subsys_nqn, kato=NVME_KEEPALIVE_MS)
        connect_with_retry(monitor_client, standby_ip)

        monitor = ANAChangeMonitor(monitor_client)
        monitor.start()  # Starts background thread

        trigger_failover_with_checks(...)

        path_taken, event_time = monitor.wait_for_change(timeout=45)
        # path_taken is 'notification' (Path 1) or 'closure' (Path 2)
        # event_time is timestamp when change was detected

        monitor.stop()  # Cleanup

    Thread Safety:
        See "Threading Architecture" overview above. Uses dedicated client instance.
    """

    def __init__(self, client: NVMeoFClient) -> None:
        self.client = client
        self.ana_change_detected = threading.Event()
        self.connection_closed = threading.Event()  # Signal connection closure
        self.last_event: Any | None = None
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.ana_change_time: float | None = (
            None  # Timestamp when ANA change was detected
        )
        self.closure_time: float | None = (
            None  # Timestamp when connection closure detected
        )

    def _poll_worker(self) -> None:
        """Background thread that polls for async events."""
        last_keepalive = time.time()
        keepalive_interval = 2.0  # Check connection every 2 seconds
        keepalive_enabled = (
            self.client.kato > 0
        )  # Only use keep-alive if KATO was negotiated

        while not self.stop_event.is_set():
            try:
                events = self.client.poll_async_events(timeout=0.5)

                for event in events:
                    self.last_event = event
                    # Check if this is a NOTICE event with ANA_CHANGE info
                    if (
                        event.event_type == AsyncEventType.NOTICE
                        and event.event_info == AsyncEventInfoNotice.ANA_CHANGE
                    ):
                        self.ana_change_time = time.time()
                        print(
                            f'[OK] ANA_CHANGE event detected (Path 1 - Notification): {event.description}'
                        )
                        self.ana_change_detected.set()
                        return
                    else:
                        print(
                            f'[DEBUG] Other event: type={event.event_type}, '
                            f'info={event.event_info}, desc={event.description}'
                        )

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
                            print(
                                f'[OK] Connection closed detected (Path 2 - Closure): keep-alive failed: {ka_e}'
                            )
                            self.connection_closed.set()
                            return

            except Exception as e:
                # Connection might be broken during failover (Path 2)
                error_str = str(e).lower()
                if 'closed' in error_str or 'connection' in error_str:
                    self.closure_time = time.time()
                    print(f'[OK] Connection closed detected (Path 2 - Closure): {e}')
                    self.connection_closed.set()
                    return
                else:
                    print(f'[DEBUG] Unexpected exception in poll_worker: {e}')
                    # Check stop_event before sleeping
                    if self.stop_event.is_set():
                        return
                    # Interruptible sleep - wakes immediately if stop_event set
                    self.stop_event.wait(timeout=0.5)
            # Interruptible sleep - wakes immediately if stop_event set
            self.stop_event.wait(timeout=0.1)

    def start(self) -> None:
        """Enable async event monitoring."""
        self.client.enable_async_events()
        self.client.request_async_events(count=4)  # Request multiple AERs
        self.thread = threading.Thread(target=self._poll_worker, daemon=True)
        self.thread.start()

    def wait_for_ana_change(self, timeout: float = 30) -> bool:
        """Wait for ANA change notification (Path 1 only).

        DEPRECATED: Use wait_for_change() instead to handle both paths.
        """
        return self.ana_change_detected.wait(timeout)

    def wait_for_change(self, timeout: float = 30) -> tuple[str | None, float | None]:
        """Wait for either ANA notification or connection closure.

        Returns:
            Tuple of (path_taken, timestamp):
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

    def stop(self) -> None:
        """Stop the polling thread."""
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=10)


class MultipathClient:
    """Manages multiple NVMe controller connections with automatic ANA-based path selection.

    This class provides multipath I/O capability for NVMe-oF subsystems by maintaining
    simultaneous connections to multiple controllers (typically active and standby in
    an HA configuration) and automatically selecting the optimal path for I/O operations
    based on ANA (Asymmetric Namespace Access) state.

    Key Features:
    - Connects to multiple controllers simultaneously
    - Automatically selects the OPTIMIZED path for I/O operations
    - Transparently handles path state changes during failover
    - Maintains keep-alive for connection health monitoring

    ANA States:
    - OPTIMIZED: Path is active and preferred for I/O (used by this class)
    - NON_OPTIMIZED: Path is accessible but not preferred
    - INACCESSIBLE: Path cannot access namespaces (post-failover state)

    Usage:
        # Connect to both controllers
        controllers = [(active_ip, port), (standby_ip, port)]
        multipath = MultipathClient(controllers, subsys_nqn)

        # I/O automatically uses OPTIMIZED path
        data = multipath.read_data(nsid=1, lba=0, block_count=1)
        multipath.write_data(nsid=1, lba=0, data=pattern)

        # After failover, automatically switches to new OPTIMIZED path
        data = multipath.read_data(nsid=1, lba=0, block_count=1)  # Uses new active controller

        # Cleanup
        multipath.disconnect_all()

    Thread Safety:
        NOT thread-safe. See "Threading Architecture" overview above for proper
        usage patterns with worker threads.
    """

    def __init__(self, controllers: list[tuple[str, int]], subsystem_nqn: str) -> None:
        """
        Args:
            controllers: [(ip1, port1), (ip2, port2), ...]
            subsystem_nqn: NQN of the subsystem to connect to
        """
        self.clients: dict[str, NVMeoFClient] = {}  # {ip: client}
        for ip, port in controllers:
            # Enable keep-alive for connection health monitoring
            client = NVMeoFClient(ip, subsystem_nqn, port, kato=NVME_KEEPALIVE_MS)
            connect_with_retry(client, ip)
            self.clients[ip] = client

    def get_active_client(self) -> tuple[NVMeoFClient, str]:
        """Return the client connected to OPTIMIZED path."""
        for ip, client in self.clients.items():
            try:
                if is_ana_state_optimized(client):
                    return client, ip
            except Exception as e:
                print(f'[DEBUG] {ip}: Failed to check ANA state: {e}')
                continue
        raise Exception('No OPTIMIZED path found')

    def get_client_by_ip(self, ip: str) -> NVMeoFClient | None:
        """Get specific client by IP."""
        return self.clients.get(ip)

    def read_data(self, nsid: int, lba: int, block_count: int) -> bytes:
        """Read from the currently OPTIMIZED path."""
        client, ip = self.get_active_client()
        return client.read_data(nsid, lba, block_count)

    def write_data(self, nsid: int, lba: int, data: bytes) -> None:
        """Write to the currently OPTIMIZED path."""
        client, ip = self.get_active_client()
        return client.write_data(nsid, lba, data)

    def disconnect_all(self) -> None:
        """Disconnect all controller connections."""
        for client in self.clients.values():
            if client.is_connected:
                client.disconnect()


class IOWorker:
    """Performs continuous background I/O to test behavior during failover.

    Runs in background thread, continuously writing and reading data to verify
    that I/O operations behave correctly during failover transitions. Tracks
    success and error counts to measure failover impact on I/O.

    Key Behaviors:
        - Writes test pattern 'IOWORKER' to LBA 0, reads it back
        - Cycles through all namespaces (1 to namespace_count)
        - Runs at ~10 ops/sec (0.1s sleep between operations)
        - Errors during failover are EXPECTED and tracked
        - With MultipathClient: automatically switches to OPTIMIZED path
        - With NVMeoFClient: errors expected until path becomes OPTIMIZED

    Usage:
        # For ANA mode (multipath)
        multipath = MultipathClient([(active_ip, port), (standby_ip, port)], subsys_nqn)
        io_worker = IOWorker(multipath, namespace_count=3)
        io_worker.start()

        trigger_failover_with_checks(...)

        stats = io_worker.stop()
        print(f"Successes: {stats['successes']}, Errors: {stats['errors']}")
        assert stats['successes'] > 0, "No successful I/O after failover"

        # For single-path testing
        client = NVMeoFClient(ip, subsys_nqn)
        io_worker = IOWorker(client, namespace_count=1)
        # ... same pattern

    Thread Safety:
        See "Threading Architecture" overview above. Manages its own thread and client.
    """

    def __init__(
        self, client: MultipathClient | NVMeoFClient, namespace_count: int
    ) -> None:
        self.client = client
        self.namespace_count = namespace_count
        self.stop_event = threading.Event()
        self.error_count = 0
        self.success_count = 0
        self.errors: list[str] = []
        self.thread: threading.Thread | None = None

    def _worker(self) -> None:
        """Worker thread that performs continuous I/O."""
        data = b'IOWORKER'.ljust(512, b'\x00')
        while not self.stop_event.is_set():
            try:
                # Cycle through namespaces
                nsid = (self.success_count % self.namespace_count) + 1
                self.client.write_data(nsid=nsid, lba=0, data=data)
                read_back = self.client.read_data(nsid=nsid, lba=0, block_count=1)
                assert read_back[:8] == b'IOWORKER'
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

    def start(self) -> None:
        """Start the I/O worker thread."""
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()
        # Let some I/O happen before returning
        time.sleep(1)

    def stop(self) -> dict[str, int | list[str]]:
        """Stop the I/O worker and return statistics."""
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=WORKER_THREAD_JOIN_TIMEOUT)
        return {
            'errors': self.error_count,
            'successes': self.success_count,
            'error_samples': self.errors[:5],  # First 5 errors
        }


class ReconnectingIOWorker:
    """Performs continuous background I/O with automatic reconnection for IP takeover.

    Like IOWorker but designed for IP takeover failover mode where the Virtual IP
    (VIP) moves from one node to another. When failover occurs, the connection to
    the VIP breaks and must be re-established to the new node. This worker handles
    that reconnection automatically.

    Key Differences from IOWorker:
        - Creates and manages its own NVMeoFClient (takes IP, not client)
        - Automatically reconnects on I/O failure
        - Tracks reconnection count in addition to success/error counts
        - Used for IP takeover mode (not ANA mode)

    IP Takeover Scenario:
        1. Initially connected to VIP on Node A
        2. Failover triggered - VIP moves to Node B
        3. Connection to VIP breaks (now points to Node B)
        4. Worker detects I/O failure, reconnects to VIP
        5. Now connected to same VIP but on Node B
        6. I/O resumes successfully

    Expected Behavior:
        - Reconnect count should be >= 1 after failover
        - Some I/O errors during transition are expected
        - Success count should be > 0 after reconnection

    Usage:
        vip = truenas_server.ip  # Virtual IP that moves between nodes

        io_worker = ReconnectingIOWorker(vip, subsys_nqn, namespace_count=3)
        io_worker.start()

        trigger_failover_with_checks(...)  # VIP moves to other node

        stats = io_worker.stop()
        print(f"Reconnects: {stats['reconnects']}, Successes: {stats['successes']}")
        assert stats['reconnects'] >= 1, "Expected reconnection during failover"
        assert stats['successes'] > 0, "No I/O after reconnection"

    Thread Safety:
        See "Threading Architecture" overview above. Manages its own thread and client.
    """

    def __init__(
        self,
        ip: str,
        subsystem_nqn: str,
        namespace_count: int,
        port: int = NVME_DEFAULT_TCP_PORT,
    ) -> None:
        self.ip = ip
        self.subsystem_nqn = subsystem_nqn
        self.namespace_count = namespace_count
        self.port = port
        self.client: NVMeoFClient | None = None
        self.stop_event = threading.Event()
        self.error_count = 0
        self.success_count = 0
        self.reconnect_count = 0
        self.errors: list[str] = []
        self.thread: threading.Thread | None = None

    def _reconnect(self) -> None:
        """Attempt to reconnect to the target."""
        if self.client and self.client.is_connected:
            safe_disconnect(self.client)

        # Try to connect
        self.client = NVMeoFClient(self.ip, self.subsystem_nqn, self.port)
        self.client.connect()
        self.reconnect_count += 1

    def _worker(self) -> None:
        """Worker thread that performs continuous I/O with reconnection."""
        data = b'RECONECT'.ljust(512, b'\x00')

        # Initial connection
        try:
            self._reconnect()
        except Exception as e:
            self.errors.append(f'Initial connect failed: {e}')
            return

        while not self.stop_event.is_set():
            try:
                # Cycle through namespaces
                nsid = (self.success_count % self.namespace_count) + 1
                self.client.write_data(nsid=nsid, lba=0, data=data)
                read_back = self.client.read_data(nsid=nsid, lba=0, block_count=1)
                assert read_back[:8] == b'RECONECT'
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
                        self.errors.append(
                            f'Reconnect attempt {attempt + 1} failed: {reconnect_error}'
                        )
                    # Interruptible sleep - wakes immediately if stop_event set
                    if self.stop_event.wait(timeout=0.1):
                        return

                if not reconnected:
                    self.errors.append('Failed to reconnect after 30 attempts')
                    return

    def start(self) -> None:
        """Start the I/O worker thread."""
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()
        # Let some I/O happen before returning
        time.sleep(1)

    def stop(self) -> dict[str, int | list[str]]:
        """Stop the I/O worker and return statistics."""
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=RECONNECT_WORKER_JOIN_TIMEOUT)

        # Clean up connection
        if self.client and self.client.is_connected:
            safe_disconnect(self.client)

        return {
            'errors': self.error_count,
            'successes': self.success_count,
            'reconnects': self.reconnect_count,
            'error_samples': self.errors[:10],  # First 10 errors
        }
