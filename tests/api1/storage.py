#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD

import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, GET, POST, DELETE
from auto_config import disk1, disk2


# Create tests
def test_01_Check_getting_disks():
    results = GET("/storage/disk/")
    assert results.status_code == 200, results.text


def test_02_Check_getting_disks():
    results = GET("/storage/volume/")
    assert results.status_code == 200, results.text


def test_03_Check_creating_a_zpool():
    payload = {"volume_name": "tank",
               "layout": [{"vdevtype": "stripe", "disks": [disk1, disk2]}]}
    results = POST("/storage/volume/", payload)
    assert results.status_code == 201, results.text


def test_04_Check_creating_dataset_01_20_share():
    payload = {"name": "share"}
    results = POST("/storage/volume/tank/datasets/", payload)
    assert results.status_code == 201, results.text


def test_05_Check_creating_dataset_02_20_jails():
    payload = {"name": "jails"}
    results = POST("/storage/volume/tank/datasets/", payload)
    assert results.status_code == 201, results.text


def test_06_Changing_permissions_on_share():
    payload = {"mp_path": "/mnt/tank/share",
               "mp_acl": "unix",
               "mp_mode": "777",
               "mp_user": "root",
               "mp_group": "wheel"}
    results = PUT("/storage/permission/", payload)
    assert results.status_code == 201, results.text


def test_07_Changing_permissions_on_share():
    payload = {"mp_path": "/mnt/tank/jails",
               "mp_acl": "unix",
               "mp_mode": "777",
               "mp_user": "root",
               "mp_group": "wheel"}
    results = PUT("/storage/permission/", payload)
    assert results.status_code == 201, results.text


def test_08_Creating_a_ZFS_snapshot():
    payload = {"dataset": "tank", "name": "test"}
    results = POST("/storage/snapshot/", payload)
    assert results.status_code == 201, results.text


def test_09_Creating_dataset_for_testing_snapshot():
    payload = {"name": "snapcheck"}
    results = POST("/storage/volume/tank/datasets/", payload)
    assert results.status_code == 201, results.text


def test_10_Creating_a_ZVOL_1sur2():
    payload = {"name": "testzvol1", "volsize": "10M"}
    results = POST("/storage/volume/tank/zvols/", payload)
    assert results.status_code == 202, results.text


def test_11_Creating_a_ZVOL_2sur2():
    payload = {"name": "testzvol2", "volsize": "10M"}
    results = POST("/storage/volume/tank/zvols/", payload)
    assert results.status_code == 202, results.text


# Update tests
# Check updating a ZVOL
def test_12_Updating_ZVOL():
    payload = {"volsize": "50M"}
    results = PUT("/storage/volume/tank/zvols/testzvol1/", payload)
    assert results.status_code == 201, results.text


# Check rolling back a ZFS snapshot
def test_13_Rolling_back_ZFS_snapshot_tank_test():
    payload = {"force": True}
    results = POST("/storage/snapshot/tank@test/rollback/", payload)
    assert results.status_code == 202, results.text


# Check to verify snapshot was rolled back
# def test_14_Check_to_verify_snapshot_was_rolled_back():
#     GET_OUTPUT("/storage/volume/tank/datasets/", "name") == "snapcheck"


# Delete tests
# Check destroying a ZFS snapshot
def test_15_Destroying_ZFS_snapshot_IXBUILD_ROOT_ZVOL_test():
    results = DELETE("/storage/snapshot/tank@test/")
    assert results.status_code == 204, results.text


# Check destroying a ZVOL 1/2
def test_16_Destroying_ZVOL_01_02():
    results = DELETE("/storage/volume/tank/zvols/testzvol1/")
    assert results.status_code == 204, results.text


# Check destroying a ZVOL 2/2
def test_17_Destroying_ZVOL_02_02():
    results = DELETE("/storage/volume/tank/zvols/testzvol2/")
    assert results.status_code == 204, results.text
