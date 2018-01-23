#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import unittest
import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import DELETE


class bootenv_test(unittest.TestCase):

    def test_01_Removing_a_boot_environment_newbe2(self):
        assert DELETE("/system/bootenv/newbe2/") == 204

if __name__ == "__main__":
    unittest.main(verbosity=2)
