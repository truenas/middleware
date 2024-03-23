#!/usr/bin/env python3

# Author: Eric Turgeon
# License: BSD

import pytest
import sys
import os
from pytest_dependency import depends
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import GET, POST, PUT, DELETE
from auto_config import ha, pool_name, ip
from middlewared.test.integration.assets.pool import dataset

support_virtualization = GET('/vm/supports_virtualization/', controller_a=ha).json()
DISK_DATASET = f'{pool_name}/disks'
DISK_DATASET_URL = DISK_DATASET.replace('/', '%2F')
DISK_DATASET_PATH = f'/mnt/{DISK_DATASET}'
CDROM_DATASET = f'{pool_name}/cdrom'
CDROM_DATASET_URL = CDROM_DATASET.replace('/', '%2F')
CDROM_DATASET_PATH = f'/mnt/{CDROM_DATASET}'
DEVICE = {'disk_id': 'DISK', 'display_id': 'DISPLAY', 'cdrom_id': 'CDROM'}
pytestmark = pytest.mark.vm


@pytest.fixture(scope='module')
def data():
    return {}


def test_01_vm_disk_choices(request):
    with dataset('test zvol', {'type': 'VOLUME', 'volsize': 1048576}) as ds:
        results = GET('/vm/device/disk_choices')
        assert isinstance(results.json(), dict), results.json()
        assert results.json().get(f'/dev/zvol/{ds.replace(" ", "+")}') == f'{ds}'


