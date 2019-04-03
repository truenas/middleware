#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD

import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from auto_config import disk1, disk2
from functions import GET, POST, PUT

disk0 = disk1[:-1] + '0'
RunTest = True
TestName = "get disk information"
DISK_ID = None


def test_01_verifying_that_the_installer_created_all_disk():
    results = GET('/disk/')
    assert results.status_code == 200, results.text
    assert len(results.json()) == 3


def test_02_looking_for_disk0_was_created():
    results = GET('/disk/')
    assert results.status_code == 200, results.text
    assert results.json()[0]['name'] == disk0


def test_03_looking_disk0_subsystem():
    results = GET('/disk?number=0')
    assert results.status_code == 200, results.text
    assert results.json()[0]['subsystem'] == disk0[:-1]


def test_04_looking_disk0_number():
    results = GET('/disk?number=0')
    assert results.status_code == 200, results.text
    assert results.json()[0]['number'] == 0


def test_05_looking_disk0_identifier_and_serial_match():
    results = GET('/disk?number=0')
    assert results.status_code == 200, results.text
    identifier_serial = results.json()[0]['identifier'][8:]
    serial = results.json()[0]['serial']
    assert identifier_serial == serial


def test_06_looking_for_disk1_was_created():
    global DISK_ID
    results = GET('/disk?number=1')
    assert results.status_code == 200, results.text
    DISK_ID = results.json()[0]['identifier']
    assert results.json()[0]['name'] == disk1, results.text


def test_07_looking_disk1_subsystem():
    results = GET('/disk?number=1')
    assert results.status_code == 200, results.text
    assert results.json()[0]['subsystem'] == disk1[:-1]


def test_08_looking_disk1_number():
    results = GET('/disk?number=1')
    assert results.status_code == 200, results.text
    assert results.json()[0]['number'] == 1


def test_09_looking_disk1_identifier_and_serial_match():
    results = GET('/disk?number=1')
    assert results.status_code == 200, results.text
    identifier_serial = results.json()[0]['identifier'][8:]
    serial = results.json()[0]['serial']
    assert identifier_serial == serial, results.text


def test_10_looking_for_disk2_was_created():
    results = GET('/disk?number=2')
    assert results.status_code == 200, results.text
    assert results.json()[0]['name'] == disk2


def test_11_looking_disk2_subsystem():
    results = GET('/disk?number=2')
    assert results.status_code == 200, results.text
    assert results.json()[0]['subsystem'] == disk2[:-1]


def test_12_looking_disk2_number():
    results = GET('/disk?number=2')
    assert results.status_code == 200, results.text
    assert results.json()[0]['number'] == 2


def test_13_looking_disk2_identifier_and_serial_match():
    results = GET('/disk?number=2')
    assert results.status_code == 200, results.text
    identifier_serial = results.json()[0]['identifier'][8:]
    serial = results.json()[0]['serial']
    assert identifier_serial == serial


def test_14_update_disk_description():
    updated_description = 'Updated description'
    results = PUT(
        f'/disk/id/{DISK_ID}/', {
            'description': updated_description
        }
    )
    assert results.status_code == 200, results.text
    assert results.json()['description'] == updated_description, results.text


def test_15_update_disk_password():
    new_passwd = 'freenas'
    results = PUT(
        f'/disk/id/{DISK_ID}', {
            'passwd': new_passwd
        }
    )
    assert results.status_code == 200, results.text
    assert results.json()['passwd'] == new_passwd


def test_16_get_encrypted_disks():
    # TODO: create a volume with encryption enabled and then test the
    # encrypted disk. Will complete as soon as we have implementation of pool
    # create in middlewared
    pass


def test_17_get_decrypted_disks():
    # TODO: Complete after test 05
    pass


def test_18_get_unused_disks():
    results = POST('/disk/get_unused/', False)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list), results.text


def test_19_perform_wipe_on_unused_disk():
    unused_disks = POST('/disk/get_unused/', False)
    if len(unused_disks.json()) > 0:
        print('in if')
        results = POST('/disk/wipe/', {
            'dev': unused_disks.json()[0]['name'],
            'mode': 'QUICK'
        })
        assert results.status_code == 200, results.text
