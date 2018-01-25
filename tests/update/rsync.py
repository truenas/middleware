#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import unittest
import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import GET_OUTPUT  # , PUT


class nfs_test(unittest.TestCase):

    # def test_01_Updating_rsync_resource(self):
    #     payload = {"rsyncmod_user": "testuser"}
    #     assert PUT("/services/rsyncmod/1/", payload) == 200

    def test_02_Checking_to_see_if_rsync_service_is_enabled(self):
        assert GET_OUTPUT("/services/services/rsync/",
                          "srv_state") == "RUNNING"

if __name__ == "__main__":
    unittest.main(verbosity=2)
