#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD

import unittest
import sys
import os
import xmlrunner
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import POST, GET_OUTPUT
from auto_config import results_xml
RunTest = True
TestName = "create debug"


class create_debug_test(unittest.TestCase):

    def test_01_Creating_diagnostic_file(self):
        payload = {"name": "newbe1", "source": "default"}
        assert POST("/system/debug/", payload) == 200

    def test_02_Verify_that_API_returns_WWW_download_path(self):
        assert GET_OUTPUT("/system/debug/", "url") == "/system/debug/download/"


def run_test():
    suite = unittest.TestLoader().loadTestsFromTestCase(create_debug_test)
    xmlrunner.XMLTestRunner(output=results_xml, verbosity=2).run(suite)

if RunTest is True:
    print('\n\nStarting %s tests...' % TestName)
    run_test()
