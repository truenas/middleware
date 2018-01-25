#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD

import unittest
import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import POST


class bootenv_test(unittest.TestCase):

    def test_01_Creating_a_new_boot_environment_newbe1(self):
        payload = {"name": "newbe1", "source": "default"}
        assert POST("/system/bootenv/", payload) == 201

if __name__ == "__main__":
    unittest.main(verbosity=2)
