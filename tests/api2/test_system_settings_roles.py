import pytest

from middlewared.test.integration.assets.roles import common_checks


@pytest.mark.parametrize('role,endpoint,payload,should_work,valid_role_exception,is_return_type_none', [
    ('APPS_READ', 'system.general.config', [], False, False, False),
    ('SYSTEM_GENERAL_READ', 'system.general.config', [], True, False, False),
    ('READONLY_ADMIN', 'system.general.update', [{}], False, False, False),
    ('SYSTEM_GENERAL_WRITE', 'system.general.update', [{}], True, False, False),
    ('APPS_READ', 'system.advanced.config', [], False, False, False),
    ('SYSTEM_ADVANCED_READ', 'system.advanced.config', [], True, False, False),
    ('READONLY_ADMIN', 'system.advanced.update', [{}], False, False, False),
    ('SYSTEM_ADVANCED_WRITE', 'system.advanced.update', [{}], True, False, False),
    ('SYSTEM_ADVANCED_READ', 'system.advanced.sed_global_password', [], True, False, False),
    ('APPS_READ', 'system.advanced.sed_global_password', [], False, False, False),
    ('READONLY_ADMIN', 'system.advanced.update_gpu_pci_ids', [[]], False, False, False),
    ('SYSTEM_ADVANCED_WRITE', 'system.advanced.update_gpu_pci_ids', [], True, False, True),
    ('APPS_READ', 'system.general.local_url', [], False, False, False),
    ('SYSTEM_GENERAL_READ', 'system.general.local_url', [], True, False, False),
])
def test_catalog_read_and_write_role(
    unprivileged_user_fixture, role, endpoint, payload, should_work, valid_role_exception, is_return_type_none
):
    common_checks(
        unprivileged_user_fixture, endpoint, role, should_work, is_return_type_none=is_return_type_none,
        valid_role_exception=valid_role_exception, method_args=payload
    )
