#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD

import unittest
import sys
import os
import xmlrunner
apifolder = os.getcwd()
sys.path.append(apifolder)
from auto_config import interface, results_xml, ip
from functions import GET_ALL_OUTPUT
# try:
#     from config import BRIDGEDOMAIN, BRIDGEHOST, BRIDGEDNS, BRIDGEGW
# except ImportError:
#      RunTest = False
# else:

RunTest = True
TestName = "get interface information"


class get_interfaces_test(unittest.TestCase):

    def test_01_get_interfaces_driver(self):
        assert GET_ALL_OUTPUT('/interfaces/query')[0]['name'] == interface

    def test_02_get_interfaces_ip(self):
        getip = GET_ALL_OUTPUT('/interfaces/query')[0]['aliases'][1]['address']
        assert getip == ip

    def test_03_get_interfaces_netmask(self):
        getinfo = GET_ALL_OUTPUT('/interfaces/query')
        getinfo = getinfo[0]['aliases'][1]['netmask']
        assert getinfo == 24


def run_test():
    suite = unittest.TestLoader().loadTestsFromTestCase(get_interfaces_test)
    xmlrunner.XMLTestRunner(output=results_xml, verbosity=2).run(suite)

if RunTest is True:
    print('\n\nStarting %s tests...' % TestName)
    run_test()
