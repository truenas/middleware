import dataclasses
import time

import pytest
from pytest_dependency import depends

from auto_config import pool_name
from middlewared.test.integration.utils import call
from middlewared.test.integration.assets.pool import dataset


@dataclasses.dataclass
class VmAssets:
    # probably best to keep this module
    # to only creating 1 VM, since the
    # functionality can be tested on 1
    # and creating > 1 nested VMs incurs
    # an ever-increasing perf penalty in
    # test infrastructure
    VM_NAMES = ['vm01']
    VM_INFO = dict()
    VM_DEVICES = dict()


@pytest.mark.dependency(name='VIRT_SUPPORTED')
def test_001_is_virtualization_supported():
    if not call('vm.virtualization_details')['supported']:
        pytest.skip('Virtualization not supported')
    elif call('failover.licensed'):
        pytest.skip('Virtualization not supported on HA')


@pytest.mark.parametrize(
    'info',
    [
        {'method': 'vm.flags', 'type': dict, 'keys': ('intel_vmx', 'amd_rvi')},
        {'method': 'vm.cpu_model_choices', 'type': dict, 'keys': ('EPYC',)},
        {'method': 'vm.bootloader_options', 'type': dict, 'keys': ('UEFI', 'UEFI_CSM')},
        {'method': 'vm.get_available_memory', 'type': int},
        {'method': 'vm.guest_architecture_and_machine_choices', 'type': dict, 'keys': ('i686', 'x86_64')},
        {'method': 'vm.maximum_supported_vcpus', 'type': int},
        {'method': 'vm.port_wizard', 'type': dict, 'keys': ('port', 'web')},
        {'method': 'vm.random_mac', 'type': str},
        {'method': 'vm.resolution_choices', 'type': dict, 'keys': ('1920x1200', '640x480')},
        {'method': 'vm.device.bind_choices', 'type': dict, 'keys': ('0.0.0.0', '::')},
        {'method': 'vm.device.iommu_enabled', 'type': bool},
        {'method': 'vm.device.iotype_choices', 'type': dict, 'keys': ('NATIVE',)},
        {'method': 'vm.device.nic_attach_choices', 'type': dict},
        {'method': 'vm.device.usb_controller_choices', 'type': dict, 'keys': ('qemu-xhci',)},
        {'method': 'vm.device.usb_passthrough_choices', 'type': dict},
        {'method': 'vm.device.passthrough_device_choices', 'type': dict},
        {'method': 'vm.device.pptdev_choices', 'type': dict}
    ],
    ids=lambda x: x['method']
)
def test_002_vm_endpoint(info, request):
    """
    Very basic behavior of various VM endpoints. Ensures they
    return without error and that the type of response is what
    we expect. If a dict is returned, we check that top-level
    keys exist
    """
    depends(request, ['VIRT_SUPPORTED'])
    rv = call(info['method'])
    assert isinstance(rv, info['type'])
    if (keys := info.get('keys')):
        assert all((i in rv for i in keys))


@pytest.mark.parametrize('disk_name', ['test zvol'])
def test_003_verify_disk_choice(disk_name):
    with dataset(disk_name, {'type': 'VOLUME', 'volsize': 1048576, 'sparse': True}) as ds:
        assert call('vm.device.disk_choices').get(f'/dev/zvol/{ds.replace(" ", "+")}') == ds


@pytest.mark.parametrize('vm_name', VmAssets.VM_NAMES)
@pytest.mark.dependency(name='VM_CREATED')
def test_010_create_vm(vm_name, request):
    depends(request, ['VIRT_SUPPORTED'])
    vm_payload = {
        'name': vm_name,
        'description': f'{vm_name} description',
        'vcpus': 1,
        'memory': 512,
        'bootloader': 'UEFI',
        'autostart': False,
    }
    vm = call('vm.create', vm_payload)
    qry = call('vm.query', [['id', '=', vm['id']]], {'get': True})
    assert all((vm_payload[key] == qry[key] for key in vm_payload))
    VmAssets.VM_INFO.update({qry['name']: {'query_response': qry}})


