#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD

import unittest
import sys
import os
import xmlrunner
apifolder = os.getcwd()
sys.path.append(apifolder)
from auto_config import interface, results_xml
from functions import POST, PUT
try:
    from config import BRIDGEDOMAIN, BRIDGEHOST, BRIDGEDNS, BRIDGEGW
except ImportError:
    RunTest = False
else:
    RunTest = True
TestName = "create network"


class create_network_test(unittest.TestCase):

    def test_01_configure_interface_dhcp(self):
        payload = {"int_dhcp": "true",
                   "int_name": "ext",
                   "int_interface": interface}
        assert POST("/network/interface/", payload) == 201

    def test_02_Setting_default_route_and_DNS(self):
        payload = {"gc_domain": BRIDGEDOMAIN,
                   "gc_hostname": BRIDGEHOST,
                   "gc_ipv4gateway": BRIDGEGW,
                   "gc_nameserver1": BRIDGEDNS}
        assert PUT("/network/globalconfiguration/", payload) == 200


def run_test():
    suite = unittest.TestLoader().loadTestsFromTestCase(create_network_test)
    xmlrunner.XMLTestRunner(output=results_xml, verbosity=2).run(suite)

if RunTest is True:
    print('\n\nStarting %s tests...' % TestName)
    run_test()
