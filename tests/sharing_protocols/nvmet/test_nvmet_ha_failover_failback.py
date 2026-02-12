"""
NVMe-oF HA Failover + Failback Cycle Testing

Tests the complete HA cycle:
- Failover: active node -> standby node
- Failback: standby node -> original active node
- Verifies data integrity survives complete cycle back to original node

Does not assume which node starts active - handles either node.

Test coverage: 2 implementations x 2 modes = 4 tests (always run)
"""

import time
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
    ZVOL_MB,
    MAX_FAILOVER_TIME,
    HA_SETTLE_SLEEP,
    connect_with_retry,
    get_node_ips,
    print_test_config,
    trigger_failover_with_checks,
    wait_for_ana_path_optimized,
    wait_for_ip_takeover,
    double_settle_ha,
)

pytestmark = pytest.mark.skipif(not ha, reason='Failover tests require HA')

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(scope='module')
def single_zvol_failback() -> Iterator[str]:
    """Create single ZVOL for failback testing."""
    with zvol('ha_failback', ZVOL_MB, pool_name):
        yield 'ha_failback'


@pytest.fixture(scope='module')
def configured_subsystem_failback(
    single_zvol_failback: str,
    fixture_failover_mode: str,
) -> Iterator[dict[str, Any]]:
    """Set up single subsystem with one namespace for failback testing."""
    subsys_name = 'failback_test'
    zvol_path = f'zvol/{pool_name}/{single_zvol_failback}'

    with nvmet_port(truenas_server.ip) as port:
        with nvmet_subsys(subsys_name, allow_any_host=True) as subsys:
            with nvmet_port_subsys(subsys['id'], port['id']):
                with nvmet_namespace(subsys['id'], zvol_path) as ns:
                    # Double settle pattern for stability
                    double_settle_ha()

                    yield {'subnqn': subsys['subnqn'], 'nsid': ns['nsid']}

    # Cleanup
    time.sleep(HA_SETTLE_SLEEP)


# ============================================================================
# Test Functions
# ============================================================================


