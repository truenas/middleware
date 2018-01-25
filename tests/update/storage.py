#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import unittest
import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, POST  # , GET_OUTPUT


class storage_test(unittest.TestCase):

    # Check updating a ZVOL
    def test_01_Updating_ZVOL(self):
        payload = {"volsize": "50M"}
        assert PUT("/storage/volume/tank/zvols/testzvol1/", payload) == 201

    # Check rolling back a ZFS snapshot
    def test_02_Rolling_back_ZFS_snapshot_tank_test(self):
        payload = {"force": True}
        assert POST("/storage/snapshot/tank@test/rollback/", payload) == 202

    # Check to verify snapshot was rolled back
    # def test_03_Check_to_verify_snapshot_was_rolled_back(self):
    #     GET_OUTPUT("/storage/volume/tank/datasets/", "name") == "snapcheck"

if __name__ == "__main__":
    unittest.main(verbosity=2)
