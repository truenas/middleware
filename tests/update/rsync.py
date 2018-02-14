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
from functions import GET_OUTPUT  # , PUT
from auto_config import results_xml
RunTest = True
TestName = "update rsync"


class update_rsync_test(unittest.TestCase):

    # def test_01_Updating_rsync_resource(self):
    #     payload = {"rsyncmod_user": "testuser"}
    #     assert PUT("/services/rsyncmod/1/", payload) == 200

    def test_02_Checking_to_see_if_rsync_service_is_enabled(self):
        assert GET_OUTPUT("/services/services/rsync/",
                          "srv_state") == "RUNNING"


def run_test():
    suite = unittest.TestLoader().loadTestsFromTestCase(update_rsync_test)
    xmlrunner.XMLTestRunner(output=results_xml, verbosity=2).run(suite)

if RunTest is True:
    print('\n\nStarting %s tests...' % TestName)
    run_test()