@pytest.mark.parametrize('device', ['DISK', 'DISPLAY', 'NIC'])
@pytest.mark.dependency(name='ADD_DEVICES_TO_VM')
def test_011_add_devices_to_vm(device, request):
    depends(request, ['VM_CREATED'])
    for vm_name, info in VmAssets.VM_INFO.items():
        if vm_name not in VmAssets.VM_DEVICES:
            VmAssets.VM_DEVICES[vm_name] = dict()

        dev_info = {
            'dtype': device,
            'vm': info['query_response']['id'],
        }
        if device == 'DISK':
            zvol_name = f'{pool_name}/{device}_for_{vm_name}'
            dev_info.update({
                'attributes': {
                    'create_zvol': True,
                    'zvol_name': zvol_name,
                    'zvol_volsize': 1048576
                }
            })
        elif device == 'DISPLAY':
            dev_info.update({'attributes': {'resolution': '1024x768', 'password': 'displaypw'}})
        elif device == 'NIC':
            for nic_name in call('vm.device.nic_attach_choices'):
                dev_info.update({'attributes': {'nic_attach': nic_name}})
                break
        else:
            assert False, f'Unhandled device type: ({device!r})'

        info = call('vm.device.create', dev_info)
        VmAssets.VM_DEVICES[vm_name].update({device: info})
        # only adding these devices to 1 VM
        break


@pytest.mark.parametrize('vm_name', VmAssets.VM_NAMES)
def test_012_verify_devices_for_vm(vm_name, request):
    depends(request, ['ADD_DEVICES_TO_VM'])
    for device, info in VmAssets.VM_DEVICES[vm_name].items():
        qry = call('vm.device.query', [['id', '=', info['id']]], {'get': True})
        assert qry['dtype'] == device
        assert qry['vm'] == VmAssets.VM_INFO[vm_name]['query_response']['id']
        assert qry['attributes'] == VmAssets.VM_DEVICES[vm_name][device]['attributes']


@pytest.mark.parametrize('vm_name', VmAssets.VM_NAMES)
def test_013_delete_vm_devices(vm_name, request):
    depends(request, ['ADD_DEVICES_TO_VM'])
    for device, info in VmAssets.VM_DEVICES[vm_name].items():
        opts = {}
        if device == 'DISK':
            opts = {'zvol': True}

        call('vm.device.delete', info['id'], opts)
        assert not call('vm.device.query', [['id', '=', info['id']]])


@pytest.mark.parametrize('vm_name', VmAssets.VM_NAMES)
@pytest.mark.dependency(name='VM_STARTED')
def test_014_start_vm(vm_name, request):
    depends(request, ['VM_CREATED'])
    _id = VmAssets.VM_INFO[vm_name]['query_response']['id']
    call('vm.start', _id)
    vm_status = call('vm.status', _id)
    assert all((vm_status[key] == 'RUNNING' for key in ('state', 'domain_state')))
    assert all((vm_status['pid'], isinstance(vm_status['pid'], int)))


@pytest.mark.parametrize('vm_name', VmAssets.VM_NAMES)
def test_015_query_vm_info(vm_name, request):
    depends(request, ['VIRT_SUPPORTED', 'VM_CREATED', 'VM_STARTED'])
    _id = VmAssets.VM_INFO[vm_name]['query_response']['id']
    vm_string = f'{_id}_{vm_name}'
    assert call('vm.get_console', _id) == vm_string
    assert vm_string in call('vm.log_file_path', _id)

    mem_keys = ('RNP', 'PRD', 'RPRD')
    mem_info = call('vm.get_vmemory_in_use')
    assert isinstance(mem_info, dict)
    assert all((key in mem_info for key in mem_keys))
    assert all((isinstance(mem_info[key], int) for key in mem_keys))