@pytest.mark.parametrize('bind', ['0.0.0.0', '::', ip])
def test_02_verify_vm_device_bind_choices(bind):
    results = GET('/vm/device/bind_choices/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    assert results.json()[bind] == bind, results.text


def test_03_verify_vm_device_iommu_enabled_return_a_boolean():
    results = GET('/vm/device/iommu_enabled/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), bool), results.text


def test_04_get_vm_device_iotype_choices():
    results = GET('/vm/device/iotype_choices/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    assert results.json()['NATIVE'] == 'NATIVE', results.text


def test_05_verify_vm_device_nic_attach_choices():
    interface_results = GET('/interface/')
    assert interface_results.status_code == 200, interface_results.text
    assert isinstance(interface_results.json(), list), interface_results.text

    nic_results = GET('/vm/device/nic_attach_choices/')
    assert nic_results.status_code == 200, nic_results.text
    assert isinstance(nic_results.json(), dict), nic_results.text

    for interface in interface_results.json():
        assert nic_results.json()[interface['name']] == interface['name'], nic_results.text


def test_06_get_vm_device_usb_controller_choices():
    results = GET('/vm/device/usb_controller_choices/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    assert results.json()['qemu-xhci'] == 'qemu-xhci', results.text


# Only run if the system support virtualization
if support_virtualization:

    def test_07_get_vm_passthrough_device_choices():
        results = GET('/vm/device/passthrough_device_choices/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text

    def test_08_get_vm_device_pptdev_choices():
        results = GET('/vm/device/pptdev_choices/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text

    def test_09_get_vm_device_usb_passthrough_choices():
        results = GET('/vm/device/usb_passthrough_choices/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text

    @pytest.mark.dependency(name='DISK_CDROM_DATASET')
    def test_10_create_dataset_for_disk_and_cdrom(request):
        results = POST("/pool/dataset/", payload={"name": DISK_DATASET})
        assert results.status_code == 200, results.text

        results = POST("/pool/dataset/", payload={"name": CDROM_DATASET})
        assert results.status_code == 200, results.text

    @pytest.mark.dependency(name='VM_FOR_DEVICE')
    def test_11_creating_a_vm_for_device_testing(data, request):
        depends(request, ["DISK_CDROM_DATASET"])
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
        assert isinstance(results.json(), dict), results.text
        data['vmid'] = results.json()['id']

    @pytest.mark.dependency(name='DISK_DEVICE')
    def test_12_create_a_disk_device(data, request):
        depends(request, ["VM_FOR_DEVICE"])
        payload = {
            'dtype': 'DISK',
            'vm': data['vmid'],
            'attributes': {'path': DISK_DATASET_PATH}
        }
        results = POST('/vm/device/', payload)
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        data['disk_id'] = results.json()['id']

    def test_13_verify_disk_device_by_id(data, request):
        depends(request, ["DISK_DEVICE"])
        results = GET(f'/vm/device/id/{data["disk_id"]}/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        assert results.json()['dtype'] == 'DISK', results.text
        assert results.json()['vm'] == data["vmid"], results.text
        assert results.json()['attributes']['path'] == DISK_DATASET_PATH, results.text

    @pytest.mark.dependency(name='DISPLAY_DEVICE')
    def test_14_create_a_display_device(data, request):
        depends(request, ["VM_FOR_DEVICE"])
        payload = {
            'dtype': 'DISPLAY',
            'vm': data['vmid'],
            'attributes': {'resolution': '1920x1080'}
        }
        results = POST('/vm/device/', payload)
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        data['display_id'] = results.json()['id']

    def test_15_verify_diplay_device_by_id(data, request):
        depends(request, ["DISPLAY_DEVICE"])
        results = GET(f'/vm/device/id/{data["display_id"]}/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        assert results.json()['dtype'] == 'DISPLAY', results.text
        assert results.json()['vm'] == data["vmid"], results.text
        assert results.json()['attributes']['resolution'] == '1920x1080', results.text

    @pytest.mark.dependency(name='CDROM_DEVICE')
    def test_16_create_a_cdrom_device(data, request):
        depends(request, ["VM_FOR_DEVICE"])
        payload = {
            'dtype': 'CDROM',
            'vm': data["vmid"],
            'attributes': {'path': CDROM_DATASET_PATH}
        }
        results = POST('/vm/device/', payload)
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        data['cdrom_id'] = results.json()['id']

    def test_17_verify_cdrom_device_by_id(data, request):
        depends(request, ["CDROM_DEVICE"])
        results = GET(f'/vm/device/id/{data["cdrom_id"]}/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        assert results.json()['dtype'] == 'CDROM', results.text
        assert results.json()['vm'] == data["vmid"], results.text
        assert results.json()['attributes']['path'] == CDROM_DATASET_PATH, results.text

    def test_18_verify_vm_device_list(request):
        depends(request, ["DISK_DEVICE"])
        results = GET('/vm/device/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), list), results.text
        assert len(results.json()) > 0, results.text

    @pytest.mark.parametrize('device_id', list(DEVICE.keys()))
    def test_19_get_vm_device_instance(data, device_id, request):
        depends(request, ["VM_FOR_DEVICE"])
        results = POST('/vm/device/get_instance/', {'id': data[device_id]})
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        assert results.json()['dtype'] == DEVICE[device_id], results.text
        assert results.json()['vm'] == data["vmid"], results.text

    def test_20_get_vm_display_devices(data, request):
        depends(request, ["DISPLAY_DEVICE"])
        results = POST('/vm/get_display_devices/', data["vmid"])
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), list), results.text
        assert results.json()[0]['vm'] == data["vmid"], results.json()

    def test_21_get_usb_passthrough_device_info(data, request):
        depends(request, ["VM_FOR_DEVICE"])
        usb_devices = list(GET('/vm/device/usb_passthrough_choices/').json().keys())
        results = POST('/vm/device/usb_passthrough_device/', usb_devices[0])
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text

    def test_22_change_display_resolution(data, request):
        depends(request, ["DISPLAY_DEVICE"])
        payload = {
            'attributes': {'resolution': '1280x720'}
        }
        results = PUT(f'/vm/device/id/{data["display_id"]}/', payload)
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        assert results.json()['attributes']['resolution'] == '1280x720', results.text
        assert results.json()['vm'] == data["vmid"], results.json()

    def test_23_verify_display_resolution(data, request):
        depends(request, ["DISPLAY_DEVICE"])
        results = GET(f'/vm/device/id/{data["display_id"]}/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        assert results.json()['attributes']['resolution'] == '1280x720', results.text
        assert results.json()['vm'] == data["vmid"], results.json()

    @pytest.mark.dependency(name='NIC_DEVICE')
    def test_24_create_a_nic_device(data, request):
        depends(request, ["VM_FOR_DEVICE"])
        payload = {
            'dtype': 'NIC',
            'vm': data["vmid"],
            'attributes': {}
        }
        results = POST('/vm/device/', payload)
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        data['nic_id'] = results.json()['id']

    def test_25_verify_nic_device_by_id(data, request):
        depends(request, ["NIC_DEVICE"])
        results = GET(f'/vm/device/id/{data["nic_id"]}/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        assert results.json()['dtype'] == 'NIC', results.text
        assert results.json()['vm'] == data["vmid"], results.text

    def test_26_add_a_nic_attach_nic_device(data, request):
        depends(request, ["NIC_DEVICE"])
        global nic_list
        nic_list = list(GET('/vm/device/nic_attach_choices/').json().keys())
        payload = {
            'attributes': {'nic_attach': nic_list[0]}
        }
        results = PUT(f'/vm/device/id/{data["nic_id"]}/', payload)
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text

    def test_27_verify_nic_device_nic_attach_attributes(data, request):
        depends(request, ["NIC_DEVICE"])
        results = GET(f'/vm/device/id/{data["nic_id"]}/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        assert results.json()['attributes']['nic_attach'] == nic_list[0], results.text

    @pytest.mark.parametrize('device_id', list(DEVICE.keys()))
    def test_28_delete_devices(device_id, data, request):
        depends(request, ["DISK_DEVICE"])
        results = DELETE(f'/vm/device/id/{data[device_id]}/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), bool), results.text

    def test_29_verify_vm_device_list_is_not_empty_before_deleting_the_vm(data, request):
        depends(request, ["VM_FOR_DEVICE"])
        results = GET(f'/vm/device/?vm={data["vmid"]}')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), list), results.text
        assert len(results.json()) > 0, results.text

    def test_30_delete_the_vm(data, request):
        depends(request, ["VM_FOR_DEVICE"])
        results = DELETE(f'/vm/id/{data["vmid"]}/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), bool), results.text

    def test_31_verify_vm_device_list_is_empty_after_deleting_the_vm(data, request):
        depends(request, ["VM_FOR_DEVICE"])
        results = GET(f'/vm/device/?vm={data["vmid"]}')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), list), results.text
        assert len(results.json()) == 0, results.text

    def test_32_delete_disk_and_cdrom_dataset(request):
        depends(request, ["DISK_CDROM_DATASET"])
        results = DELETE(f"/pool/dataset/id/{DISK_DATASET_URL}/")
        assert results.status_code == 200, results.text

        results = DELETE(f"/pool/dataset/id/{CDROM_DATASET_URL}/")
        assert results.status_code == 200, results.text
