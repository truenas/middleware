#!/usr/bin/env python3
# License: BSD

import os
import pytest
import sys
from pytest_dependency import depends
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, GET, SSH_TEST
from auto_config import user, password, ip, scale, dev_test
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skip for testing')
MOTD = 'FREENAS_MOTD'


@pytest.fixture(scope='module')
def sysadv_dict():
    return {}


def test_01_system_advanced_get():
    results = GET('/system/advanced/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict)


def test_02_system_advanced_serial_port_choices(sysadv_dict):
    results = GET('/system/advanced/serial_port_choices/')
    assert results.status_code == 200, results.text
    data = results.json()
    sysadv_dict['serial_choices'] = [k for k in data]
    assert isinstance(data, dict), data
    assert len(data) > 0, data


def test_03_system_advanced_set_serial_port(sysadv_dict):
    results = PUT('/system/advanced/', {
        'serialconsole': True,
        'serialport': sysadv_dict['serial_choices'][0],
    })
    assert results.status_code == 200, results.text
    data = results.json()
    assert isinstance(data, dict), data


def test_04_system_advanced_check_serial_port_using_api(sysadv_dict):
    results = GET('/system/advanced/')
    assert results.status_code == 200, results.text
    data = results.json()
    assert isinstance(data, dict)
    assert data['serialport'] == sysadv_dict['serial_choices'][0]


def test_05_system_advanced_check_serial_port_using_ssh(sysadv_dict, request):
    depends(request, ["ssh_password"], scope="session")
    if scale is True:
        cmd = f'dmesg | grep "{sysadv_dict["serial_choices"][0]}"'
    else:
        cmd = f'cat /boot/loader.conf.local | grep "{sysadv_dict["serial_choices"][0]}"'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results


def test_06_system_advanced_disable_serial_port():
    results = PUT('/system/advanced/', {
        'serialconsole': False,
    })
    assert results.status_code == 200, results.text
    data = results.json()
    assert isinstance(data, dict), data


def test_07_system_advanced_check_disabled_serial_port_using_ssh(sysadv_dict, request):
    depends(request, ["ssh_password"], scope="session")
    results = SSH_TEST(f'cat /boot/loader.conf.local | grep "{sysadv_dict["serial_choices"][0]}"', user, password, ip)
    assert results['result'] is False, results


def test_08_system_advanced_set_motd():
    results = PUT('/system/advanced/', {
        'motd': MOTD
    })
    assert results.status_code == 200, results.text
    data = results.json()
    assert isinstance(data, dict), data


def test_09_system_advanced_check_motd_using_api():
    results = GET('/system/advanced/')
    assert results.status_code == 200, results.text
    data = results.json()
    assert isinstance(data, dict)
    assert data['motd'] == MOTD


def test_10_system_advanced_check_motd_using_ssh(request):
    depends(request, ["ssh_password"], scope="session")
    results = SSH_TEST(f'cat /etc/motd | grep "{MOTD}"', user, password, ip)
    assert results['result'] is True, results
