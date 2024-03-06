import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)

import pytest
from pytest_dependency import depends

from auto_config import ha, ip, vip, pool_name
from middlewared.client.client import ValidationErrors
# from middlewared.test.integration.assets.directory_service import active_directory
from middlewared.test.integration.utils import fail
from middlewared.test.integration.utils.client import client, host


@pytest.fixture(scope='module')
def ws_client():
    # by the time this test is called in the pipeline,
    # the HA VM should have networking configured so
    # we can use the VIP
    with client(host_ip=vip if ha else ip) as c:
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


"""
# TODO: refactor and backport the active_directory test asset
def test_activedirectory_requires_pool(request):
    depends(request, ['SYSDS'])
    with pytest.raises(ValidationErrors) as ve:
        with active_directory():
            pass

    assert ve.value.errors[0].errmsg.startswith('Active Directory service may not be enabled before data pool is created')
"""


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
    unused_disks = ws_client.call('disk.get_unused')
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
    1. disk.get_unused should NOT show disks that are a part of a zpool that is
        currently imported
    2. make sure the system dataset doesn't migrate to the 2nd zpool that we create
        since it should only be migrating to the 1st zpool that is created
    """
    unused_disks = ws_client.call('disk.get_unused')
    assert len(unused_disks) >= 1

    try:
        pool = ws_client.call(
            'pool.create', {
                'name': 'temp',
                'topology': {'data': [{'type': 'STRIPE', 'disks': [unused_disks[0]['name']]}]}
            },
            job=True
        )
    except Exception as e:
        assert False, e
    else:
        pool_data[pool['name']] = pool
        # disk should not show up in `exported_zpool` keys since it's still imported
        unused_disks = ws_client.call('disk.get_unused', False)
        assert not any((i['exported_zpool'] == pool['name'] for i in unused_disks))

        sysds = ws_client.call('systemdataset.config')
        assert pool['name'] != sysds['pool']
        assert f'{pool["name"]}/.system' != sysds['basename']

    try:
        ws_client.call('systemdataset.update', {'pool': 'temp'}, job=True)
    except Exception as e:
        fail(f'Failed to move system dataset to temporary pool: {e}')

    try:
        ws_client.call('systemdataset.update', {'pool': pool_name}, job=True)
    except Exception as e:
        fail(f'Failed to return system dataset from temporary pool: {e}')


def test_004_verify_pool_property_unused_disk_functionality(request, ws_client, pool_data):
    """
    This does a few things:
    1. export the zpool without wiping the disk and verify that disk.get_unused
        still shows the relevant disk as being part of an exported zpool
    2. clean up the pool by exporting and wiping the disks
    3. finally, if this is HA enable failover since all tests after this one
        expect it to be turned on
    """
    depends(request, ['POOL_FUNCTIONALITY1'])
    zp_name = list(pool_data.keys())[0]
    with pytest.raises(Exception):
        # should prevent setting this property at root dataset
        ws_client.call('zfs.dataset.update', zp_name, {'properties': {'sharenfs': {'value': 'on'}}})

    # export zpool
    try:
        ws_client.call('pool.export', pool_data[zp_name]['id'], job=True)
    except Exception as e:
        assert False, e

    imported = False
    try:
        # disk should show up in `exported_zpool` keys since zpool was exported
        # without wiping the disk
        unused_disks = ws_client.call('disk.get_unused', False)
        assert any((i['exported_zpool'] == zp_name for i in unused_disks))

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
