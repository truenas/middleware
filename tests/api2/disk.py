#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD

import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from auto_config import disk1, disk2
from functions import GET

disk0 = disk1[:-1] + '0'
RunTest = True
TestName = "get disk information"


def test_01_verifying_that_the_installer_created_all_disk():
    assert len(GET('/disk').json()) == 3


def test_02_looking_for_disk0_was_created():
    assert GET('/disk').json()[0]['name'] == disk0


def test_03_looking_disk0_subsystem():
    assert GET('/disk').json()[0]['subsystem'] == disk0[:-1]


def test_04_looking_disk0_number():
    assert GET('/disk').json()[0]['number'] == 0


def test_05_looking_disk0_identifier_and_serial_match():
    identifier_serial = GET('/disk').json()[0]['identifier'][8:]
    serial = GET('/disk').json()[0]['serial']
    assert identifier_serial == serial


def test_06_looking_for_disk1_was_created():
    assert GET('/disk').json()[1]['name'] == disk1


def test_07_looking_disk1_subsystem():
    assert GET('/disk').json()[1]['subsystem'] == disk1[:-1]


def test_08_looking_disk1_number():
    assert GET('/disk').json()[1]['number'] == 1


def test_09_looking_disk1_identifier_and_serial_match():
    identifier_serial = GET('/disk').json()[1]['identifier'][8:]
    serial = GET('/disk').json()[1]['serial']
    assert identifier_serial == serial


def test_10_looking_for_disk2_was_created():
    assert GET('/disk').json()[2]['name'] == disk2


def test_11_looking_disk2_subsystem():
    assert GET('/disk').json()[2]['subsystem'] == disk2[:-1]


def test_12_looking_disk2_number():
    assert GET('/disk').json()[2]['number'] == 2


def test_13_looking_disk2_identifier_and_serial_match():
    identifier_serial = GET('/disk').json()[2]['identifier'][8:]
    serial = GET('/disk').json()[2]['serial']
    assert identifier_serial == serial
