import pytest

from middlewared.test.integration.assets.roles import common_checks


@pytest.mark.parametrize('method, expected_error', [
    ('vm.virtualization_details', False),
    ('vm.maximum_supported_vcpus', False),
    ('vm.get_display_devices', True),
    ('vm.get_display_web_uri', True),
    ('vm.get_available_memory', False),
    ('vm.bootloader_options', False),
])
def test_vm_readonly_role(unprivileged_user_fixture, method, expected_error):
    common_checks(unprivileged_user_fixture, method, 'READONLY_ADMIN', True, valid_role_exception=expected_error)


@pytest.mark.parametrize('role, method, valid_role', [
    ('VM_READ', 'vm.supports_virtualization', True),
    ('VM_WRITE', 'vm.supports_virtualization', True),
    ('VM_READ', 'vm.virtualization_details', True),
    ('VM_WRITE', 'vm.virtualization_details', True),
    ('VM_READ', 'vm.maximum_supported_vcpus', True),
    ('VM_WRITE', 'vm.maximum_supported_vcpus', True),
    ('VM_READ', 'vm.flags', True),
    ('VM_WRITE', 'vm.flags', True),
    ('VM_READ', 'vm.cpu_model_choices', True),
    ('VM_WRITE', 'vm.cpu_model_choices', True),
    ('VM_READ', 'vm.port_wizard', True),
    ('VM_READ', 'vm.bootloader_options', True),
])
def test_vm_read_write_roles(unprivileged_user_fixture, role, method, valid_role):
    common_checks(unprivileged_user_fixture, method, role, valid_role, valid_role_exception=False)


@pytest.mark.parametrize('role, method, valid_role', [
    ('VM_WRITE', 'vm.clone', True),
    ('VM_READ', 'vm.get_memory_usage', True),
    ('VM_WRITE', 'vm.get_memory_usage', True),
    ('VM_READ', 'vm.start', False),
    ('VM_WRITE', 'vm.start', True),
    ('VM_READ', 'vm.stop', False),
    ('VM_WRITE', 'vm.stop', True),
    ('VM_READ', 'vm.restart', False),
    ('VM_WRITE', 'vm.restart', True),
    ('VM_READ', 'vm.suspend', False),
    ('VM_WRITE', 'vm.suspend', True),
    ('VM_READ', 'vm.resume', False),
    ('VM_WRITE', 'vm.resume', True),
    ('VM_READ', 'vm.get_vm_memory_info', True),
    ('VM_READ', 'vm.get_display_devices', True),
    ('VM_READ', 'vm.status', True),
    ('VM_READ', 'vm.log_file_path', True),
])
def test_vm_read_write_roles_requiring_virtualization(unprivileged_user_fixture, role, method, valid_role):
    common_checks(unprivileged_user_fixture, method, role, valid_role)


@pytest.mark.parametrize('role, method, valid_role', [
    ('VM_DEVICE_READ', 'vm.device.iommu_enabled', True),
    ('VM_DEVICE_READ', 'vm.device.passthrough_device_choices', True),
    ('VM_DEVICE_READ', 'vm.device.nic_attach_choices', True),
    ('VM_DEVICE_READ', 'vm.device.usb_passthrough_choices', True),
    ('VM_READ', 'vm.guest_architecture_and_machine_choices', True),
])
def test_vm_device_read_write_roles(unprivileged_user_fixture, role, method, valid_role):
    common_checks(unprivileged_user_fixture, method, role, valid_role, valid_role_exception=False)


@pytest.mark.parametrize('role, method, valid_role', [
    ('VM_DEVICE_READ', 'vm.device.passthrough_device', True),
    ('VM_DEVICE_WRITE', 'vm.device.passthrough_device', True),
])
def test_vm_device_read_write_roles_requiring_virtualization(unprivileged_user_fixture, role, method, valid_role):
    common_checks(unprivileged_user_fixture, method, role, valid_role)
