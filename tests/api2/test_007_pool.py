#!/usr/bin/env python3

import pytest
import sys
import os
import re
from pytest_dependency import depends
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import POST, GET, wait_on_job, make_ws_request
from auto_config import pool_name, ha  # , ha_pool_name
from middlewared.test.integration.assets.pool import another_pool

IMAGES = {}
loops = {
    'msdosfs': '/dev/loop8',
    'msdosfs-nonascii': '/dev/loop9',
    'ntfs': '/dev/loop10'
}
boot_pool_disks = GET('/boot/get_disks/', controller_a=ha).json()
all_disks = list(POST('/device/get_info/', 'DISK', controller_a=ha).json().keys())
pool_disks = sorted(list(set(all_disks) - set(boot_pool_disks)))
tank_pool_disks = [pool_disks[0]]

if ha and "virtual_ip" in os.environ:
    ip = os.environ["virtual_ip"]
else:
    from auto_config import ip


@pytest.fixture(scope='module')
def pool_data():
    return {}


def test_01_get_pool():
    results = GET("/pool/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list), results.text


@pytest.mark.dependency(name="wipe_disk")
@pytest.mark.parametrize('disk', pool_disks)
def test_02_wipe_pool_disk(disk):
    payload = {
        "dev": disk,
        "mode": "QUICK",
        "synccache": True
    }
    results = POST('/disk/wipe/', payload)
    job_id = results.json()
    job_status = wait_on_job(job_id, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


@pytest.mark.dependency(name="pool_04")
def test_03_creating_a_pool(request):
    depends(request, ["wipe_disk"])
    global payload
    payload = {
        "name": pool_name,
        "encryption": False,
        "topology": {
            "data": [
                {"type": "STRIPE", "disks": tank_pool_disks}
            ],
        },
        "allow_duplicate_serials": True,
    }
    results = POST("/pool/", payload)
    assert results.status_code == 200, results.text
    job_id = results.json()
    job_status = wait_on_job(job_id, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


@pytest.mark.dependency(name="get_pool_id")
def test_04_get_pool_id(request, pool_data):
    depends(request, ["pool_04"])
    results = GET(f"/pool?name={pool_name}")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list), results.text
    pool_data['id'] = results.json()[0]['id']


def test_05_get_pool_disks(request, pool_data):
    depends(request, ["get_pool_id"])
    payload = {'msg': 'method', 'method': 'pool.get_disks', 'params': [pool_data['id']]}
    res = make_ws_request(ip, payload)
    assert isinstance(res['result'], list), res
    assert res['result'] and (set(res['result']) == set(tank_pool_disks)), res


def test_06_get_pool_id_info(request, pool_data):
    depends(request, ["pool_04"])
    results = GET(f"/pool/id/{pool_data['id']}/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    global pool_info
    pool_info = results


@pytest.mark.parametrize('pool_keys', ["name", "topology:data:disks"])
def test_07_looking_pool_info_of_(request, pool_keys):
    depends(request, ["pool_04"])
    results = pool_info
    if ':' in pool_keys:
        keys_list = pool_keys.split(':')
        if 'disks' in keys_list:
            info = results.json()[keys_list[0]][keys_list[1]]
            disk_list = payload[keys_list[0]][keys_list[1]][0][keys_list[2]]
            for props in info:
                device = re.sub(r'[0-9]+', '', props['device'])
                assert device in disk_list, results.text
                assert props['disk'] in disk_list, results.text
        else:
            info = results.json()[keys_list[0]][keys_list[1]][keys_list[2]]
    else:
        assert payload[pool_keys] == results.json()[pool_keys], results.text


def test_08_test_pool_property_normalization(request):
    """
    middleware attempts to normalize certain ZFS dataset properties so that
    importing a foreign pool doesn't break our configuration. Currently we
    do this by resetting the mountpoint of datasets, and disabling sharenfs
    property. This test simultates such a situation by creating a test pool
    setting parameters that must be migrated, then exporting the pool and
    re-importing it. Once this is complete, we check whether properties
    have been set to their correct new values.
    """
    depends(request, ["pool_04"])
    global tp
    with another_pool() as tp:
        payload = {'msg': 'method', 'method': 'zfs.dataset.update', 'params': [
            tp['name'],
            {'properties': {
                'sharenfs': {'value': 'on'},
            }},
        ]}
        res = make_ws_request(ip, payload)
        error = res.get('error')
        assert error is not None, str(error)
        assert 'NFS share creation failed' in error['reason'], str(error['reason'])

        result = POST("/pool/dataset/", {"name": f"{tp['name']}/ds1"})
        assert result.status_code == 200, result.text

        payload['params'][0] += "/ds1"
        payload['params'][1]['properties'].update({
            'mountpoint': {'value': 'legacy'},
        })
        res = make_ws_request(ip, payload)
        error = res.get('error')
        assert error is None, str(error)

    res = GET("/pool/import_find")
    assert res.status_code == 200, res.text
    job_id = res.json()
    job_status = wait_on_job(job_id, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])

    available = job_status['results']['result']
    assert len(available) == 1, res.text
    assert available[0]['name'] == tp['name'], res.text

    res = POST('/pool/import_pool', {'guid': available[0]['guid']})
    assert res.status_code == 200, res.text
    job_id = res.json()
    job_status = wait_on_job(job_id, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])

    for ds in (f'{tp["name"]}/ds1', tp['name']):
        payload = {'msg': 'method', 'method': 'zfs.dataset.query', 'params': [
            [['id', '=', ds]],
            {'get': True, 'extra': {'retrieve_children': False}}
        ]}
        req = make_ws_request(ip, payload)
        error = req.get('error')
        ds = req.get('result')

        assert error is None, str(error)
        assert ds['properties']['mountpoint']['value'] != 'legacy', str(ds['properties'])
        assert ds['properties']['sharenfs']['value'] == 'off', str(ds['properties'])


def test_09_export_test_pool_with_destroy_true(request):
    depends(request, ["pool_04"])
    payload = {'cascade': True, 'restart_services': True, 'destroy': True}
    results = POST(f'/pool/id/{tp["id"]}/export/', payload)
    assert results.status_code == 200, results.text
    job_id = results.json()
    job_status = wait_on_job(job_id, 120)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])

    results = GET(f'/pool/id/{tp["id"]}')
    assert results.status_code == 404, results.text


def test_10_test_get_unused_before_pool_export_and_after_pool_export(request):
    depends(request, ["pool_04"])

    with another_pool() as temp:
        # disk should not show up in `exported_zpool` keys
        results = POST('/disk/get_unused/', False)
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), list), results.text
        assert not any((i['exported_zpool'] == temp['name'] for i in results.json())), results.json()

    results = POST('/disk/get_unused/', False)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list), results.text
    # disk should show up in `exported_zpool` keys
    assert any((i['exported_zpool'] == temp['name'] for i in results.json())), results.json()
