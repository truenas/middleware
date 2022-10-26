#!/usr/bin/env python3

import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)

import pytest
from functions import GET, SSH_TEST, make_ws_request
from auto_config import ha, user, password, dev_test
from pytest_dependency import depends

# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skipping for test development testing')
if ha and "virtual_ip" in os.environ:
    ip = os.environ["virtual_ip"]
else:
    from auto_config import ip

from middlewared.test.integration.utils import call


@pytest.mark.dependency(name='hactl_install_dir')
def test_01_check_hactl_installed(request):
    rv = SSH_TEST('which hactl', user, password, ip)
    assert rv['output'].strip() == '/usr/local/sbin/hactl', rv['output']


@pytest.mark.dependency(name='hactl_status')
def test_02_check_hactl_status(request):
    depends(request, ['hactl_install_dir'])
    rv = SSH_TEST('hactl', user, password, ip)
    output = rv['output'].strip()
    if ha:
        for i in ('Node status:', 'This node serial:', 'Other node serial:', 'Failover status:'):
            assert i in output, output
    else:
        assert 'Not an HA node' in output, output


@pytest.mark.dependency(name='hactl_takeover')
def test_03_check_hactl_takeover(request):
    # integration tests run against the master node (at least they should...)
    depends(request, ['hactl_status'])
    rv = SSH_TEST('hactl takeover', user, password, ip)
    output = rv['output'].strip()
    if ha:
        assert 'This command can only be run on the standby node.' in output, output
    else:
        assert 'Not an HA node' in output, output


@pytest.mark.dependency(name='hactl_enable')
def test_04_check_hactl_enable(request):
    # integration tests run against the master node (at least they should...)
    depends(request, ['hactl_takeover'])
    rv = SSH_TEST('hactl enable', user, password, ip)
    output = rv['output'].strip()
    if ha:
        assert 'Failover already enabled.' in output, output
    else:
        assert 'Not an HA node' in output, output


def test_05_check_hactl_disable(request):
    # integration tests run against the master node (at least they should...)
    depends(request, ['hactl_enable'])
    rv = SSH_TEST('hactl disable', user, password, ip)
    output = rv['output'].strip()
    if ha:
        assert 'Failover disabled.' in output, output

        rv = make_ws_request(ip, {'msg': 'method', 'method': 'failover.config', 'params': []})
        assert isinstance(rv['result'], dict), rv['result']
        assert rv['result']['disabled'] is True, rv['result']

        rv = SSH_TEST('hactl enable', user, password, ip)
        output = rv['output'].strip()
        assert 'Failover enabled.' in output, output

        rv = make_ws_request(ip, {'msg': 'method', 'method': 'failover.config', 'params': []})
        assert isinstance(rv['result'], dict), rv['result']
        assert rv['result']['disabled'] is False, rv['result']
    else:
        assert 'Not an HA node' in output, output


def test_06_test_failover_get_ips():
    results = GET('/failover/get_ips', controller_a=ha)
    assert results.status_code == 200, results.text
    rv = results.json()
    assert (isinstance(rv, list)), rv
    if ha:
        assert rv


if ha:
    def test_07_failover_replicate():
        old_ns = call('network.configuration.config')['nameserver3']
        new_ns = '1.1.1.1'
        try:
            call('network.configuration.update', {'nameserver3': new_ns})

            remote = call('failover.call_remote', 'network.configuration.config')
            assert remote['nameserver3'] == new_ns
            assert remote['state']['nameserver3'] == new_ns
        finally:
            call('network.configuration.update', {'nameserver3': old_ns})
            remote = call('failover.call_remote', 'network.configuration.config')
            assert remote['nameserver3'] == old_ns
            assert remote['state']['nameserver3'] == old_ns
