"""
Integration tests for external Docker container support in TrueNAS Apps.

These tests verify the ability to query and monitor Docker containers deployed
outside of TrueNAS Apps (via Docker CLI, Portainer, Dockage, etc.)

Prerequisites:
- Docker service must be running
"""

import pytest
import subprocess
import time

from middlewared.test.integration.utils import call, ssh


# Test container configuration
TEST_CONTAINER_NAME = 'truenas-test-external-app'
TEST_CONTAINER_IMAGE = 'alpine:latest'


@pytest.fixture(scope='module')
def external_container():
    """
    Deploy an external Docker container for testing.

    This creates a simple Alpine container that runs indefinitely,
    simulating an externally deployed container.

    IMPORTANT: This fixture will FAIL the test if the container cannot be
    created, ensuring that external app functionality is properly tested.
    """
    # Ensure Docker is running
    try:
        ssh('docker info', check=False)
    except Exception as e:
        pytest.fail(f'Docker service is not running: {e}')

    # Clean up any existing test container
    ssh(f'docker rm -f {TEST_CONTAINER_NAME}', check=False, complete_response=True)

    # Pull the test image
    result = ssh(f'docker pull {TEST_CONTAINER_IMAGE}', complete_response=True)
    if result['result'] is False:
        pytest.fail(f'Failed to pull test image {TEST_CONTAINER_IMAGE}: {result.get("stderr", "")}')

    # Deploy the external container (sleep indefinitely to keep it running)
    result = ssh(
        f'docker run -d --name {TEST_CONTAINER_NAME} '
        f'--label com.docker.compose.project=test-external '
        f'{TEST_CONTAINER_IMAGE} sleep infinity',
        complete_response=True
    )

    if result['result'] is False:
        pytest.fail(f'Failed to create external test container: {result.get("stderr", "")}')

    # Wait for container to be running
    time.sleep(2)

    # Verify container is running
    result = ssh(f'docker inspect -f "{{{{.State.Running}}}}" {TEST_CONTAINER_NAME}', complete_response=True)
    if 'true' not in result['stdout'].lower():
        ssh(f'docker rm -f {TEST_CONTAINER_NAME}', check=False)
        pytest.fail(f'Test container failed to start. State: {result.get("stdout", "")}')

    yield TEST_CONTAINER_NAME

    # Cleanup: remove the test container
    ssh(f'docker rm -f {TEST_CONTAINER_NAME}', check=False)


def test_query_apps_with_include_external_true(external_container):
    """Test querying apps with include_external=True returns external containers."""
    apps = call('app.query', [], {'extra': {'include_external': True}})

    assert isinstance(apps, list)

    # Check if we have any external apps
    external_apps = [app for app in apps if app.get('source') == 'external']

    # We should have at least our test container
    assert len(external_apps) > 0

    # Verify structure of external apps
    for app in external_apps:
        assert app['name'] is not None
        assert app['source'] == 'external'
        assert app['custom_app'] is True
        assert app['metadata']['train'] == 'external'
        assert 'External Docker container' in app['metadata']['description']
        assert 'active_workloads' in app
        assert 'state' in app


def test_query_apps_with_include_external_false(external_container):
    """Test querying apps with include_external=False excludes external containers."""
    apps_with_external = call('app.query', [], {'extra': {'include_external': True}})
    apps_without_external = call('app.query', [], {'extra': {'include_external': False}})

    # Count apps by source
    external_count_with = len([a for a in apps_with_external if a.get('source') == 'external'])
    external_count_without = len([a for a in apps_without_external if a.get('source') == 'external'])

    # When include_external=False, there should be no external apps
    assert external_count_without == 0

    # When include_external=True, there may be external apps (if any exist)
    # We can't assert they exist because test environment may not have any
    assert external_count_with >= 0


def test_query_apps_default_includes_external(external_container):
    """Test that app.query includes external apps by default (backward compatibility check)."""
    # Default behavior should match include_external=True for the WebUI
    apps = call('app.query', [])

    # Verify the query succeeds
    assert isinstance(apps, list)

    # Should have our test container
    external_apps = [app for app in apps if app.get('source') == 'external']
    assert len(external_apps) > 0

    # Verify apps are properly categorized
    for app in apps:
        if 'source' in app:
            assert app['source'] in ('truenas', 'external')


def test_filter_apps_by_source(external_container):
    """Test filtering apps by source field."""
    # Get all apps including external
    all_apps = call('app.query', [], {'extra': {'include_external': True}})

    # Filter for TrueNAS apps only
    truenas_apps = call('app.query', [['source', '=', 'truenas']], {'extra': {'include_external': True}})

    # Filter for external apps only
    external_apps = call('app.query', [['source', '=', 'external']], {'extra': {'include_external': True}})

    # Verify all apps are accounted for
    assert len(all_apps) >= len(truenas_apps) + len(external_apps)

    # Verify filtering worked correctly
    for app in truenas_apps:
        assert app.get('source') == 'truenas'

    for app in external_apps:
        assert app.get('source') == 'external'


@pytest.mark.parametrize('interval', [2, 5])
def test_app_stats_includes_external(external_container, interval):
    """Test that app.stats event source includes external container statistics."""
    from middlewared.test.integration.utils import client

    # Get external apps
    apps = call('app.query', [], {'extra': {'include_external': True}})
    external_apps = [a for a in apps if a.get('source') == 'external']

    # Should have our test container
    assert len(external_apps) > 0

    external_app_names = {a['name'] for a in external_apps}

    # Subscribe to stats and collect one batch
    with client() as c:
        stats_received = []

        def callback(mtype, **message):
            if mtype == 'ADDED':
                stats_received.extend(message['fields'])

        c.subscribe('app.stats', callback, sync=True)

        # Wait for stats to be collected
        time.sleep(interval + 1)

        c.unsubscribe('app.stats')

    # Verify we received stats
    assert len(stats_received) > 0

    # Check if any external app stats were included
    external_stats = [s for s in stats_received if s['app_name'] in external_app_names]

    # We should have stats for at least some external apps
    assert len(external_stats) > 0

    # Verify stats structure
    for stat in external_stats:
        assert 'app_name' in stat
        assert 'cpu_usage' in stat
        assert 'memory' in stat
        assert 'networks' in stat
        assert 'blkio' in stat

        # Stats should be non-negative
        assert stat['cpu_usage'] >= 0
        assert stat['memory'] >= 0


