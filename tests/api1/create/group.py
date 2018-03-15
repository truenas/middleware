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
from functions import POST
from auto_config import results_xml
RunTest = True
TestName = "create group"


class create_group_test(unittest.TestCase):

    def test_01_Creating_group_testgroup(self):
        payload = {"bsdgrp_gid": 1200, "bsdgrp_group": "testgroup"}
        assert POST("/account/groups/", payload) == 201


def run_test():
    suite = unittest.TestLoader().loadTestsFromTestCase(create_group_test)
    xmlrunner.XMLTestRunner(output=results_xml, verbosity=2).run(suite)

if RunTest is True:
    print('\n\nStarting %s tests...' % TestName)
    run_test()
