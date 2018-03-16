#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD

import unittest
import sys
import os
import xmlrunner
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import POST
from auto_config import results_xml
TestName = "create bootenv"


class create_bootenv_test(unittest.TestCase):

    def test_01_Creating_a_new_boot_environment_newbe1(self):
        payload = {"name": "newbe1", "source": "default"}
        assert POST("/system/bootenv/", payload) == 201