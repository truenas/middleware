from copy import deepcopy
import os
import pytest

from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call

permset_posix_full = {"READ": True, "WRITE": True, "EXECUTE": True}
permset_nfsv4_full = {"BASIC": "FULL_CONTROL"}
flagset_nfsv4_inherit = {"BASIC": "INHERIT"}


@pytest.fixture(scope='module')
def posix_acl_dataset():
    with dataset('posix') as ds:
        yield ds


@pytest.fixture(scope='module')
def nfsv4_acl_dataset():
    with dataset('nfs4', data={'share_type': 'SMB'}) as ds:
        yield ds


def test__posix_by_who(posix_acl_dataset):
    target = os.path.join('/mnt', posix_acl_dataset)
    the_acl = call('filesystem.getacl', target)['acl']
    the_acl.extend([
        {'tag': 'USER', 'who': 'root', 'perms': permset_posix_full, 'default': False},
        {'tag': 'GROUP', 'who': 'root', 'perms': permset_posix_full, 'default': False},
        {'tag': 'MASK', 'id': -1, 'perms': permset_posix_full, 'default': False},
    ])

    call('filesystem.setacl', {'path': target, 'dacl': the_acl}, job=True)

    new_acl = call('filesystem.getacl', target)['acl']
    saw_user = False
    saw_group = False
    for entry in new_acl:
        if entry['tag'] == 'USER':
            assert entry['id'] == 0
            assert entry['perms'] == permset_posix_full
            saw_user = True
        elif entry['tag'] == 'GROUP':
            assert entry['id'] == 0
            assert entry['perms'] == permset_posix_full
            saw_group = True


    assert saw_user, str(new_acl)
    assert saw_group, str(new_acl)


def test__nfsv4_by_who(nfsv4_acl_dataset):
    target = os.path.join('/mnt', nfsv4_acl_dataset)
    the_acl = call('filesystem.getacl', target)['acl']
    the_acl.extend([
        {'tag': 'USER', 'who': 'root', 'perms': permset_nfsv4_full, 'flags': flagset_nfsv4_inherit, 'type': 'ALLOW'},
        {'tag': 'GROUP', 'who': 'root', 'perms': permset_nfsv4_full, 'flags': flagset_nfsv4_inherit, 'type': 'ALLOW'},
    ])

    call('filesystem.setacl', {'path': target, 'dacl': the_acl}, job=True)

    new_acl = call('filesystem.getacl', target)['acl']
    saw_user = False
    saw_group = False
    for entry in new_acl:
        if entry['tag'] == 'USER':
            assert entry['id'] == 0
            assert entry['perms'] == permset_nfsv4_full
            saw_user = True
        elif entry['tag'] == 'GROUP' and entry['id'] == 0:
            assert entry['perms'] == permset_nfsv4_full
            saw_group = True

    assert saw_user, str(new_acl)
    assert saw_group, str(new_acl)


def test__acl_validation_errors_posix(posix_acl_dataset):
    target = os.path.join('/mnt', posix_acl_dataset)
    the_acl = call('filesystem.getacl', target)['acl']

    new_acl = deepcopy(the_acl)
    new_acl.extend([
        {'tag': 'USER', 'perms': permset_posix_full, 'default': False},
    ])

    with pytest.raises(ValidationErrors) as ve:
        call('filesystem.setacl', {'path': target, 'dacl': the_acl}, job=True)

    assert ve.value.errors[0].errmsg == 'Numeric ID "id" or account name "who" must be specified'

    new_acl = deepcopy(the_acl)
    new_acl.extend([
        {'tag': 'USER', 'perms': permset_posix_full, 'default': False, 'who': 'root', 'id': 0},
    ])

    with pytest.raises(ValidationErrors) as ve:
        call('filesystem.setacl', {'path': target, 'dacl': the_acl}, job=True)

    assert ve.value.errors[0].errmsg == 'Numeric ID "id" and account name "who" may not be specified simultaneously'
