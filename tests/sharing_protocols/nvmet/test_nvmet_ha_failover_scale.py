"""
NVMe-oF HA Large-Scale Failover Testing

Tests failover with many subsystems/namespaces:
- SCALE_SINGLE_NS_SUBSYSTEMS subsystems with 1 namespace each (50)
- 1 subsystem with SCALE_MULTI_NS_COUNT namespaces (20)
- Total: 51 subsystems, 70 namespaces

Verifies:
- Unique data patterns per namespace survive failover
- Failover timing (must complete within MAX_FAILOVER_TIME seconds)
- I/O integrity across all namespaces after failover

Test matrix (4 tests):
- All implementation/mode combinations
- kernel-ana, kernel-ip_takeover, spdk-ana, spdk-ip_takeover
- 2 implementations x 2 modes = 4 tests
"""

import contextlib
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Iterator

import pytest

from nvmeof_client import NVMeoFClient
from assets.websocket.pool import zvol
from auto_config import ha, pool_name
from middlewared.test.integration.assets.nvmet import (
    nvmet_namespace,
    nvmet_port,
    nvmet_port_subsys,
    nvmet_subsys,
)
from middlewared.test.integration.utils import call
from middlewared.test.integration.utils.client import truenas_server

# Import shared utilities
from nvmet_ha_utils import (
    SERVICE_NAME,
    MAX_FAILOVER_TIME,
    CONNECTION_RETRY_DELAY,
    PATH_WAIT_MAX_ATTEMPTS,
    RESOURCE_CLEANUP_SLEEP,
    connect_with_retry,
    get_node_ips,
    safe_disconnect,
    print_test_config,
    trigger_failover_with_checks,
    wait_for_ana_path_optimized,
    wait_for_ip_takeover,
    double_settle_ha,
)

pytestmark = pytest.mark.skipif(not ha, reason='Failover tests require HA')

# ============================================================================
# Constants
# ============================================================================

# Scale test configuration
SCALE_SINGLE_NS_SUBSYSTEMS = 50  # Number of subsystems with 1 namespace each
SCALE_MULTI_NS_COUNT = 20  # Number of namespaces in multi-namespace subsystem
SCALE_ZVOL_MB = 20  # Size of each ZVOL in MB (smaller for faster testing)
# Total scale: 51 subsystems, 70 namespaces

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(scope='module')
def many_zvols_scale() -> Iterator[list[str]]:
    """Create ZVOLs for scale testing."""
    total_zvols = SCALE_SINGLE_NS_SUBSYSTEMS + SCALE_MULTI_NS_COUNT
    zvol_names = []

    # Create all ZVOLs using ExitStack
    print(f'[FIXTURE] Creating {total_zvols} ZVOLs for scale testing...')
    with contextlib.ExitStack() as es:
        for i in range(total_zvols):
            zvol_name = f'ha_scale_{i}'
            zvol_names.append(zvol_name)
            es.enter_context(zvol(zvol_name, SCALE_ZVOL_MB, pool_name))
        print(f'[FIXTURE] {total_zvols} ZVOLs created')
        yield zvol_names
        print(f'[FIXTURE] About to destroy {total_zvols} ZVOLs...')
    print(f'[FIXTURE] {total_zvols} ZVOLs destroyed')


