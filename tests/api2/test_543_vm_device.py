#!/usr/bin/env python3

# Author: Eric Turgeon
# License: BSD

import pytest
import sys
import os
from pytest_dependency import depends
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import GET, POST, DELETE
from auto_config import dev_test, ha
from middlewared.test.integration.assets.pool import dataset
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skip for development testing')

support_virtualization = GET('/vm/supports_virtualization/', controller_a=ha).json()


@pytest.fixture(scope='module')
def data():
    return {}


def test_01_vm_disk_choices(request):
    depends(request, ["pool_04"], scope="session")
    with dataset('test zvol', {'type': 'VOLUME', 'volsize': 1024000}) as ds:
        results = GET('/vm/device/disk_choices')
        assert isinstance(results.json(), dict), results.json()
        assert results.json().get(f'/dev/zvol/{ds.replace(" ", "+")}') == f'{ds}'


# Only run if the system support virtualization
if support_virtualization:

    def test_02_creating_a_vm_for_device_testing(data):
        global payload
        payload = {
            'name': 'devicetest',
            'description': 'desc',
            'vcpus': 1,
            'memory': 512,
            'bootloader': 'UEFI',
            'autostart': False,
        }
        results = POST('/vm/', payload)
        assert results.status_code == 200, results.text
        data['vmid'] = results.json()['id']

    def test_02_delete_vm(data,):
        results = DELETE(f'/vm/id/{data["vmid"]}/')
        assert results.status_code == 200, results.text
