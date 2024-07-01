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


def test_system_advanced_get():
    results = call('system.advanced.config')


def test_system_advanced_serial_port_choices(sysadv_dict):
    results = call('system.advanced.serial_port_choices')
    sysadv_dict['serial_choices'] = [k for k in results]
    assert len(results) > 0


def test_system_advanced_set_serial_port(sysadv_dict):
    results = call('system.advanced.update', {
        'serialconsole': True,
        'serialport': sysadv_dict['serial_choices'][0],
    })


def test_system_advanced_check_serial_port_using_api(sysadv_dict):
    results = call('system.advanced.config')
    assert results['serialport'] == sysadv_dict['serial_choices'][0]


def test_system_advanced_check_serial_port_using_ssh(sysadv_dict, request):
    cmd = f'systemctl | grep "{sysadv_dict["serial_choices"][0]}"'
    results = ssh(cmd)


def test_system_advanced_disable_serial_port():
    results = call('system.advanced.update', {
        'serialconsole': False,
    })


def test_system_advanced_check_disabled_serial_port_using_ssh(sysadv_dict, request):
    results = ssh(f'grep "{sysadv_dict["serial_choices"][0]}" /boot/loader.conf.local', complete_response=True)
    assert results['result'] is False, results


def test_system_advanced_set_motd():
    results = call('system.advanced.update', {
        'motd': MOTD,
    })


def test_system_advanced_check_motd_using_api():
    results = call('system.advanced.config')
    assert results['motd'] == MOTD


def test_system_advanced_check_motd_using_ssh(request):
    results = ssh(f'grep "{MOTD}" /etc/motd', complete_response=True)
    assert results['result'] is True, results


def test_system_advanced_login_banner():
    results = call('system.advanced.update', {
        'login_banner': 'TrueNAS login banner.'
    })
    results = call('system.advanced.config')
    assert results['login_banner'] == "TrueNAS login banner."
    results = ssh('grep Banner /etc/ssh/sshd_config')
    assert results['result'] is True, results


def test_Setting_sysloglevel():
    results = call('system.advanced.update', {
        'sysloglevel': SYSLOGLEVEL
    })
    

def test_Checking_sysloglevel_using_api():
    results = call('system.advanced.config')
    assert results['sysloglevel'] == SYSLOGLEVEL
