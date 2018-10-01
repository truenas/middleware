#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD

import pytest
import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import GET, POST

dataset = "tank/vmware"
url_dataset = "tank%2Fvmware"

vmw_credentials = pytest.mark.skipif(all(['VMWARE_HOST' in os.environ,
                                          'VMWARE_USERNAME' in os.environ,
                                          'VMWARE_PASSWORD' in os.environ]
                                         ) is False, reason="No credentials"
                                     )


@pytest.fixture(scope='module')
def data():
    return {}


def test_01_get_vmware_query():
    results = GET('/vmware/')
    assert results.status_code == 200
    assert isinstance(results.json(), list) is True


@vmw_credentials
def test_02_create_vmware(data):
    payload = {
        'hostname': os.environ['VMWARE_HOST'],
        'username': os.environ['VMWARE_USERNAME'],
        'password': os.environ['VMWARE_PASSWORD']
    }
    results = POST('/vmware/get_datastores/', payload)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict) is True, results.text
    data['vmid'] = results.json()
