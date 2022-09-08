#!/usr/bin/env python3

import sys
import os
import pytest
apifolder = os.getcwd()
sys.path.append(apifolder)

from functions import SSH_TEST
from auto_config import ha, user, password
from pytest_dependency import depends
from auto_config import dev_test

if ha and "virtual_ip" in os.environ:
    ip = os.environ["virtual_ip"]
else:
    from auto_config import ip

# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skipping for test development testing')


@pytest.mark.dependency(name='hactl_install_dir')
def test_01_check_hactl_installed(request):
    rv = SSH_TEST('which hactl', user, password, ip)
    assert rv['output'].strip() == '/usr/local/sbin/hactl', rv['output']


def test_02_check_hactl_output(request):
    depends(request, ['hactl_install_dir'])
    rv = SSH_TEST('hactl', user, password, ip)
    output = rv['output'].strip()
    if ha:
        for i in ('Node status:', 'This node serial:', 'Other node serial:', 'Failover status:'):
            assert i in output, output
    else:
        assert 'Not an HA node' in output, output
