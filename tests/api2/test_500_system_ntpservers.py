#!/usr/bin/env python3
# License: BSD

import os
import pytest
import sys
from pytest_dependency import depends
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import DELETE, GET, PUT, SSH_TEST
from auto_config import ntpServer, user, password, ip
from auto_config import dev_test
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skipping for test development testing')
CONFIG_FILE = '/etc/chrony/chrony.conf'


@pytest.fixture(scope='module')
def ntp_dict():
    return {}


def test_01_Changing_options_in_ntpserver():
    results = PUT('/system/ntpserver/id/1/', {
        'address': ntpServer,
        'burst': True,
        'iburst': True,
        'maxpoll': 10,
        'minpoll': 6,
        'prefer': True,
        'force': True})
    assert results.status_code == 200, results.text


def test_02_Check_ntpserver_configured_using_api(ntp_dict):
    results = GET('/system/ntpserver/?id=1')
    assert results.status_code == 200, results.text
    data = results.json()
    assert isinstance(data, list), data
    assert len(data) == 1, data
    assert data[0]['address'] == ntpServer, data


def test_03_Checking_ntpserver_configured_using_ssh(request):
    depends(request, ["ssh_password"], scope="session")
    cmd = f'fgrep "{ntpServer}" {CONFIG_FILE}'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results


def test_04_Check_ntpservers(ntp_dict):
    results = GET('/system/ntpserver/')
    assert results.status_code == 200, results.text
    data = results.json()
    assert isinstance(data, list), data
    ntp_dict['servers'] = {i['id']: i for i in data}


def test_05_Removing_non_AD_NTP_servers(ntp_dict):
    if len(ntp_dict['servers']) == 1:
        pytest.skip('Only one NTP server found')
    for k in list(ntp_dict['servers'].keys()):
        if k == 1:
            continue
        results = DELETE(f'/system/ntpserver/id/{k}/')
        assert results.status_code == 200, results.text
        ntp_dict['servers'].pop(k)


def test_06_Checking_ntpservers_num_configured_using_ssh(ntp_dict, request):
    depends(request, ["ssh_password"], scope="session")
    results = SSH_TEST(f'grep -R ^server {CONFIG_FILE}', user, password, ip)
    assert results['result'] is True, results
    assert len(results['output'].strip().split('\n')) == \
        len(ntp_dict['servers']), results['output']
