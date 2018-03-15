#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import unittest
import sys
import os
import xmlrunner
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import DELETE
from auto_config import results_xml
RunTest = True
TestName = "delete storage"


class delete_storage_test(unittest.TestCase):

    # Check destroying a ZFS snapshot
    def test_01_Destroying_ZFS_snapshot_IXBUILD_ROOT_ZVOL_test(self):
        assert DELETE("/storage/snapshot/tank@test/") == 204

    # Check destroying a ZVOL 1/2
    def test_01_Destroying_ZVOL_01_02(self):
        assert DELETE("/storage/volume/tank/zvols/testzvol1/") == 204

    # Check destroying a ZVOL 2/2
    def test_01_Destroying_ZVOL_02_02(self):
        assert DELETE("/storage/volume/tank/zvols/testzvol2/") == 204


def run_test():
    suite = unittest.TestLoader().loadTestsFromTestCase(delete_storage_test)
    xmlrunner.XMLTestRunner(output=results_xml, verbosity=2).run(suite)

if RunTest is True:
    print('\n\nStarting %s tests...' % TestName)
    run_test()
