#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD

import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, GET, POST
from auto_config import disk1, disk2


# Create tests
def test_01_Check_getting_disks():
    results = GET("/storage/disk/", api=1)
    assert results.status_code == 200, results.text


def test_02_Check_getting_disks():
    results = GET("/storage/volume/", api=1)
    assert results.status_code == 200, results.text


def test_03_creating_a_zpool():
    payload = {"volume_name": "tank",
               "layout": [{"vdevtype": "stripe", "disks": [disk1, disk2]}]}
    results = POST("/storage/volume/", payload, api=1)
    assert results.status_code == 201, results.text


def test_04_creating_dataset_share():
    payload = {"name": "share"}
    results = POST("/storage/volume/tank/datasets/", payload, api=1)
    assert results.status_code == 201, results.text


def test_05_creating_dataset_jails():
    payload = {"name": "jails"}
    results = POST("/storage/volume/tank/datasets/", payload, api=1)
    assert results.status_code == 201, results.text


def test_06_changing_permissions_on_share():
    payload = {"mp_path": "/mnt/tank/share",
               "mp_acl": "unix",
               "mp_mode": "777",
               "mp_user": "root",
               "mp_group": "wheel"}
    results = PUT("/storage/permission/", payload, api=1)
    assert results.status_code == 201, results.text


def test_07_changing_permissions_on_share():
    payload = {"mp_path": "/mnt/tank/jails",
               "mp_acl": "unix",
               "mp_mode": "777",
               "mp_user": "root",
               "mp_group": "wheel"}
    results = PUT("/storage/permission/", payload, api=1)
    assert results.status_code == 201, results.text
