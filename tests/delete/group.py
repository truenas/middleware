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
TestName = "delete group"


class delete_group_test(unittest.TestCase):

    # Delete the testgroup
    def test_01_Delete_group_testgroup_newgroup(self):
        assert DELETE("/account/groups/1/") == 204


def run_test():
    suite = unittest.TestLoader().loadTestsFromTestCase(delete_group_test)
    xmlrunner.XMLTestRunner(output=results_xml, verbosity=2).run(suite)

if RunTest is True:
    print('\n\nStarting %s tests...' % TestName)
    run_test()