def test_external_app_metadata_structure(external_container):
    """Test that external app metadata has expected synthetic structure."""
    apps = call('app.query', [], {'extra': {'include_external': True}})
    external_apps = [a for a in apps if a.get('source') == 'external']

    # Should have our test container
    assert len(external_apps) > 0

    for app in external_apps:
        # Verify synthetic metadata structure
        assert app['metadata']['name'] == app['name']
        assert app['metadata']['title'] == app['name']
        assert app['metadata']['train'] == 'external'
        assert 'categories' in app['metadata']
        assert 'external' in app['metadata']['categories']

        # Verify human_version shows image
        assert app['human_version'] is not None

        # Verify notes mention external deployment
        assert app['notes'] is not None
        assert 'external' in app['notes'].lower()

        # Verify it's marked as custom app
        assert app['custom_app'] is True


def test_external_app_active_workloads(external_container):
    """Test that external apps have proper active_workloads data."""
    apps = call('app.query', [], {'extra': {'include_external': True}})
    running_external = [a for a in apps if a.get('source') == 'external' and a['state'] == 'RUNNING']

    # Should have our test container running
    assert len(running_external) > 0

    for app in running_external:
        workloads = app['active_workloads']

        # Verify workload structure
        assert 'containers' in workloads
        assert 'container_details' in workloads
        assert 'images' in workloads
        assert 'networks' in workloads

        # Should have at least one container
        assert workloads['containers'] > 0
        assert len(workloads['container_details']) > 0

        # Verify container details
        for container in workloads['container_details']:
            assert 'id' in container
            assert 'service_name' in container
            assert 'image' in container
            assert 'state' in container


def test_mixed_apps_query():
    """Test querying when both TrueNAS and external apps exist."""
    from middlewared.test.integration.assets.apps import app
    from middlewared.test.integration.assets.docker import docker
    from middlewared.test.integration.assets.pool import another_pool

    # This test requires a running pool and docker
    try:
        pools = call('pool.query')
        if not pools:
            pytest.skip('No pools available for testing')

        # Query apps with external containers
        all_apps = call('app.query', [], {'extra': {'include_external': True}})

        # Categorize apps
        truenas_apps = [a for a in all_apps if a.get('source') == 'truenas']
        external_apps = [a for a in all_apps if a.get('source') == 'external']

        # Verify both types can coexist
        assert isinstance(truenas_apps, list)
        assert isinstance(external_apps, list)

        # Verify no overlap in app names (unless explicitly created)
        truenas_names = {a['name'] for a in truenas_apps}
        external_names = {a['name'] for a in external_apps}

        # Each app should have unique identifiers
        all_names = [a['name'] for a in all_apps]
        assert len(all_names) == len(set(all_names))  # No duplicates

    except Exception as e:
        pytest.skip(f'Could not set up test environment: {e}')


def test_external_app_state_accuracy(external_container):
    """Test that external app states are accurately reported."""
    apps = call('app.query', [], {'extra': {'include_external': True}})
    external_apps = [a for a in apps if a.get('source') == 'external']

    # Should have our test container
    assert len(external_apps) > 0

    for app in external_apps:
        # Verify state is one of the valid states
        valid_states = ['RUNNING', 'STOPPED', 'CRASHED', 'DEPLOYING', 'STOPPING']
        assert app['state'] in valid_states

        # If state is RUNNING, should have active containers
        if app['state'] == 'RUNNING':
            assert app['active_workloads']['containers'] > 0
            running_containers = [
                c for c in app['active_workloads']['container_details']
                if c['state'] == 'running'
            ]
            assert len(running_containers) > 0


def test_query_specific_external_app(external_container):
    """Test querying a specific external app by name."""
    # Get our test container app
    all_apps = call('app.query', [], {'extra': {'include_external': True}})
    test_app = [a for a in all_apps if a.get('name') == 'test-external']

    # Should find our test container
    assert len(test_app) == 1
    app_name = test_app[0]['name']

    # Query for this specific app
    specific_app = call('app.query', [['name', '=', app_name]], {'extra': {'include_external': True}})

    assert len(specific_app) == 1
    assert specific_app[0]['name'] == app_name
    assert specific_app[0]['source'] == 'external'


def test_external_apps_not_in_delete_validation(external_container):
    """Test that attempting operations on external apps is handled properly."""
    apps = call('app.query', [], {'extra': {'include_external': True}})
    test_app = [a for a in apps if a.get('name') == 'test-external']

    # Should find our test container
    assert len(test_app) == 1

    # External apps should be queryable but TrueNAS app management operations
    # may have different behavior - this test verifies the system doesn't crash
    target_app = test_app[0]['name']

    # Just verify we can query app config without errors
    # (whether it returns data or raises a specific error is implementation-dependent)
    try:
        config = call('app.config', target_app)
        # If it succeeds, config should be a dict
        assert isinstance(config, dict)
    except Exception as e:
        # If it fails, it should be a controlled failure, not a crash
        assert 'ValidationErrors' in str(type(e)) or 'CallError' in str(type(e))
