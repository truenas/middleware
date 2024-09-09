import errno

import pytest

from middlewared.service_exception import ValidationErrors, ValidationError
from middlewared.test.integration.utils import call, ssh


def test_get_default_environment_and_make_new_one():
    active_be_id = call('bootenv.query', [['activated', '=', True]], {'get': True})['id']

    # create duplicate name to test failure
    with pytest.raises(ValidationErrors) as ve:
        call('bootenv.create', {'name': active_be_id, 'source': active_be_id})
    assert ve.value.errors == [
        ValidationError('bootenv_create.name', f'The name "{active_be_id}" already exists', errno.EEXIST)
    ]

    # create new bootenv and activate it
    call('bootenv.create', {'name': 'bootenv01', 'source': active_be_id})
    call('bootenv.query', [['name', '=', 'bootenv01']], {'get': True})


def test_change_boot_environment_name_and_attributes_then_delete():
    call('bootenv.update', 'bootenv01', {'name': 'bootenv03'})
    call('bootenv.set_attribute', 'bootenv03', {'keep': True})
    assert call('bootenv.query', [['name', '=', 'bootenv03']], {'get': True})['keep'] is True
    call('bootenv.set_attribute', 'bootenv03', {'keep': False})
    call('bootenv.delete', 'bootenv03')


def test_promote_current_be_datasets():
    var_log = ssh('df | grep /var/log').split()[0]

    snapshot_name = 'snap-1'
    snapshot = f'{var_log}@{snapshot_name}'
    ssh(f'zfs snapshot {snapshot}')
    try:
        clone = 'boot-pool/ROOT/clone'
        ssh(f"zfs clone {snapshot} {clone}")
        try:
            ssh(f'zfs promote {clone}')

            assert ssh(f'zfs get -H -o value origin {var_log}').strip() == f'{clone}@{snapshot_name}'

            call('bootenv.promote_current_be_datasets')

            assert ssh(f'zfs get -H -o value origin {var_log}').strip() == '-'
        finally:
            ssh(f'zfs destroy {clone}')
    finally:
        ssh(f'zfs destroy {snapshot}')
