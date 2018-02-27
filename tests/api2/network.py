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
try:
    from config import BRIDGEGW
except ImportError:
    RunTest = False
else:
    RunTest = True
TestName = "get network information"


class get_network_info_test(unittest.TestCase):

    def test_01_get_IPV4_info(self):
        getinfo = GET_ALL_OUTPUT("/network/general/summary")
        getinfo = getinfo['ips'][interface]['IPV4']
        assert getinfo == ['%s/24' % ip]

    def test_02_get_default_routes_info(self):
        getinfo = GET_ALL_OUTPUT("/network/general/summary")
        getinfo = getinfo['default_routes'][0]
        assert getinfo == BRIDGEGW

    def test_03_get_nameserver_info(self):
        getinfo = GET_ALL_OUTPUT("/network/general/summary")['nameservers'][0]
        assert getinfo == BRIDGEGW


def run_test():
    suite = unittest.TestLoader().loadTestsFromTestCase(get_network_info_test)
    xmlrunner.XMLTestRunner(output=results_xml, verbosity=2).run(suite)

if RunTest is True:
    print('\n\nStarting %s tests...' % TestName)
    run_test()
