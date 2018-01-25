#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import unittest
import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import DELETE, GET_USER


class user_test(unittest.TestCase):

    # Get the ID of testuser
    @classmethod
    def setUpClass(inst):
        inst.userid = GET_USER("testuser")

    # Delete the testuser
    def test_01_Deleting_user_testuser(self):
        assert DELETE("/account/users/%s/" % self.userid) == 204

if __name__ == "__main__":
    unittest.main(verbosity=2)
