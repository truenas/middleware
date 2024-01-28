import pytest

from middlewared.service_exception import ValidationErrors
from middlewared.pytest.unit.helpers import load_compound_service
from middlewared.pytest.unit.middleware import Middleware


VMService = load_compound_service('vm')


@pytest.mark.parametrize('ha_capable,license_features,should_work', [
    (True, [], False),
    (True, ['VM'], True),
    (False, [], True),
])
@pytest.mark.asyncio
async def test_vm_license_active_response(ha_capable, license_features, should_work):
    m = Middleware()
    vm_svc = VMService(m)

    m['system.is_ha_capable'] = lambda *args: ha_capable
    m['system.license'] = lambda *args: {'features': license_features}

    assert await vm_svc.license_active() is should_work


@pytest.mark.parametrize('license_active', [
    True,
    False,
])
@pytest.mark.asyncio
async def test_vm_creation_for_licensed_and_unlicensed_systems(license_active):
    m = Middleware()
    vm_svc = VMService(m)
    vm_payload = {
        'name': 'test_vm',
        'description': '',
        'vcpus': 0,
        'memory': 14336,
        'min_memory': None,
        'autostart': False,
        'time': 'LOCAL',
        'bootloader': 'UEFI',
        'bootloader_ovmf': 'OVMF_CODE.fd',
        'cores': 1,
        'threads': 1,
        'hyperv_enlightenments': False,
        'shutdown_timeout': 90,
        'cpu_mode': 'HOST-PASSTHROUGH',
        'cpu_model': None,
        'cpuset': None,
        'nodeset': None,
        'pin_vcpus': False,
        'hide_from_msr': False,
        'ensure_display_device': True,
        'arch_type': None,
        'machine_type': None,
        'uuid': '64e31dd7-8c76-4dca-8b4b-0126b8853c5b',
        'command_line_args': '',
        'nvram_location': '/mnt/pool/test_vm_VARS.fd',
    }

    m['vm.bootloader_ovmf_choices'] = lambda *args: {'OVMF_CODE.fd': 'OVMF_CODE.fd'}
    m['vm.license_active'] = lambda *args: license_active
    m['vm.query'] = lambda *args: []

    verrors = ValidationErrors()
    await vm_svc.common_validation(verrors, 'vm_create', vm_payload)

    assert [e.errmsg for e in verrors.errors] == (
        [] if license_active else ['System is not licensed to use VMs']
    )