@pytest.fixture(scope='module')
def configured_subsystems_scale(
    many_zvols_scale: list[str],
    fixture_failover_mode: str,
) -> Iterator[list[dict[str, Any]]]:
    """Set up multiple subsystems with namespaces for scale testing.

    Returns:
        List of dicts with keys: 'subnqn', 'namespace_count', 'nsids'
    """
    subsystems = []
    zvol_index = 0

    # Create port once for all subsystems
    with nvmet_port(truenas_server.ip) as port:
        with contextlib.ExitStack() as stack:
            # Create single-namespace subsystems
            for i in range(SCALE_SINGLE_NS_SUBSYSTEMS):
                subsys_name = f'scale_single_{i}'
                subsys = stack.enter_context(
                    nvmet_subsys(subsys_name, allow_any_host=True)
                )
                stack.enter_context(nvmet_port_subsys(subsys['id'], port['id']))

                # Add one namespace
                zvol_name = many_zvols_scale[zvol_index]
                zvol_index += 1
                zvol_path = f'zvol/{pool_name}/{zvol_name}'
                ns = stack.enter_context(nvmet_namespace(subsys['id'], zvol_path))

                subsystems.append(
                    {
                        'subnqn': subsys['subnqn'],
                        'namespace_count': 1,
                        'nsids': [ns['nsid']],
                    }
                )

            # Create multi-namespace subsystem
            subsys_name = 'scale_multi'
            subsys = stack.enter_context(nvmet_subsys(subsys_name, allow_any_host=True))
            stack.enter_context(nvmet_port_subsys(subsys['id'], port['id']))

            nsids = []
            for j in range(SCALE_MULTI_NS_COUNT):
                zvol_name = many_zvols_scale[zvol_index]
                zvol_index += 1
                zvol_path = f'zvol/{pool_name}/{zvol_name}'
                ns = stack.enter_context(nvmet_namespace(subsys['id'], zvol_path))
                nsids.append(ns['nsid'])

            subsystems.append(
                {
                    'subnqn': subsys['subnqn'],
                    'namespace_count': SCALE_MULTI_NS_COUNT,
                    'nsids': nsids,
                }
            )

            # Double settle pattern for stability
            double_settle_ha()

            print(
                f'\n[SCALE] Created {len(subsystems)} subsystems with '
                f'{sum(s["namespace_count"] for s in subsystems)} total namespaces'
            )

            yield subsystems

            # Cleanup happens via context managers
            print(
                '[FIXTURE] Scale test teardown - namespaces/subsystems being destroyed...'
            )

    # After all context managers have exited (namespaces/subsystems destroyed)
    print('[FIXTURE] Namespaces/subsystems destroyed, checking service state...')

    # Verify service state before proceeding
    service_state = call('service.query', [['service', '=', SERVICE_NAME]])[0]
    print(f"[FIXTURE] Service '{SERVICE_NAME}' state: {service_state['state']}")

    # Sleep to allow kernel/SPDK to release ZVOL references
    print('[FIXTURE] Sleeping 15s for backend to release ZVOL references...')
    time.sleep(RESOURCE_CLEANUP_SLEEP)

    print(
        '[FIXTURE] About to exit configured_subsystems_scale (ZVOLs will be destroyed next)'
    )


# ============================================================================
# Helper Functions
# ============================================================================


def connect_and_write_pattern(
    subsys_info: dict[str, Any],
    subsys_index: int,
    connect_ip: str,
    implementation: str,
    failover_mode: str,
) -> tuple[str, list[tuple[int, bytes]]]:
    """Connect to subsystem, write unique patterns to ALL namespaces, and disconnect immediately."""
    subsys_nqn = subsys_info['subnqn']
    client = None
    try:
        client = NVMeoFClient(connect_ip, subsys_nqn)
        connect_with_retry(client, connect_ip)

        # Write unique pattern to EVERY namespace in this subsystem
        patterns = []
        for nsid in subsys_info['nsids']:
            # Create unique pattern: test params + subsystem index + namespace ID + subsystem NQN
            pattern_str = (
                f'SCALE_{implementation}_{failover_mode}_'
                f'SUBSYS_{subsys_index}_NSID_{nsid}_{subsys_nqn}'
            )
            pattern = pattern_str.encode().ljust(512, b'\0')
            client.write_data(nsid=nsid, lba=0, data=pattern)
            patterns.append((nsid, pattern))

        # flush to ensure data reaches stable storage
        for nsid in subsys_info['nsids']:
            client.flush_namespace(nsid=nsid)

        print(
            f'  [OK] Connected to {subsys_nqn} ({subsys_info["namespace_count"]} namespaces)'
        )
        return (subsys_nqn, patterns)
    except Exception as e:
        raise AssertionError(f'Failed to connect/write to {subsys_nqn}: {e}')
    finally:
        # Disconnect immediately after writing patterns
        safe_disconnect(client)


