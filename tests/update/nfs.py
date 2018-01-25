#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import unittest
import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, GET_OUTPUT


class nfs_test(unittest.TestCase):

    # Update NFS server
    def test_01_Updating_the_NFS_service(self):
        assert PUT("/services/nfs/", {"nfs_srv_servers": "50"}) == 200

    def test_02_Checking_to_see_if_NFS_service_is_enabled(self):
        assert GET_OUTPUT("/services/services/nfs/", "srv_state") == "RUNNING"

if __name__ == "__main__":
    unittest.main(verbosity=2)
