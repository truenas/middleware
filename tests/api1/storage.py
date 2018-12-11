#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD

import pytest
import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, GET, POST, DELETE
from auto_config import disk0, disk1, disk2

disk_list = [disk0, disk1, disk2]

pool_data = {
    'is_decrypted': True,
    'mountpoint': '/mnt/tank',
    'name': 'tank',
    'status': 'HEALTHY',
    'vol_encryptkey': '',
    'vol_name': 'tank'
}

datasets = ['share', 'jails', 'snapcheck', 'testzvol1', 'testzvol2']


def test_01_Check_getting_disks():
    global results
    results = GET("/storage/disk/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list), results.text


# make sure all disk exist
@pytest.mark.parametrize('disk', disk_list)
def test_02_Check_existence_of_(disk):
    for disk_info in results.json():
        if disk_info['disk_name'] == disk:
            assert True
            break
    else:
        assert False, results.text


def test_03_check_get_storage_volume():
    results = GET("/storage/volume/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list), results.text
    assert results.json() == [], results.text


def test_04_creating_storage_volume():
    payload = {
        "volume_name": "tank",
        "layout": [
            {
                "vdevtype": "stripe",
                "disks": [disk1, disk2]
            }
        ]
    }
    global results
    results = POST("/storage/volume/", payload)
    assert results.status_code == 201, results.text
    assert isinstance(results.json(), dict), results.text


@pytest.mark.parametrize('data', list(pool_data.keys()))
def test_05_check_created_storage_volume_results_(data):
    assert results.json()[data] == pool_data[data], results.text


def test_06_get_storage_volume():
    global results
    results = GET("/storage/volume/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list), results.text


@pytest.mark.parametrize('data', list(pool_data.keys()))
def test_07_check_get_storage_volume_results_(data):
    assert results.json()[0][data] == pool_data[data], results.text


@pytest.mark.parametrize('dataset', ['share', 'jails'])
def test_08_creating_dataset_(dataset):
    if 'testzvol' in dataset:
        payload = {"name": dataset, "volsize": "10M"}
    else:
        payload = {"name": dataset}
    results = POST("/storage/volume/tank/datasets/", payload)
    assert results.status_code == 201, results.text


@pytest.mark.parametrize('dataset', ['share', 'jails'])
def test_09_changing_permissions_on_(dataset):
    payload = {
        "mp_path": f"/mnt/tank/{dataset}",
        "mp_acl": "unix",
        "mp_mode": "777",
        "mp_user": "root",
        "mp_group": "wheel"
    }
    results = PUT("/storage/permission/", payload)
    assert results.status_code == 201, results.text


# Check to verify snapshot was rolled back
@pytest.mark.parametrize('dataset', ['share', 'jails'])
def test_10_verify_the_existence_of_dataset_(dataset):
    results = GET("/storage/volume/tank/datasets/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list), results.text
    for name_dict in results.json():
        if name_dict['name'] == dataset:
            assert name_dict['name'] == dataset, results.text
            break
    else:
        assert False, results.test


def test_11_Creating_a_ZFS_snapshot():
    payload = {"dataset": "tank", "name": "test"}
    results = POST("/storage/snapshot/", payload)
    assert results.status_code == 201, results.text


@pytest.mark.parametrize('dataset', ['snapcheck'])
def test_12_creating_dataset_(dataset):
    payload = {"name": dataset}
    results = POST("/storage/volume/tank/datasets/", payload)
    assert results.status_code == 201, results.text


@pytest.mark.parametrize('zvol', ['testzvol1', 'testzvol2'])
def test_13_creating_zvol_(zvol):
    payload = {"name": zvol, "volsize": "10M"}
    results = POST("/storage/volume/tank/zvols/", payload)
    assert results.status_code == 202, results.text


# Check updating a ZVOL
def test_14_updating_zvols_testzvol1():
    payload = {"volsize": "50M"}
    results = PUT("/storage/volume/tank/zvols/testzvol1/", payload)
    assert results.status_code == 201, results.text


# Check rolling back a ZFS snapshot
def test_15_Rolling_back_ZFS_snapshot_tank_test():
    payload = {"force": True}
    results = POST("/storage/snapshot/tank@test/rollback/", payload)
    assert results.status_code == 202, results.text


# Check to verify snapshot was rolled back
@pytest.mark.parametrize('dataset', ['snapcheck'])
def test_16_verify_the_existence_of_dataset_(dataset):
    results = GET(f"/storage/volume/tank/datasets/{dataset}/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text


@pytest.mark.parametrize('zvol', ['testzvol1', 'testzvol2'])
def test_17_verify_the_existence_of_zvol_(zvol):
    results = GET(f"/storage/volume/tank/zvols/{zvol}/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text


# Delete tests
# Check destroying a ZFS snapshot
def test_18_destroying_zfs_snapshot_IXBUILD_ROOT_ZVOL_test():
    results = DELETE("/storage/snapshot/tank@test/")
    assert results.status_code == 204, results.text


@pytest.mark.parametrize('dataset', ['snapcheck'])
def test_19_destroying_dataset_(dataset):
    results = DELETE(f"/storage/volume/tank/datasets/{dataset}/")
    assert results.status_code == 204, results.text


# Check destroying a ZVOL
@pytest.mark.parametrize('zvol', ['testzvol1', 'testzvol2'])
def test_20_destroying_zvol_(zvol):
    results = DELETE(f"/storage/volume/tank/zvols/{zvol}/")
    assert results.status_code == 204, results.text
