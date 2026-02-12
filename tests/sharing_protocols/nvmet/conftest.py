"""
Pytest configuration and fixtures for NVMe-oF HA tests.

This conftest.py provides module-scoped fixtures that are automatically
discovered by pytest without needing explicit imports in test files.

FIXTURE DEPENDENCY CHAIN:
========================
The fixtures have a carefully ordered dependency chain to ensure correct setup:

1. initialize_node_ips (session-scoped, autouse)
   -> Initializes TrueNAS HA node IP addresses once per test session
   -> Runs automatically before any tests execute

2. fixture_implementation (module-scoped, parametrized: 'kernel', 'spdk')
   -> Sets the NVMet target implementation backend
   -> Each test module runs twice: once with kernel, once with SPDK

3. fixture_nvmet_running (module-scoped, depends on fixture_implementation)
   -> Starts the NVMet service with the configured implementation
   -> Service must be running before any configuration changes

4. fixture_failover_mode (module-scoped, parametrized: 'ana', 'ip_takeover')
   -> Depends on fixture_nvmet_running (service must start BEFORE ANA config)
   -> For 'ana': enables ANA mode with propagation delays
   -> For 'ip_takeover': uses default configuration (ANA off)
   -> Each test module runs 2x2=4 times (kernel-ana, kernel-ip, spdk-ana, spdk-ip)

5. configured_subsystem* fixtures (module-scoped, depend on fixture_failover_mode)
   -> Create NVMe subsystems and namespaces for testing
   -> Must run AFTER ANA configuration is complete
   -> Setup is identical for both modes (system handles multi-node automatically)

6. restore_original_master (module-scoped, autouse)
   -> Ensures the original master node is restored after all tests complete
   -> Runs automatically during test teardown

CRITICAL ORDERING REQUIREMENTS:
- Service must be running before ANA configuration can be applied
- ANA configuration must be complete before subsystems are created
- Both requirements ensure predictable failover behavior during tests

The dependency chain ensures each test runs with the correct combination of:
- Implementation backend (kernel or SPDK)
- Failover mode (ANA or IP takeover)
- Properly initialized subsystems and namespaces
"""

import time
from typing import Any, Iterator

import pytest

from middlewared.test.integration.utils import call
from middlewared.test.integration.utils.failover import do_failover
from middlewared.test.integration.utils.ha import settle_ha

from assets.websocket.service import ensure_service_enabled, ensure_service_started
from middlewared.test.integration.assets.nvmet import nvmet_ana

from middlewared.test.integration.utils.client import (
    truenas_server,
    host as init_truenas_server,
)

from nvmet_ha_utils import double_settle_ha, nvmet_implementation, SERVICE_NAME


@pytest.fixture(scope='session', autouse=True)
def initialize_node_ips() -> None:
    """Initialize TrueNAS HA node IP addresses once per test session.

    This autouse fixture ensures node IPs (nodea_ip, nodeb_ip) are initialized
    before any tests run, eliminating the need for repeated initialization checks
    in individual test fixtures.
    """
    if truenas_server.nodea_ip is None:
        init_truenas_server()


@pytest.fixture(scope='module')
def fixture_nvmet_running(fixture_implementation: str) -> Iterator[str]:
    """Ensure NVMet service is running with the configured implementation.

    Starts the service after implementation is set, enabling tests to proceed
    with the correct backend (kernel or SPDK).
    """
    with ensure_service_enabled(SERVICE_NAME):
        with ensure_service_started(SERVICE_NAME, 3):
            yield fixture_implementation


@pytest.fixture(params=['ana', 'ip_takeover'], scope='module')
def fixture_failover_mode(request: Any, fixture_nvmet_running: str) -> Iterator[str]:
    """Parametrize failover mode (ANA vs IP takeover).

    IMPORTANT: Takes fixture_nvmet_running as parameter to ensure service is
    started BEFORE this fixture configures ANA settings. This dependency ensures
    proper ordering: implementation -> service start -> ANA configuration.
    """
    if request.param == 'ana':
        with nvmet_ana(True):
            # Give ANA configuration time to propagate to both nodes
            print('[FIXTURE] Sleeping 2s for ANA mode initialization...')
            time.sleep(2)
            yield request.param
        # After ANA disabled (context exit), give time for change to propagate
        print('[FIXTURE] Sleeping 2s after ANA mode teardown...')
        time.sleep(2)
    else:
        # IP takeover - no configuration change, just use default (ANA off)
        yield request.param


@pytest.fixture(scope='module', autouse=True)
def restore_original_master() -> Iterator[None]:
    """Ensure the original master node is restored after all tests complete.

    Records which node is active on entry, then restores it on exit if needed.
    This ensures the test module leaves the system in the same state it found it.
    """
    # Entry: record which node is currently active
    orig_master_node = call('failover.node')
    print(f'[FIXTURE] Original master node at module start: {orig_master_node}')

    yield

    # Exit: restore if needed
    current_master_node = call('failover.node')
    if current_master_node != orig_master_node:
        print(
            f'\n[FIXTURE] Restoring master to original node {orig_master_node} (currently {current_master_node})...'
        )

        # Ensure HA is settled and ready for failover
        settle_ha()

        # Perform failover back to original master
        do_failover(settle=True, abusive=False)

        # Double settle for full stabilization
        double_settle_ha()

        # Verify restoration succeeded
        final_master_node = call('failover.node')
        if final_master_node == orig_master_node:
            print(f'[FIXTURE] Successfully restored master to {orig_master_node}')
        else:
            print(
                '[FIXTURE] WARNING: Failed to restore original master: '
                f'expected {orig_master_node}, got {final_master_node}'
            )
    else:
        print(
            f'\n[FIXTURE] Master node unchanged ({orig_master_node}), no restoration needed'
        )


@pytest.fixture(params=['kernel', 'spdk'], scope='module')
def fixture_implementation(request: Any) -> Iterator[str]:
    """Set NVMet implementation (kernel or SPDK) before service starts."""
    with nvmet_implementation(request.param):
        yield request.param
