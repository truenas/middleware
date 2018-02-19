#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD

import unittest
import sys
import os
import xmlrunner
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, GET, POST
from auto_config import disk1, disk2, results_xml
RunTest = True
TestName = "create storage"


class create_storage_test(unittest.TestCase):

    def test_01_Check_getting_disks(self):
        assert GET("/storage/disk/") == 200

    def test_02_Check_getting_disks(self):
        assert GET("/storage/volume/") == 200

    def test_03_Check_creating_a_zpool(self):
        payload = {"volume_name": "tank",
                   "layout": [{"vdevtype": "stripe", "disks": [disk1, disk2]}]}
        assert POST("/storage/volume/", payload) == 201

    def test_04_Check_creating_dataset_01_20_share(self):
        payload = {"name": "share"}
        assert POST("/storage/volume/tank/datasets/", payload) == 201

    def test_05_Check_creating_dataset_02_20_jails(self):
        payload = {"name": "jails"}
        assert POST("/storage/volume/tank/datasets/", payload) == 201

    def test_06_Changing_permissions_on_share(self):
        payload = {"mp_path": "/mnt/tank/share",
                   "mp_acl": "unix",
                   "mp_mode": "777",
                   "mp_user": "root",
                   "mp_group": "wheel"}
        assert PUT("/storage/permission/", payload) == 201

    def test_07_Changing_permissions_on_share(self):
        payload = {"mp_path": "/mnt/tank/jails",
                   "mp_acl": "unix",
                   "mp_mode": "777",
                   "mp_user": "root",
                   "mp_group": "wheel"}
        assert PUT("/storage/permission/", payload) == 201

    def test_08_Creating_a_ZFS_snapshot(self):
        payload = {"dataset": "tank", "name": "test"}
        assert POST("/storage/snapshot/", payload) == 201

    def test_09_Creating_dataset_for_testing_snapshot(self):
        payload = {"name": "snapcheck"}
        assert POST("/storage/volume/tank/datasets/", payload) == 201

    def test_10_Creating_a_ZVOL_1sur2(self):
        payload = {"name": "testzvol1", "volsize": "10M"}
        assert POST("/storage/volume/tank/zvols/", payload) == 202

    def test_11_Creating_a_ZVOL_2sur2(self):
        payload = {"name": "testzvol2", "volsize": "10M"}
        assert POST("/storage/volume/tank/zvols/", payload) == 202


def run_test():
    suite = unittest.TestLoader().loadTestsFromTestCase(create_storage_test)
    xmlrunner.XMLTestRunner(output=results_xml, verbosity=2).run(suite)

if RunTest is True:
    print('\n\nStarting %s tests...' % TestName)
    run_test()