@pytest.mark.parametrize('vm_name', VmAssets.VM_NAMES)
@pytest.mark.dependency(name='VM_SUSPENDED')
def test_020_suspend_vm(vm_name, request):
    depends(request, ['VIRT_SUPPORTED', 'VM_CREATED', 'VM_STARTED'])
    _id = VmAssets.VM_INFO[vm_name]['query_response']['id']
    call('vm.suspend', _id)
    for retry in range(1, 4):
        status = call('vm.status', _id)
        if all((status['state'] == 'SUSPENDED', status['domain_state'] == 'PAUSED')):
            break
        else:
            time.sleep(1)
    else:
        assert False, f'Timed out after {retry} seconds waiting on {vm_name!r} to suspend'


@pytest.mark.parametrize('vm_name', VmAssets.VM_NAMES)
@pytest.mark.dependency(name='VM_RESUMED')
def test_021_resume_vm(vm_name, request):
    depends(request, ['VM_SUSPENDED'])
    _id = VmAssets.VM_INFO[vm_name]['query_response']['id']
    call('vm.resume', _id)
    for retry in range(1, 4):
        status = call('vm.status', _id)
        if all((status['state'] == 'RUNNING', status['domain_state'] == 'RUNNING')):
            break
        else:
            time.sleep(1)
    else:
        assert False, f'Timed out after {retry} seconds waiting on {vm_name!r} to resume'

@pytest.mark.skip(reason='Takes > 60 seconds and is flaky')
@pytest.mark.parametrize('vm_name', VmAssets.VM_NAMES)
@pytest.mark.dependency(name='VM_RESTARTED')
def test_022_restart_vm(vm_name, request):
    depends(request, ['VM_RESUMED'])
    _id = VmAssets.VM_INFO[vm_name]['query_response']['id']
    call('vm.restart', _id, job=True)
    status = call('vm.status', _id)
    assert all((status['state'] == 'RUNNING', status['domain_state'] == 'RUNNING'))


@pytest.mark.parametrize('vm_name', VmAssets.VM_NAMES)
@pytest.mark.dependency(name='VM_POWERED_OFF')
def test_023_poweroff_vm(vm_name, request):
    depends(request, ['VM_RESUMED'])
    _id = VmAssets.VM_INFO[vm_name]['query_response']['id']
    call('vm.poweroff', _id)
    for retry in range(1, 4):
        status = call('vm.status', _id)
        if all((status['state'] == 'STOPPED', status['domain_state'] == 'SHUTOFF')):
            break
        else:
            time.sleep(1)
    else:
        assert False, f'Timed out after {retry} seconds waiting on {vm_name!r} to poweroff'


@pytest.mark.parametrize('vm_name', VmAssets.VM_NAMES)
@pytest.mark.dependency(name='VM_UPDATED')
def test_024_update_powered_off_vm(vm_name, request):
    depends(request, ['VM_POWERED_OFF'])
    _id = VmAssets.VM_INFO[vm_name]['query_response']['id']
    new_mem = 768
    call('vm.update', _id, {'memory': new_mem})
    assert call('vm.query', [['id', '=', _id]], {'get': True})['memory'] == new_mem


@pytest.mark.parametrize('vm_name', VmAssets.VM_NAMES)
def test_024_clone_powered_off_vm(vm_name, request):
    depends(request, ['VM_POWERED_OFF'])
    to_clone_id = VmAssets.VM_INFO[vm_name]['query_response']['id']
    new_name = f'{vm_name}_clone'
    call('vm.clone', to_clone_id, new_name)
    qry = call('vm.query', [['name', '=', new_name]], {'get': True})
    VmAssets.VM_INFO.update({new_name: {'query_response': qry}})
    assert call('vm.get_console', qry['id']) == f'{qry["id"]}_{new_name}'

    VmAssets.VM_DEVICES.update({new_name: dict()})
    for dev in call('vm.device.query', [['vm', '=', qry['id']]]):
        if dev['dtype'] in ('DISK', 'NIC', 'DEVICE'):
            # add this to VM_DEVICES so we properly clean-up after
            # the test module runs
            VmAssets.VM_DEVICES[new_name].update({dev['dtype']: dev})


def test_025_cleanup_vms(request):
    depends(request, ['VM_POWERED_OFF'])
    for vm in call('vm.query'):
        call('vm.delete', vm['id'])
        assert not call('vm.query', [['name', '=', vm['id']]])
