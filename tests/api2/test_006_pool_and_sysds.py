import time

import pytest
from pytest_dependency import depends

from auto_config import ha, pool_name
from middlewared.test.integration.utils import call, fail
from middlewared.test.integration.utils.client import client


def wait_for_standby(ws_client):
    # we sleep here since this function is called directly after
    # the system dataset has been explicitly migrated to another
    # zpool. On HA systems, the standby node will reboot but we
    # need to give the other controller some time to actually
    # reboot before we start checking to make sure it's online
    time.sleep(5)

    sleep_time, max_wait_time = 1, 300
    rebooted = False
    waited_time = 0
    while waited_time < max_wait_time and not rebooted:
        if ws_client.call('failover.remote_connected'):
            rebooted = True
        else:
            waited_time += sleep_time
            time.sleep(sleep_time)

    assert rebooted, f'Standby did not connect after {max_wait_time} seconds'

    waited_time = 0  # need to reset this
    is_backup = False
    while waited_time < max_wait_time and not is_backup:
        try:
            is_backup = ws_client.call('failover.call_remote', 'failover.status') == 'BACKUP'
        except Exception:
            pass

        if not is_backup:
            waited_time += sleep_time
            time.sleep(sleep_time)

    assert is_backup, f'Standby node did not become BACKUP after {max_wait_time} seconds'
    pass


@pytest.fixture(scope='module')
def ws_client():
    # by the time this test is called in the pipeline,
    # the HA VM should have networking configured so
    # we can use the VIP
    with client() as c:
        yield c


@pytest.fixture(scope='module')
def pool_data():
    return dict()


@pytest.mark.dependency(name='SYSDS')
def test_001_check_sysdataset_exists_on_boot_pool(ws_client):
    """
    When a system is first installed or all zpools are deleted
    then we place the system dataset on the boot pool. Since our
    CI pipelines always start with a fresh VM, we can safely assume
    that there are no zpools (created or imported) by the time this
    test runs and so we can assert this accordingly.
    """
    bp_name = ws_client.call('boot.pool_name')
    bp_basename = f'{bp_name}/.system'
    sysds = ws_client.call('systemdataset.config')
    assert bp_name == sysds['pool']
    assert bp_basename == sysds['basename']


def test_002_create_permanent_zpool(request, ws_client):
    """
    This creates the "permanent" zpool which is used by every other
    test module in the pipeline.
    More specifically we do the following:
        1. get unused disks
        2. create a 1 disk striped zpool
        3. verify system dataset automagically migrated to this pool
    """
    depends(request, ['SYSDS'])
    unused_disks = ws_client.call('disk.details')['unused']
    assert len(unused_disks) >= 2

    try:
        ws_client.call(
            'pool.create', {
                'name': pool_name,
                'topology': {'data': [{'type': 'STRIPE', 'disks': [unused_disks[0]['name']]}]}
            },
            job=True
        )
    except Exception as e:
        fail(f"Unable to create test pool: {e!r}. Aborting tests.")
    else:
        results = ws_client.call('systemdataset.config')
        assert results['pool'] == pool_name
        assert results['basename'] == f'{pool_name}/.system'

    try:
        sysdataset_update = ws_client.call('core.get_jobs', [
            ['method', '=', 'systemdataset.update']
        ], {'order_by': ['-id'], 'get': True})
    except Exception:
        fail('Failed to get status of systemdataset update')

    if sysdataset_update['state'] != 'SUCCESS':
        fail(f'System dataset move failed: {sysdataset_update["error"]}')


