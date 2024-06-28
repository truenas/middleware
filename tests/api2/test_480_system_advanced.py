#!/usr/bin/env python3
# License: BSD

import os
import pytest
import sys
from pytest_dependency import depends
apifolder = os.getcwd()
sys.path.append(apifolder)
from middlewared.test.integration.utils import call, ssh
MOTD = 'FREENAS_MOTD'
SYSLOGLEVEL = "F_CRIT"


@pytest.fixture(scope='module')
def sysadv_dict():
    return {}


def test_01_system_advanced_get():
    results = call('system.advanced.config')
    assert results
    assert isinstance(results, dict)


def test_02_system_advanced_serial_port_choices(sysadv_dict):
    results = call('system.advanced.serial_port_choices')
    assert results
    sysadv_dict['serial_choices'] = [k for k in results]
    assert isinstance(results, dict)
    assert len(results) > 0


def test_03_system_advanced_set_serial_port(sysadv_dict):
    results = call('system.advanced.update', {
        'serialconsole': True,
        'serialport': sysadv_dict['serial_choices'][0],
    })
    assert results
    assert isinstance(results, dict)


def test_04_system_advanced_check_serial_port_using_api(sysadv_dict):
    results = call('system.advanced.config')
    assert results
    assert isinstance(results, dict)
    assert results['serialport'] == sysadv_dict['serial_choices'][0]


def test_05_system_advanced_check_serial_port_using_ssh(sysadv_dict, request):
    cmd = f'systemctl | grep "{sysadv_dict["serial_choices"][0]}"'
    results = ssh(cmd)
    assert results['result'] is True, results


def test_06_system_advanced_disable_serial_port():
    results = call('system.advanced.update', {
        'serialconsole': False,
    })
    assert results
    assert isinstance(results, dict)


def test_07_system_advanced_check_disabled_serial_port_using_ssh(sysadv_dict, request):
    results = ssh(f'grep "{sysadv_dict["serial_choices"][0]}" /boot/loader.conf.local')
    assert results['result'] is False, results


def test_08_system_advanced_set_motd():
    results = call('system.advanced.update', {
        'motd': MOTD,
    })
    assert results
    assert isinstance(results, dict)


def test_09_system_advanced_check_motd_using_api():
    results = call('system.advanced.config')
    assert results
    assert isinstance(results, dict)
    assert results['motd'] == MOTD


def test_10_system_advanced_check_motd_using_ssh(request):
    results = ssh(f'grep "{MOTD}" /etc/motd')
    assert results['result'] is True, results


def test_11_system_advanced_login_banner():
    results = call('system.advanced.update', {
        'login_banner': 'TrueNAS login banner.'
    })
    assert results
    results = call('system.advanced.config')
    assert results
    assert results['login_banner'] == "TrueNAS login banner"

    results = ssh('grep Banner /etc/ssh/sshd_config')
    assert results['result'] is True, results


def test_12_Setting_sysloglevel():
    results = call('system.advanced.update', {
        'sysloglevel': SYSLOGLEVEL
    })
    assert results


def test_13_Checking_sysloglevel_using_api():
    results = call('system.advanced.config')
    assert results
    assert results['sysloglevel'] == SYSLOGLEVEL