def verify_pattern(
    subsys_nqn: str, nsid: int, expected_pattern: bytes, verify_ip: str
) -> tuple[str, int, bool, str | None]:
    """Reconnect to subsystem on new controller and verify unique pattern for specific namespace."""
    client = None
    try:
        client = NVMeoFClient(verify_ip, subsys_nqn)
        connect_with_retry(client, verify_ip, max_attempts=PATH_WAIT_MAX_ATTEMPTS)

        # Retry read operation in case namespace isn't ready for I/O yet
        max_read_attempts = PATH_WAIT_MAX_ATTEMPTS
        data = None
        for attempt in range(max_read_attempts):
            try:
                data = client.read_data(nsid=nsid, lba=0, block_count=1)
                break  # Success
            except Exception:
                if attempt < max_read_attempts - 1:
                    time.sleep(CONNECTION_RETRY_DELAY)
                else:
                    raise  # Final attempt failed, re-raise exception

        # Verify pattern matches
        if data != expected_pattern:
            raise AssertionError(
                f'Data pattern mismatch for {subsys_nqn} nsid={nsid}. '
                f'Expected pattern starts with: {expected_pattern[:50]}, '
                f'Got: {data[:50]}'
            )

        print(
            f'  [OK] {subsys_nqn} nsid={nsid} - I/O verified and data pattern matched'
        )
        return (subsys_nqn, nsid, True, None)
    except Exception as e:
        return (subsys_nqn, nsid, False, str(e))
    finally:
        # Always disconnect, even on error
        safe_disconnect(client)


# ============================================================================
# Test Functions
# ============================================================================


