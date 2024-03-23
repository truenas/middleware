#!/usr/bin/env python3

# Author: Eric Turgeon
# License: BSD

import pytest
import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import GET, POST, PUT
from auto_config import ha
RunTest = True
TestName = "get disk information"
DISK_ID = None
pytestmark = pytest.mark.disk

disk_list = list(POST('/device/get_info/', 'DISK', controller_a=ha).json().keys())


def test_01_verifying_that_the_installer_created_all_disk():
    results = GET('/disk/')
    assert results.status_code == 200, results.text
    assert len(results.json()) == len(disk_list)


@pytest.mark.parametrize('disk', disk_list)
def test_02_looking_for_disk(disk):
    results = GET(f'/disk?name={disk}')
    assert results.status_code == 200, results.text
    assert results.json()[0]['name'] == disk


@pytest.mark.parametrize('disk', disk_list)
def test_03_looking_subsystem(disk):
    results = GET(f'/disk?name={disk}')
    assert results.status_code == 200, results.text
    assert results.json()[0]['subsystem'] == 'scsi'


@pytest.mark.parametrize('disk', disk_list)
def test_04_looking_number(disk):
    results = GET(f'/disk?name={disk}')
    assert results.status_code == 200, results.text
    assert isinstance(results.json()[0]['number'], int), results.text


@pytest.mark.parametrize('disk', disk_list)
def test_05_looking_disk0_identifier_and_serial_match(disk):
    results = GET(f'/disk?name={disk}')
    assert results.status_code == 200, results.text
    identifier_serial = results.json()[0]['identifier']
    serial = results.json()[0]['serial']
    assert serial in identifier_serial, results.text


def test_06_get_for_disk1_id():
    global DISK_ID
    results = GET(f'/disk?name={disk_list[1]}')
    assert results.status_code == 200, results.text
    DISK_ID = results.json()[0]['identifier']


def test_07_update_disk_description():
    updated_description = 'Updated description'
    results = PUT(
        f'/disk/id/{DISK_ID}/', {
            'description': updated_description
        }
    )
    assert results.status_code == 200, results.text
    assert results.json()['description'] == updated_description, results.text


def test_08_update_disk_password():
    new_passwd = 'freenas'
    results = PUT(
        f'/disk/id/{DISK_ID}', {
            'passwd': new_passwd
        }
    )
    assert results.status_code == 200, results.text
    results = GET(
        '/disk', payload={
            'query-filters': [['identifier', '=', DISK_ID]],
            'query-options': {'extra': {'passwords': True}},
        }
    )
    assert results.status_code == 200, results.text
    assert results.json()[0]['passwd'] == new_passwd


def test_09_get_unused_disks():
    results = POST('/disk/get_unused/', False)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list), results.text


def test_10_perform_wipe_on_unused_disk():
    unused_disks = POST('/disk/get_unused/', False)
    if len(unused_disks.json()) > 0:
        print('in if')
        results = POST('/disk/wipe/', {
            'dev': unused_disks.json()[0]['name'],
            'mode': 'QUICK'
        })
        assert results.status_code == 200, results.text
