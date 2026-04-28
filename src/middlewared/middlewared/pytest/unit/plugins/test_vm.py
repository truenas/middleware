import logging
from unittest.mock import AsyncMock, patch

import pytest

from middlewared.api.current import VMCreate, VMFlags
from middlewared.plugins.vm.info import license_active
from middlewared.pytest.unit.helpers import load_compound_service
from middlewared.pytest.unit.middleware import Middleware
from middlewared.service.context import ServiceContext
from middlewared.service_exception import ValidationErrors

VMService = load_compound_service('vm')

VM_PAYLOAD = {
    'name': 'test_vm',
    'description': '',
    'vcpus': 1,
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
    'enable_secure_boot': False,
}

VM_FLAGS = VMFlags(intel_vmx=True, unrestricted_guest=True, amd_rvi=False, amd_asids=False)


@pytest.mark.parametrize('ha_capable,feature_enabled,should_work', [
    (True, False, False),
    (True, True, True),
    (False, False, True),
])
@pytest.mark.asyncio
async def test_vm_license_active_response(ha_capable, feature_enabled, should_work):
    m = Middleware()
    m['system.is_ha_capable'] = lambda *args: ha_capable
    m['system.feature_enabled'] = lambda *args: feature_enabled

    context = ServiceContext(m, logging.getLogger('test'))
    assert await license_active(context) is should_work


@pytest.mark.parametrize('is_licensed', [True, False])
@pytest.mark.asyncio
async def test_vm_creation_for_licensed_and_unlicensed_systems(is_licensed):
    m = Middleware()
    vm_svc = VMService(m)

    m['system.is_ha_capable'] = lambda *args: True
    m['system.feature_enabled'] = lambda *args: is_licensed
    m['datastore.query'] = lambda *args, **kwargs: []

    with patch('middlewared.plugins.vm.crud.vm_flags', new=AsyncMock(return_value=VM_FLAGS)):
        verrors = ValidationErrors()
        data = VMCreate(**VM_PAYLOAD)
        await vm_svc._svc_part.validate(verrors, 'vm_create', data)

    assert [e.errmsg for e in verrors.errors] == (
        [] if is_licensed else ['System is not licensed to use VMs']
    )


@pytest.mark.parametrize('enable_secure_boot,bootloader_ovmf,expected_error', [
    (True, 'OVMF_CODE.secboot.fd', None),
    (True, 'OVMF_CODE_4M.secboot.fd', None),
    (True, 'OVMF_CODE.fd', 'Select a bootloader_ovmf that supports secure boot i.e OVMF_CODE_4M.secboot.fd'),
    (True, 'OVMF_CODE_4M.fd', 'Select a bootloader_ovmf that supports secure boot i.e OVMF_CODE_4M.secboot.fd'),
    (False, 'OVMF_CODE.fd', None),
    (False, 'OVMF_CODE_4M.fd', None),
])
@pytest.mark.asyncio
async def test_vm_secure_boot_ovmf_validation(enable_secure_boot, bootloader_ovmf, expected_error):
    m = Middleware()
    vm_svc = VMService(m)

    m['system.is_ha_capable'] = lambda *args: False
    m['datastore.query'] = lambda *args, **kwargs: []
    m['etc.generate'] = lambda *args: None

    mock_result = AsyncMock()

    ovmf_choices = {
        'OVMF_CODE.fd': 'OVMF_CODE.fd',
        'OVMF_CODE.secboot.fd': 'OVMF_CODE.secboot.fd',
        'OVMF_CODE_4M.fd': 'OVMF_CODE_4M.fd',
        'OVMF_CODE_4M.secboot.fd': 'OVMF_CODE_4M.secboot.fd',
    }

    payload = {**VM_PAYLOAD, 'enable_secure_boot': enable_secure_boot, 'bootloader_ovmf': bootloader_ovmf}
    data = VMCreate(**payload)

    with (
        patch('middlewared.plugins.vm.crud.vm_flags', new=AsyncMock(return_value=VM_FLAGS)),
        patch('middlewared.plugins.vm.crud.bootloader_ovmf_choices', return_value=ovmf_choices),
        patch.object(vm_svc._svc_part, '_create', new=mock_result),
    ):
        try:
            result = await vm_svc._svc_part.do_create(data)
            if expected_error:
                assert False, f"Expected error '{expected_error}' but no error was raised"
            assert result is not None
        except ValidationErrors as e:
            if not expected_error:
                raise
            error_messages = [err.errmsg for err in e.errors]
            assert expected_error in error_messages