@pytest.mark.timeout(
    900
)  # 15 minutes for large-scale tests (70 ZVOLs + test + cleanup)
def test_failover_scale(
    fixture_nvmet_running: str,
    fixture_failover_mode: str,
    configured_subsystems_scale: list[dict[str, Any]],
) -> None:
    """Test failover with multiple subsystems/namespaces.

    Tests 4 combinations (runs by default):
    - All implementation/mode combinations
    - 2 implementations x 2 modes = 4 tests
    """
    # ========================================================================
    # SETUP: Initialize test configuration and determine IPs
    # ========================================================================
    # - Get implementation and failover mode from fixtures
    # - Print test configuration (subsystems, namespaces, mode)
    # - Determine node IPs and select connect_ip based on mode

    implementation = fixture_nvmet_running
    failover_mode = fixture_failover_mode

    total_namespaces = sum(s['namespace_count'] for s in configured_subsystems_scale)

    print_test_config(
        'Scale Test Configuration',
        Implementation=implementation,
        Mode=failover_mode,
        Subsystems=len(configured_subsystems_scale),
        Total_Namespaces=total_namespaces,
    )

    orig_master_node, orig_active_ip, orig_standby_ip = get_node_ips()

    # For IP takeover mode, always use the VIP
    # For ANA mode, use per-node IPs
    if failover_mode == 'ip_takeover':
        vip = truenas_server.ip
        connect_ip = vip
        print(f'Active node: {orig_master_node}, VIP: {vip}')
    else:
        connect_ip = orig_active_ip
        print(
            f'Active node: {orig_master_node}, Active IP: {orig_active_ip}, Standby IP: {orig_standby_ip}'
        )

    # ========================================================================
    # PRE-FAILOVER: Write unique patterns to all namespaces
    # ========================================================================
    # - Connect to all subsystems in parallel (ThreadPoolExecutor)
    # - Write unique test pattern to each namespace
    # - Flush to ensure data reaches stable storage
    # - Disconnect immediately (don't hold connections during failover)

    print('\n[SCALE] Pre-failover: Connecting to all subsystems in parallel...')

    # Use ThreadPoolExecutor for parallel connections (max 10 workers to avoid overwhelming target)
    all_patterns = []  # List of (subsys_nqn, nsid, pattern) tuples
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [
            executor.submit(
                connect_and_write_pattern,
                subsys,
                i,
                connect_ip,
                implementation,
                failover_mode,
            )
            for i, subsys in enumerate(configured_subsystems_scale)
        ]

        # Collect results
        for future in futures:
            subsys_nqn, ns_patterns = future.result()
            # Flatten namespace patterns into single list
            for nsid, pattern in ns_patterns:
                all_patterns.append((subsys_nqn, nsid, pattern))

    num_subsystems = len(configured_subsystems_scale)
    print(
        f'[SCALE] All {num_subsystems} subsystems had {len(all_patterns)} namespace patterns '
        f'written (and disconnected)'
    )

    # ========================================================================
    # FAILOVER: Trigger failover event
    # ========================================================================

    print('\n[SCALE] Triggering failover...')
    failover_start_time = trigger_failover_with_checks('NVMe-oF scale test')

    # ========================================================================
    # WAIT FOR ACCESSIBLE: New controller becomes ready for I/O
    # ========================================================================
    # - For ANA mode: wait for path to become OPTIMIZED (not INACCESSIBLE)
    # - For IP takeover: wait for VIP to be accessible on new node
    # - Verify failover time is within acceptable limits
    # Note: Pre-failover connections already disconnected after writing patterns

    print('[SCALE] Waiting for new active controller to become accessible...')

    if failover_mode == 'ana':
        path_accessible_time = wait_for_ana_path_optimized(
            orig_standby_ip,
            configured_subsystems_scale[0]['subnqn'],
            failover_start_time,
        )
    else:
        path_accessible_time = wait_for_ip_takeover(
            vip, configured_subsystems_scale[0]['subnqn'], failover_start_time
        )

    time_to_accessible = path_accessible_time - failover_start_time

    # Verify failover time is within acceptable limits
    if time_to_accessible > MAX_FAILOVER_TIME:
        raise AssertionError(
            f'Failover time {time_to_accessible:.2f}s exceeds maximum acceptable time of {MAX_FAILOVER_TIME}s'
        )

    # ========================================================================
    # VERIFY I/O & DATA: Check all namespaces on new controller
    # ========================================================================
    # - Determine verify_ip (VIP for IP takeover, orig_standby_ip for ANA)
    # - Reconnect to all subsystems in parallel
    # - Read and verify unique patterns match what was written pre-failover
    # - Collect any failures for reporting

    verify_ip = vip if failover_mode == 'ip_takeover' else orig_standby_ip

    print(
        f'\n[SCALE] Verifying I/O and data patterns on all {len(all_patterns)} namespaces in parallel...'
    )

    # Use ThreadPoolExecutor for parallel verification of ALL namespaces
    failed_namespaces = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [
            executor.submit(verify_pattern, subsys_nqn, nsid, pattern, verify_ip)
            for subsys_nqn, nsid, pattern in all_patterns
        ]

        # Collect results
        for future in futures:
            subsys_nqn, nsid, success, error = future.result()
            if not success:
                print(f'  [FAIL] {subsys_nqn} nsid={nsid} FAILED: {error}')
                failed_namespaces.append((subsys_nqn, nsid, error))

    io_verified_time = time.time()
    time_to_io = io_verified_time - path_accessible_time
    total_time = io_verified_time - failover_start_time

    # ========================================================================
    # TIMING SUMMARY & RESULTS: Report performance metrics
    # ========================================================================

    print('\n[SCALE] Timing Summary:')
    print(f'  Failover trigger -> Path accessible: {time_to_accessible:.2f}s')
    print(f'  Path accessible -> All I/O verified: {time_to_io:.2f}s')
    print(f'  Total time: {total_time:.2f}s')
    print(f'[SCALE] Subsystems tested: {num_subsystems}')
    print(f'[SCALE] Namespaces tested: {len(all_patterns)}')

    if failed_namespaces:
        raise AssertionError(
            f'Failover failed for {len(failed_namespaces)} namespaces: {failed_namespaces}'
        )

    print(
        f'[SCALE] [OK] All {num_subsystems} subsystems ({len(all_patterns)} namespaces) '
        'verified on new controller'
    )

    # ========================================================================
    # SETTLE: Wait for HA to reach steady state
    # ========================================================================
    # Note: Not part of client-visible timing

    print('\n[SCALE] Waiting for HA to reach steady state...')
    double_settle_ha()
