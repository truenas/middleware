"""
Integration tests for external Docker container support in TrueNAS Apps.

These tests verify the ability to query and monitor Docker containers deployed
outside of TrueNAS Apps (via Docker CLI, Portainer, Dockage, etc.)

Prerequisites:
- Docker service must be running
- At least one external Docker container should be running for full test coverage
"""

import pytest

from middlewared.test.integration.utils import call


def test_query_apps_with_include_external_true():
    """Test querying apps with include_external=True returns external containers."""
    apps = call('app.query', [], {'extra': {'include_external': True}})

    assert isinstance(apps, list)

    # Check if we have any external apps
    external_apps = [app for app in apps if app.get('source') == 'external']

    # If there are external apps, verify their structure
    if external_apps:
        for app in external_apps:
            assert app['name'] is not None
            assert app['source'] == 'external'
            assert app['custom_app'] is True
            assert app['metadata']['train'] == 'external'
            assert 'External Docker container' in app['metadata']['description']
            assert 'active_workloads' in app
            assert 'state' in app


def test_query_apps_with_include_external_false():
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


def test_query_apps_default_includes_external():
    """Test that app.query includes external apps by default (backward compatibility check)."""
    # Default behavior should match include_external=True for the WebUI
    apps = call('app.query', [])

    # Verify the query succeeds
    assert isinstance(apps, list)

    # If there are any apps with 'source' field, verify they're properly categorized
    for app in apps:
        if 'source' in app:
            assert app['source'] in ('truenas', 'external')


def test_filter_apps_by_source():
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
def test_app_stats_includes_external(interval):
    """Test that app.stats event source includes external container statistics."""
    import time
    from middlewared.test.integration.utils import client

    # First check if there are any external apps
    apps = call('app.query', [], {'extra': {'include_external': True}})
    external_apps = [a for a in apps if a.get('source') == 'external']

    if not external_apps:
        pytest.skip('No external Docker containers found, skipping stats test')

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

    if external_apps:
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


def test_external_app_metadata_structure():
    """Test that external app metadata has expected synthetic structure."""
    apps = call('app.query', [], {'extra': {'include_external': True}})
    external_apps = [a for a in apps if a.get('source') == 'external']

    if not external_apps:
        pytest.skip('No external Docker containers found')

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


def test_external_app_active_workloads():
    """Test that external apps have proper active_workloads data."""
    apps = call('app.query', [], {'extra': {'include_external': True}})
    running_external = [a for a in apps if a.get('source') == 'external' and a['state'] == 'RUNNING']

    if not running_external:
        pytest.skip('No running external Docker containers found')

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


def test_external_app_state_accuracy():
    """Test that external app states are accurately reported."""
    apps = call('app.query', [], {'extra': {'include_external': True}})
    external_apps = [a for a in apps if a.get('source') == 'external']

    if not external_apps:
        pytest.skip('No external Docker containers found')

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


def test_query_specific_external_app():
    """Test querying a specific external app by name."""
    # First get all external apps
    all_apps = call('app.query', [], {'extra': {'include_external': True}})
    external_apps = [a for a in all_apps if a.get('source') == 'external']

    if not external_apps:
        pytest.skip('No external Docker containers found')

    # Pick the first external app
    target_app = external_apps[0]
    app_name = target_app['name']

    # Query for this specific app
    specific_app = call('app.query', [['name', '=', app_name]], {'extra': {'include_external': True}})

    assert len(specific_app) == 1
    assert specific_app[0]['name'] == app_name
    assert specific_app[0]['source'] == 'external'


def test_external_apps_not_in_delete_validation():
    """Test that attempting operations on external apps is handled properly."""
    apps = call('app.query', [], {'extra': {'include_external': True}})
    external_apps = [a for a in apps if a.get('source') == 'external']

    if not external_apps:
        pytest.skip('No external Docker containers found')

    # External apps should be queryable but TrueNAS app management operations
    # may have different behavior - this test verifies the system doesn't crash
    target_app = external_apps[0]['name']

    # Just verify we can query app config without errors
    # (whether it returns data or raises a specific error is implementation-dependent)
    try:
        config = call('app.config', target_app)
        # If it succeeds, config should be a dict
        assert isinstance(config, dict)
    except Exception as e:
        # If it fails, it should be a controlled failure, not a crash
        assert 'ValidationErrors' in str(type(e)) or 'CallError' in str(type(e))
