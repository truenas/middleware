#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD

import unittest
import sys
import os
import xmlrunner
apifolder = os.getcwd()
sys.path.append(apifolder)
from auto_config import results_xml, disk1, disk2
from functions import GET_ALL_OUTPUT

disk0 = disk1[:-1] + '0'

RunTest = True
TestName = "get disk information"


class get_disk_info_test(unittest.TestCase):

    def test_01_verifying_that_the_installer_created_all_disk(self):
        assert len(GET_ALL_OUTPUT('/disk')) == 3

    def test_02_looking_for_disk0_was_created(self):
        assert GET_ALL_OUTPUT('/disk')[0]['name'] == disk0

    def test_03_looking_disk0_subsystem(self):
        assert GET_ALL_OUTPUT('/disk')[0]['subsystem'] == disk0[:-1]

    def test_04_looking_disk0_number(self):
        assert GET_ALL_OUTPUT('/disk')[0]['number'] == 0

    def test_05_looking_disk0_identifier_and_serial_match(self):
        identifier_serial = GET_ALL_OUTPUT('/disk')[0]['identifier'][8:]
        serial = GET_ALL_OUTPUT('/disk')[0]['serial']
        assert identifier_serial == serial

    def test_06_looking_for_disk1_was_created(self):
        assert GET_ALL_OUTPUT('/disk')[1]['name'] == disk1

    def test_07_looking_disk1_subsystem(self):
        assert GET_ALL_OUTPUT('/disk')[1]['subsystem'] == disk1[:-1]

    def test_08_looking_disk1_number(self):
        assert GET_ALL_OUTPUT('/disk')[1]['number'] == 1

    def test_09_looking_disk1_identifier_and_serial_match(self):
        identifier_serial = GET_ALL_OUTPUT('/disk')[1]['identifier'][8:]
        serial = GET_ALL_OUTPUT('/disk')[1]['serial']
        assert identifier_serial == serial

    def test_10_looking_for_disk2_was_created(self):
        assert GET_ALL_OUTPUT('/disk')[2]['name'] == disk2

    def test_11_looking_disk2_subsystem(self):
        assert GET_ALL_OUTPUT('/disk')[2]['subsystem'] == disk2[:-1]

    def test_12_looking_disk2_number(self):
        assert GET_ALL_OUTPUT('/disk')[2]['number'] == 2

    def test_13_looking_disk2_identifier_and_serial_match(self):
        identifier_serial = GET_ALL_OUTPUT('/disk')[2]['identifier'][8:]
        serial = GET_ALL_OUTPUT('/disk')[2]['serial']
        assert identifier_serial == serial


def run_test():
    suite = unittest.TestLoader().loadTestsFromTestCase(get_disk_info_test)
    xmlrunner.XMLTestRunner(output=results_xml, verbosity=2).run(suite)

if RunTest is True:
    print('\n\nStarting %s tests...' % TestName)
    run_test()