def test_failover_and_failback(
    fixture_nvmet_running: str,
    fixture_failover_mode: str,
    configured_subsystem_failback: dict[str, Any],
) -> None:
    """Test failover followed by failback.

    Flow:
    1. Determine currently active node (A or B)
    2. Write data on active node
    3. Failover: active -> standby
    4. Verify data on new active node (former standby)
    5. Failback: current active -> original active
    6. Verify data on original active node
    """
    # ========================================================================
    # SETUP: Initialize test configuration and determine IPs
    # ========================================================================
    # - Get implementation and failover mode from fixtures
    # - Print test configuration
    # - Determine active/standby node IPs and select connect_ip

    implementation = fixture_nvmet_running
    failover_mode = fixture_failover_mode
    subsys_nqn = configured_subsystem_failback['subnqn']
    nsid = configured_subsystem_failback['nsid']

    print_test_config(
        'Failback Test Configuration',
        Implementation=implementation,
        Mode=failover_mode,
        Pattern='failover -> failback',
    )

    orig_master_node, orig_active_ip, orig_standby_ip = get_node_ips()

    # For IP takeover mode, use VIP
    if failover_mode == 'ip_takeover':
        vip = truenas_server.ip
        initial_connect_ip = vip
    else:
        initial_connect_ip = orig_active_ip

    print(f'\n[FAILBACK] Currently active node: {orig_master_node}')
    print(f'[FAILBACK] Active IP: {orig_active_ip}, Standby IP: {orig_standby_ip}')

    # ========================================================================
    # PHASE 1: Write initial data pattern on active node
    # ========================================================================
    # - Create unique test pattern
    # - Connect to active node (orig_active_ip or VIP)
    # - Write pattern and flush to stable storage
    # - Disconnect (data should survive failover)

    print('\n[FAILBACK] Phase 1: Writing initial data pattern on active node...')
    pattern1 = f'FAILBACK_{implementation}_{failover_mode}_INITIAL'.encode().ljust(
        512, b'\0'
    )

    client = NVMeoFClient(initial_connect_ip, subsys_nqn)
    connect_with_retry(client, initial_connect_ip)
    client.write_data(nsid=nsid, lba=0, data=pattern1)
    client.flush_namespace(nsid=nsid)  # Ensure data survives failover
    client.disconnect()
    print('[FAILBACK] Initial data written and connection closed')

    # ========================================================================
    # PHASE 2: Failover (active -> standby)
    # ========================================================================
    # - Trigger failover to move from orig_master_node to standby
    # - Wait for standby node to become accessible
    # - Verify failover timing is within limits
    # - Reconnect and verify data survived failover
    # - Verify active node changed
    # - Settle HA before proceeding to failback

    print(f'\n[FAILBACK] Triggering failover ({orig_master_node} -> standby)...')
    failover_start = trigger_failover_with_checks('NVMe-oF failback test - failover')

    # Wait for standby node to become accessible as new active
    print('[FAILBACK] Waiting for standby node to become new active controller...')
    if failover_mode == 'ana':
        path_accessible_time = wait_for_ana_path_optimized(
            orig_standby_ip, subsys_nqn, failover_start
        )
    else:
        path_accessible_time = wait_for_ip_takeover(vip, subsys_nqn, failover_start)

    # Check failover timing
    time_to_accessible = path_accessible_time - failover_start
    if time_to_accessible > MAX_FAILOVER_TIME:
        raise AssertionError(
            f'Failover time {time_to_accessible:.2f}s exceeds maximum acceptable time of {MAX_FAILOVER_TIME}s'
        )
    print(
        f'[FAILBACK] Failover completed in {time_to_accessible:.2f}s (within {MAX_FAILOVER_TIME}s limit)'
    )

    # Verify data on new active node (former standby)
    print('[FAILBACK] Verifying data on new active controller (former standby)...')
    verify_ip = vip if failover_mode == 'ip_takeover' else orig_standby_ip
    client = NVMeoFClient(verify_ip, subsys_nqn)
    connect_with_retry(client, verify_ip)
    data = client.read_data(nsid=nsid, lba=0, block_count=1)
    if data != pattern1:
        raise AssertionError('Data pattern mismatch after first failover')
    client.disconnect()
    print('[FAILBACK] [OK] Data verified on new active controller')

    new_master_node = call('failover.node')
    assert new_master_node != orig_master_node, (
        f'Failover failed: still on {orig_master_node}'
    )
    print(f'[FAILBACK] New active node: {new_master_node}')

    # Wait for HA to stabilize before attempting failback
    print('\n[FAILBACK] Waiting for HA to stabilize after failover...')
    double_settle_ha()
    print('[FAILBACK] HA stabilized, ready for failback')

    # ========================================================================
    # PHASE 3: Failback (return to original active node)
    # ========================================================================
    # - Trigger failback to return from new_master_node to orig_master_node
    # - Wait for original active node to become accessible
    # - Verify failback timing is within limits
    # - Reconnect and verify data still intact
    # - Verify we're back on orig_master_node

    print(
        f'\n[FAILBACK] Triggering failback ({new_master_node} -> {orig_master_node})...'
    )
    failback_start = trigger_failover_with_checks('NVMe-oF failback test - failback')

    # Wait for original active node to become accessible again
    print('[FAILBACK] Waiting for original active node to become accessible...')
    if failover_mode == 'ana':
        path_accessible_time = wait_for_ana_path_optimized(
            orig_active_ip, subsys_nqn, failback_start
        )
    else:
        path_accessible_time = wait_for_ip_takeover(vip, subsys_nqn, failback_start)

    # Check failback timing
    time_to_accessible = path_accessible_time - failback_start
    if time_to_accessible > MAX_FAILOVER_TIME:
        raise AssertionError(
            f'Failback time {time_to_accessible:.2f}s exceeds maximum acceptable time '
            f'of {MAX_FAILOVER_TIME}s'
        )
    print(
        f'[FAILBACK] Failback completed in {time_to_accessible:.2f}s '
        f'(within {MAX_FAILOVER_TIME}s limit)'
    )

    # Verify data back on original active node
    print('[FAILBACK] Verifying data on original active controller...')
    verify_ip = vip if failover_mode == 'ip_takeover' else orig_active_ip
    client = NVMeoFClient(verify_ip, subsys_nqn)
    connect_with_retry(client, verify_ip)
    data = client.read_data(nsid=nsid, lba=0, block_count=1)
    if data != pattern1:
        raise AssertionError('Data pattern mismatch after failback')
    client.disconnect()
    print('[FAILBACK] [OK] Data verified on original active controller')

    final_master_node = call('failover.node')
    assert final_master_node == orig_master_node, (
        f'Failback incomplete: expected {orig_master_node}, got {final_master_node}'
    )

    print(
        f'[FAILBACK] [OK] Complete cycle verified: {orig_master_node} -> {new_master_node} -> '
        f'{orig_master_node}'
    )

    # ========================================================================
    # SETTLE: Final HA stabilization
    # ========================================================================

    print('\n[FAILBACK] Waiting for HA to stabilize...')
    double_settle_ha()
