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


class bootenv_test(unittest.TestCase):

    def test_01_Cloning_a_new_boot_environment_newbe2(services):
        payload = {"name": "newbe2", "source": "newbe1"}
        assert POST("/system/bootenv/", payload) == 201

if __name__ == "__main__":
    unittest.main(verbosity=2)
