#!/usr/bin/env python3
# License: BSD

import os
import sys
import time

import pytest
from pytest_dependency import depends

apifolder = os.getcwd()
sys.path.append(apifolder)
from auto_config import badNtpServer, dev_test, ip, password, user
from functions import DELETE, GET, POST, PUT, SSH_TEST

# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skipping for test development testing')
CONFIG_FILE = '/etc/chrony/chrony.conf'
from middlewared.test.integration.utils import call


class TestBadNtpServer:

    @pytest.fixture(scope='class')
    def ntp_dict(self):
        # read the current config to restore when done
        # we will remove all but the lowest id item
        results = GET('/system/ntpserver')
        assert results.status_code == 200, results.text

        orig_ntp_servers = results.json()
        lowest_id = min([ntp['id'] for ntp in orig_ntp_servers])
        try:
            yield {'lowest_id': lowest_id}
        finally:
            for ntp in orig_ntp_servers:
                ident = ntp['id']
                del ntp['id']
                ntp['force'] = True

                if ident == lowest_id:
                    result = PUT(f'/system/ntpserver/id/{ident}/', ntp)
                else:
                    result = POST('/system/ntpserver', ntp)
                assert result.status_code == 200, result.text

    def test_01_Changing_options_in_ntpserver(self, ntp_dict):
        ident = ntp_dict['lowest_id']
        results = PUT(f'/system/ntpserver/id/{ident}/', {
            'address': badNtpServer,
            'burst': True,
            'iburst': True,
            'maxpoll': 10,
            'minpoll': 6,
            'prefer': True,
            'force': True})
        assert results.status_code == 200, results.text

    def test_02_Check_ntpserver_configured_using_api(self, ntp_dict):
        ident = ntp_dict['lowest_id']
        results = GET(f'/system/ntpserver/?id={ident}')
        assert results.status_code == 200, results.text
        data = results.json()
        assert isinstance(data, list), data
        assert len(data) == 1, data
        assert data[0]['address'] == badNtpServer, data

    def test_03_Checking_ntpserver_configured_using_ssh(self, request):
        cmd = f'fgrep "{badNtpServer}" {CONFIG_FILE}'
        results = SSH_TEST(cmd, user, password, ip)
        assert results['result'] is True, results

    def test_04_Check_ntpservers(self, ntp_dict):
        results = GET('/system/ntpserver/')
        assert results.status_code == 200, results.text
        data = results.json()
        assert isinstance(data, list), data
        ntp_dict['servers'] = {i['id']: i for i in data}

    def test_05_Removing_non_AD_NTP_servers(self, ntp_dict):
        ident = ntp_dict['lowest_id']
        if len(ntp_dict['servers']) == 1:
            pytest.skip('Only one NTP server found')
        for k in list(ntp_dict['servers'].keys()):
            if k == ident:
                continue
            results = DELETE(f'/system/ntpserver/id/{k}/')
            assert results.status_code == 200, results.text
            ntp_dict['servers'].pop(k)

    def test_06_Checking_ntpservers_num_configured_using_ssh(self, ntp_dict, request):
        results = SSH_TEST(f'grep -R ^server {CONFIG_FILE}', user, password, ip)
        assert results['result'] is True, results
        assert len(results['output'].strip().split('\n')) == \
            len(ntp_dict['servers']), results['output']

    def test_07_check_alert_set(self, ntp_dict):
        # Run the NTPHealthCheckAlertClass and ensure it has an alert
        alerts = call('alert.run_source', 'NTPHealthCheck')
        assert len(alerts) == 1, alerts
        assert alerts[0]['args']['reason'].startswith("No Active NTP peers"), alerts


def test_08_check_alert_clear():
    # Now that the original NTP servers have been restored, check the alerts are gone
    # Give some retries to allow the daemon sync with the sources
    retries = 10
    while retries > 0:
        retries -= 1
        alerts = call('alert.run_source', 'NTPHealthCheck')
        if len(alerts) == 0:
            break
        time.sleep(2)
    assert len(alerts) == 0, alerts
