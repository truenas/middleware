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
    assert len(GET('/disk/').json()) == 3


def test_02_looking_for_disk0_was_created():
    assert GET('/disk?number=0').json()[0]['name'] == disk0


def test_03_looking_disk0_subsystem():
    assert GET('/disk?number=0').json()[0]['subsystem'] == disk0[:-1]


def test_04_looking_disk0_number():
    assert GET('/disk?number=0').json()[0]['number'] == 0


def test_05_looking_disk0_identifier_and_serial_match():
    identifier_serial = GET('/disk?number=0').json()[0]['identifier'][8:]
    serial = GET('/disk?number=0').json()[0]['serial']
    assert identifier_serial == serial


def test_06_looking_for_disk1_was_created():
    global DISK_ID
    result = GET('/disk?number=1')
    DISK_ID = result.json()[0]['identifier']
    assert result.json()[0]['name'] == disk1


def test_07_looking_disk1_subsystem():
    assert GET('/disk?number=1').json()[0]['subsystem'] == disk1[:-1]


def test_08_looking_disk1_number():
    assert GET('/disk?number=1').json()[0]['number'] == 1


def test_09_looking_disk1_identifier_and_serial_match():
    identifier_serial = GET('/disk?number=1').json()[0]['identifier'][8:]
    serial = GET('/disk?number=1').json()[0]['serial']
    assert identifier_serial == serial


def test_10_looking_for_disk2_was_created():
    assert GET('/disk?number=2').json()[0]['name'] == disk2


def test_11_looking_disk2_subsystem():
    assert GET('/disk?number=2').json()[0]['subsystem'] == disk2[:-1]


def test_12_looking_disk2_number():
    assert GET('/disk?number=2').json()[0]['number'] == 2


def test_13_looking_disk2_identifier_and_serial_match():
    identifier_serial = GET('/disk?number=2').json()[0]['identifier'][8:]
    serial = GET('/disk?number=2').json()[0]['serial']
    assert identifier_serial == serial


def test_14_update_disk_description():
    updated_description = 'Updated description'
    result = PUT(
        f'/disk/id/{DISK_ID}/', {
            'description': updated_description
        }
    )
    assert result.json()['description'] == updated_description, result.text


def test_15_update_disk_password():
    new_passwd = 'freenas'
    result = PUT(
        f'/disk/id/{DISK_ID}', {
            'passwd': new_passwd
        }
    )
    assert result.json()['passwd'] == new_passwd


def test_16_get_encrypted_disks():
    # TODO: create a volume with encryption enabled and then test the
    # encrypted disk. Will complete as soon as we have implementation of pool
    # create in middlewared
    pass


def test_17_get_decrypted_disks():
    # TODO: Complete after test 05
    pass


def test_18_get_unused_disks():
    result = POST('/disk/get_unused/', False)
    assert isinstance(result.json(), list), result.text


def test_19_perform_wipe_on_unused_disk():
    unused_disks = POST('/disk/get_unused/', False)
    if len(unused_disks.json()) > 0:
        print('in if')
        result = POST('/disk/wipe/', {
            'dev': unused_disks.json()[0]['name'],
            'mode': 'QUICK'
        })
        assert result.status_code == 200
