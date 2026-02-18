"""End-to-end tests for the zfs.tier plugin.

Requires:
  - At least 2 unused disks (data + special vdev)
  - TrueNAS Enterprise license (zfs.tier.update requires it)
"""
import errno
import json
import pprint
import time
from unittest.mock import ANY

import pytest

from truenas_api_client import ValidationErrors
from middlewared.test.integration.assets.pool import another_pool, dataset
from middlewared.test.integration.utils import call, client, ssh


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _wait_for_job_status(tier_job_id, desired_statuses, timeout=30, interval=1):
    """Poll rewrite_job_status until it reaches one of the desired_statuses."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status = call('zfs.tier.rewrite_job_status', {'tier_job_id': tier_job_id})['status']
        if status in desired_statuses:
            return status
        time.sleep(interval)
    raise TimeoutError(
        f'{tier_job_id!r} did not reach {desired_statuses} within {timeout}s '
        f'(last status: {status!r})'
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope='module')
def tier_pool():
    unused = call('disk.get_unused')
    if len(unused) < 2:
        pytest.skip('Need at least 2 unused disks for data + special vdev')

    with another_pool({
        'topology': {
            'data':    [{'type': 'STRIPE', 'disks': [unused[0]['name']]}],
            'special': [{'type': 'STRIPE', 'disks': [unused[1]['name']]}],
        },
        'allow_duplicate_serials': True,
    }) as pool:
        if not call('system.is_enterprise'):
            pytest.skip('ZFS tiering requires an Enterprise license')

        original_config = call('zfs.tier.config')
        call('zfs.tier.update', {'enabled': True})
        try:
            yield pool
        finally:
            call('zfs.tier.update', {
                'enabled': original_config['enabled'],
                'max_concurrent_jobs': original_config['max_concurrent_jobs'],
                'min_available_space': original_config['min_available_space'],
            })


@pytest.fixture()
def tier_ds(tier_pool):
    """Fresh dataset on the tier pool, cleaned up after each test."""
    ds_name = f"{tier_pool['name']}/tier_test_{int(time.monotonic() * 1000)}"
    call('pool.dataset.create', {'name': ds_name})
    try:
        yield ds_name
    finally:
        call('pool.dataset.delete', ds_name, {'recursive': True})


# ---------------------------------------------------------------------------
# Config tests
# ---------------------------------------------------------------------------

def test_config_fields():
    """zfs.tier.config returns the expected schema."""
    config = call('zfs.tier.config')
    assert isinstance(config['id'], int)
    assert isinstance(config['enabled'], bool)
    assert isinstance(config['max_concurrent_jobs'], int)
    assert isinstance(config['min_available_space'], int)
    assert 1 <= config['max_concurrent_jobs'] <= 10
    assert config['min_available_space'] >= 0


def test_config_update_max_concurrent_jobs(tier_pool):
    original = call('zfs.tier.config')['max_concurrent_jobs']
    new_val = 5 if original != 5 else 3
    try:
        result = call('zfs.tier.update', {'max_concurrent_jobs': new_val})
        assert result['max_concurrent_jobs'] == new_val
        assert call('zfs.tier.config')['max_concurrent_jobs'] == new_val
    finally:
        call('zfs.tier.update', {'max_concurrent_jobs': original})


def test_config_update_min_available_space(tier_pool):
    original = call('zfs.tier.config')['min_available_space']
    new_val = 10
    try:
        result = call('zfs.tier.update', {'min_available_space': new_val})
        assert result['min_available_space'] == new_val
        assert call('zfs.tier.config')['min_available_space'] == new_val
    finally:
        call('zfs.tier.update', {'min_available_space': original})


# ---------------------------------------------------------------------------
# dataset_set_tier — happy path
# ---------------------------------------------------------------------------

def test_dataset_set_tier_performance(tier_ds):
    result = call('zfs.tier.dataset_set_tier', {
        'dataset_name': tier_ds,
        'tier_type': 'PERFORMANCE',
    })
    assert result['tier_type'] == 'PERFORMANCE'
    assert result['tier_job'] is None

    # Verify the ZFS property was actually set (16 MiB)
    props = call('zfs.resource.query', {'paths': [tier_ds], 'properties': ['special_small_blocks']})
    assert props[0]['properties']['special_small_blocks']['value'] == 16 * 1024 * 1024


def test_dataset_set_tier_regular(tier_ds):
    # Set PERFORMANCE first, then revert to REGULAR
    call('zfs.tier.dataset_set_tier', {'dataset_name': tier_ds, 'tier_type': 'PERFORMANCE'})

    result = call('zfs.tier.dataset_set_tier', {
        'dataset_name': tier_ds,
        'tier_type': 'REGULAR',
    })
    assert result['tier_type'] == 'REGULAR'
    assert result['tier_job'] is None

    props = call('zfs.resource.query', {'paths': [tier_ds], 'properties': ['special_small_blocks']})
    assert props[0]['properties']['special_small_blocks']['value'] == 0


def test_dataset_set_tier_with_migration(tier_ds):
    # Populate with some data so the rewrite job has work to do
    ssh(f'dd if=/dev/urandom of=/mnt/{tier_ds}/testfile bs=4k count=64 2>/dev/null')

    with client() as c:
        events = []
        c.subscribe('zfs.tier.rewrite_job_query', lambda t, **m: events.append((t, m)), sync=True)

        result = c.call('zfs.tier.dataset_set_tier', {
            'dataset_name': tier_ds,
            'tier_type': 'PERFORMANCE',
            'move_existing_data': True,
        })

    assert result['tier_type'] == 'PERFORMANCE'
    assert result['tier_job'] is not None
    assert result['tier_job']['dataset_name'] == tier_ds
    assert result['tier_job']['status'] in ('QUEUED', 'RUNNING', 'COMPLETE')

    added = [e for e in events if e[0] == 'ADDED']
    assert len(added) == 1, pprint.pformat(events)
    assert added[0][1]['fields']['dataset_name'] == tier_ds


# ---------------------------------------------------------------------------
# dataset_set_tier — validation errors
# ---------------------------------------------------------------------------

def test_dataset_set_tier_globally_disabled():
    """Returns EINVAL when tiering is globally disabled."""
    if not call('system.is_enterprise'):
        pytest.skip('Requires enterprise to toggle enabled flag')

    original = call('zfs.tier.config')['enabled']
    try:
        call('zfs.tier.update', {'enabled': False})
        with pytest.raises(ValidationErrors) as ve:
            call('zfs.tier.dataset_set_tier', {
                'dataset_name': 'tank/nonexistent',
                'tier_type': 'PERFORMANCE',
            })
        assert ve.value.errors[0].attribute == 'zfs_tier_dataset_set_tier.dataset_name'
        assert ve.value.errors[0].errno == errno.EINVAL
    finally:
        call('zfs.tier.update', {'enabled': original})


def test_dataset_set_tier_no_special_vdev(tier_pool):
    """Returns EINVAL for a dataset on a pool without a SPECIAL vdev."""
    # Use the default test pool which has no SPECIAL vdev
    with dataset('tier_no_special_test') as ds:
        with pytest.raises(ValidationErrors) as ve:
            call('zfs.tier.dataset_set_tier', {
                'dataset_name': ds,
                'tier_type': 'PERFORMANCE',
            })
        assert ve.value.errors[0].attribute == 'zfs_tier_dataset_set_tier.dataset_name'
        assert ve.value.errors[0].errno == errno.EINVAL
        assert 'SPECIAL vdev' in ve.value.errors[0].errmsg


def test_dataset_set_tier_ebusy_while_job_running(tier_ds):
    """Returns EBUSY when a migration job is already active."""
    # Create enough data to keep the job alive long enough to race
    ssh(f'for i in $(seq 1 100); do dd if=/dev/urandom of=/mnt/{tier_ds}/f$i bs=4k count=1 2>/dev/null; done')

    call('zfs.tier.dataset_set_tier', {'dataset_name': tier_ds, 'tier_type': 'PERFORMANCE'})
    entry = call('zfs.tier.rewrite_job_create', {'dataset_name': tier_ds})

    # Only attempt if the job is still active; skip if it already finished
    status = call('zfs.tier.rewrite_job_status', {'tier_job_id': entry['tier_job_id']})['status']
    if status not in ('RUNNING', 'QUEUED'):
        pytest.skip('Job completed before EBUSY could be triggered — dataset too small')

    with pytest.raises(ValidationErrors) as ve:
        call('zfs.tier.dataset_set_tier', {
            'dataset_name': tier_ds,
            'tier_type': 'REGULAR',
        })
    assert ve.value.errors[0].errno == errno.EBUSY


# ---------------------------------------------------------------------------
# rewrite_job_create
# ---------------------------------------------------------------------------

def test_rewrite_job_create_returns_queued_or_running(tier_ds):
    entry = call('zfs.tier.rewrite_job_create', {'dataset_name': tier_ds})
    assert entry['dataset_name'] == tier_ds
    assert '@' in entry['tier_job_id']
    assert entry['status'] in ('QUEUED', 'RUNNING')


def test_rewrite_job_create_fires_added_event(tier_ds):
    with client() as c:
        events = []
        c.subscribe('zfs.tier.rewrite_job_query', lambda t, **m: events.append((t, m)), sync=True)
        entry = c.call('zfs.tier.rewrite_job_create', {'dataset_name': tier_ds})

    assert len(events) == 1, pprint.pformat(events)
    assert events[0][0] == 'ADDED'
    assert events[0][1] == {
        'collection': 'zfs.tier.rewrite_job_query',
        'msg': 'added',
        'id': entry['tier_job_id'],
        'fields': ANY,
    }
    assert events[0][1]['fields']['dataset_name'] == tier_ds


def test_rewrite_job_create_duplicate_raises_eexist(tier_ds):
    """Creating a second job for the same dataset raises EEXIST."""
    call('zfs.tier.rewrite_job_create', {'dataset_name': tier_ds})
    with pytest.raises(ValidationErrors) as ve:
        call('zfs.tier.rewrite_job_create', {'dataset_name': tier_ds})
    assert ve.value.errors[0].errno == errno.EEXIST


# ---------------------------------------------------------------------------
# rewrite_job_query
# ---------------------------------------------------------------------------

def test_rewrite_job_query_returns_created_job(tier_ds):
    entry = call('zfs.tier.rewrite_job_create', {'dataset_name': tier_ds})
    jobs = call('zfs.tier.rewrite_job_query', {})
    ids = [j['tier_job_id'] for j in jobs]
    assert entry['tier_job_id'] in ids


def test_rewrite_job_query_status_filter(tier_ds):
    entry = call('zfs.tier.rewrite_job_create', {'dataset_name': tier_ds})
    current_status = call('zfs.tier.rewrite_job_status', {'tier_job_id': entry['tier_job_id']})['status']

    matching = call('zfs.tier.rewrite_job_query', {'status': [current_status]})
    assert any(j['tier_job_id'] == entry['tier_job_id'] for j in matching)

    # Filter by a different terminal status — should not appear (unless job already transitioned)
    non_matching_status = 'CANCELLED'
    if current_status != non_matching_status:
        non_matching = call('zfs.tier.rewrite_job_query', {'status': [non_matching_status]})
        assert all(j['tier_job_id'] != entry['tier_job_id'] for j in non_matching)


# ---------------------------------------------------------------------------
# rewrite_job_status
# ---------------------------------------------------------------------------

def test_rewrite_job_status_shape(tier_ds):
    entry = call('zfs.tier.rewrite_job_create', {'dataset_name': tier_ds})
    status = call('zfs.tier.rewrite_job_status', {'tier_job_id': entry['tier_job_id']})

    assert status['tier_job_id'] == entry['tier_job_id']
    assert status['dataset_name'] == tier_ds
    assert status['job_uuid'] == entry['job_uuid']
    assert status['status'] in ('QUEUED', 'RUNNING', 'COMPLETE', 'CANCELLED', 'STOPPED', 'ERROR')
    # stats may be None if the job hasn't started yet
    assert status['stats'] is None or isinstance(status['stats'], dict)
    assert status['error'] is None or isinstance(status['error'], str)


def test_rewrite_job_status_completes(tier_ds):
    """A job on an empty dataset should reach COMPLETE quickly."""
    entry = call('zfs.tier.rewrite_job_create', {'dataset_name': tier_ds})
    final = _wait_for_job_status(entry['tier_job_id'], {'COMPLETE', 'ERROR'}, timeout=60)
    assert final == 'COMPLETE'


# ---------------------------------------------------------------------------
# rewrite_job_abort
# ---------------------------------------------------------------------------

def test_rewrite_job_abort_fires_changed_event(tier_ds):
    ssh(f'for i in $(seq 1 100); do dd if=/dev/urandom of=/mnt/{tier_ds}/f$i bs=4k count=1 2>/dev/null; done')

    entry = call('zfs.tier.rewrite_job_create', {'dataset_name': tier_ds})

    status = call('zfs.tier.rewrite_job_status', {'tier_job_id': entry['tier_job_id']})['status']
    if status not in ('RUNNING', 'QUEUED'):
        pytest.skip('Job completed before abort could be tested — dataset too small')

    with client() as c:
        events = []
        c.subscribe('zfs.tier.rewrite_job_query', lambda t, **m: events.append((t, m)), sync=True)
        c.call('zfs.tier.rewrite_job_abort', {'tier_job_id': entry['tier_job_id']})

    changed = [e for e in events if e[0] == 'CHANGED']
    assert changed, pprint.pformat(events)
    assert changed[-1][1]['fields']['status'] == 'CANCELLED'
    assert changed[-1][1]['fields']['tier_job_id'] == entry['tier_job_id']


def test_rewrite_job_abort_nonexistent_raises():
    with pytest.raises(ValidationErrors) as ve:
        call('zfs.tier.rewrite_job_abort', {'tier_job_id': 'tank/nonexistent@00000000-0000-0000-0000-000000000000'})
    assert ve.value.errors[0].errno in (errno.ENOENT, errno.EINVAL)


# ---------------------------------------------------------------------------
# rewrite_job_status event source
# ---------------------------------------------------------------------------

def test_rewrite_job_status_event_source(tier_ds):
    """The polling event source emits CHANGED events while a job is active."""
    ssh(f'for i in $(seq 1 100); do dd if=/dev/urandom of=/mnt/{tier_ds}/f$i bs=4k count=1 2>/dev/null; done')
    call('zfs.tier.rewrite_job_create', {'dataset_name': tier_ds})

    arg = json.dumps({'dataset_name': tier_ds})
    with client() as c:
        events = []
        c.subscribe(
            f'zfs.tier.rewrite_job_status:{arg}',
            lambda t, **m: events.append((t, m)),
            sync=True,
        )
        time.sleep(6)  # event source polls every 2s

    assert events, 'No events received from rewrite_job_status event source'
    assert events[0][0] == 'CHANGED'
    assert events[0][1]['fields']['dataset_name'] == tier_ds
    assert 'status' in events[0][1]['fields']