@pytest.mark.dependency(name='POOL_FUNCTIONALITY1')
def test_003_verify_unused_disk_and_sysds_functionality_on_2nd_pool(ws_client, pool_data):
    """
    This tests a few items related to zpool creation logic:
    1. disk.details()['unused'] should NOT show disks that are a part of a zpool that is
        currently imported (inversely, disk.details()['used'] should show disks that are
        currently in use by a zpool that is imported)
    2. make sure the system dataset doesn't migrate to the 2nd zpool that we create
        since it should only be migrating to the 1st zpool that is created
    3. after verifying system dataset doesn't migrate to the 2nd zpool, explicitly
        migrate it to the 2nd zpool. Migrating system datasets between zpools is a
        common operation and can be very finicky so explicitly testing this operation
        is of paramount importance.
    4. after the system dataset was migrated to the 2nd pool, migrate it back to the
        1st pool. The 2nd pool is a temporary pool used to test other functionality
        and isn't used through the CI test suite so best to clean it up.
    """
    unused_disks = ws_client.call('disk.get_unused')
    assert len(unused_disks) >= 1

    temp_pool_name = 'temp'

    pool = ws_client.call(
        'pool.create', {
            'name': temp_pool_name,
            'topology': {'data': [{'type': 'STRIPE', 'disks': [unused_disks[0]['name']]}]}
        },
        job=True
    )

    pool_data[pool['name']] = pool
    disk_deets = ws_client.call('disk.details')
    # disk should not show up in `exported_zpool` keys since it's still imported
    assert not any((i['exported_zpool'] == pool['name'] for i in disk_deets['unused']))
    # disk should show up in `imported_zpool` key
    assert any((i['imported_zpool'] == pool['name'] for i in disk_deets['used']))

    sysds = ws_client.call('systemdataset.config')
    assert pool['name'] != sysds['pool']
    assert f'{pool["name"]}/.system' != sysds['basename']

    # explicitly migrate sysdataset to temp pool
    try:
        ws_client.call('systemdataset.update', {'pool': temp_pool_name}, job=True)
    except Exception as e:
        fail(f'Failed to move system dataset to temporary pool: {e}')
    else:
        if ha:
            wait_for_standby(ws_client)

    try:
        ws_client.call('systemdataset.update', {'pool': pool_name}, job=True)
    except Exception as e:
        fail(f'Failed to return system dataset from temporary pool: {e}')
    else:
        if ha:
            wait_for_standby(ws_client)


def test_004_verify_pool_property_unused_disk_functionality(request, ws_client, pool_data):
    """
    This does a few things:
    1. export the zpool without wiping the disk and verify that disk.get_used
        still shows the relevant disk as being part of an exported zpool
    2. clean up the pool by exporting and wiping the disks
    3. finally, if this is HA enable failover since all tests after this one
        expect it to be turned on
    """
    depends(request, ['POOL_FUNCTIONALITY1'])
    zp_name = list(pool_data.keys())[0]

    # export zpool
    try:
        ws_client.call('pool.export', pool_data[zp_name]['id'], job=True)
    except Exception as e:
        assert False, e

    imported = False
    try:
        # disk should show up in `exported_zpool` keys since zpool was exported
        # without wiping the disk
        used_disks = ws_client.call('disk.get_used')
        assert any((i['exported_zpool'] == zp_name for i in used_disks))

        # pool should be available to be imported again
        available_pools = ws_client.call('pool.import_find', job=True)
        assert len(available_pools) == 1 and available_pools[0]['name'] == zp_name

        # import it
        imported = ws_client.call('pool.import_pool', {'guid': available_pools[0]['guid']}, job=True)
        assert imported
    finally:
        if imported:
            temp_id = ws_client.call('pool.query', [['name', '=', zp_name]], {'get': True})['id']
            options = {'cascade': True, 'restart_services': True, 'destroy': True}
            ws_client.call('pool.export', temp_id, options, job=True)

        if ha:
            # every test after this one expects this to be enabled
            ws_client.call('failover.update', {'disabled': False, 'master': True})
            assert ws_client.call('failover.config')['disabled'] is False


def test__check_root_level_dataset_properties():
    """ validate that our root-level dataset has expected properties """
    ds = call('pool.dataset.get_instance', pool_name)
    assert ds['acltype']['value'] == 'POSIX'
    assert ds['aclmode']['value'] == 'DISCARD'
    assert ds['xattr']['value'] == 'ON'
    assert ds['deduplication']['value'] == 'OFF'
    assert ds['casesensitivity']['value'] == 'SENSITIVE'
    assert ds['compression']['value'] == 'LZ4'
    assert ds['snapdev']['value'] == 'HIDDEN'
    assert ds['sync']['value'] == 'STANDARD'
    assert ds['checksum']['value'] == 'SA'
    assert ds['snapdir']['value'] == 'HIDDEN'
