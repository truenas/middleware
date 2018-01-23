#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import unittest
import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import POST


class group_test(unittest.TestCase):

    def test_01_Creating_group_testgroup(self):
        payload = {"bsdgrp_gid": 1200, "bsdgrp_group": "testgroup"}
        assert POST("/account/groups/", payload) == 201

if __name__ == "__main__":
    unittest.main(verbosity=2)
