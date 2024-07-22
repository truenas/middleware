import dataclasses
import errno

import pytest

from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, ssh
from truenas_api_client import ClientException


@dataclasses.dataclass
class AclIds:
    user_to_add: int = 8765309
    user2_to_add: int = 8765310
    group_to_add: int = 1138


def check_for_entry(acl, id_type, xid, perms, is_posix=False):
    has_entry = has_default = has_access = False
    for ace in acl:
        if ace['id'] == xid and ace['tag'] == id_type and ace['perms'] == perms:
            if is_posix:
                if ace['default']:
                    assert has_default is False
                    has_default = True
                else:
                    assert has_access is False
                    has_access = True

            else:
                assert has_entry is False
                has_entry = True

    return has_entry or (has_access and has_default)


def test_simplified_apps_api_posix_acl():
    posix_acl = [
       {'id_type': 'USER', 'id': AclIds.user_to_add, 'access': 'MODIFY'},
       {'id_type': 'GROUP', 'id': AclIds.group_to_add, 'access': 'READ'},
       {'id_type': 'USER', 'id': AclIds.user_to_add, 'access': 'FULL_CONTROL'},
    ]
    with dataset('APPS_POSIX') as ds:
        ds_path = f'/mnt/{ds}'
        call('filesystem.add_to_acl', {'path': ds_path, 'entries': posix_acl}, job=True)
        acl = call('filesystem.getacl', ds_path)['acl']
        assert check_for_entry(
            acl,
            'USER',
            AclIds.user_to_add,
            {'READ': True, 'WRITE': True, 'EXECUTE': True}, True
        ), acl
        assert check_for_entry(
            acl,
            'GROUP',
            AclIds.group_to_add,
            {'READ': True, 'WRITE': False, 'EXECUTE': True}, True
        ), acl


def test_simplified_apps_api_nfs4_acl(request):
    nfs4_acl = [
       {'id_type': 'USER', 'id': AclIds.user_to_add, 'access': 'MODIFY'},
       {'id_type': 'GROUP', 'id': AclIds.group_to_add, 'access': 'READ'},
       {'id_type': 'USER', 'id': AclIds.user2_to_add, 'access': 'FULL_CONTROL'},
    ]
    with dataset('APPS_NFS4', {'share_type': 'APPS'}) as ds:
        ds_path = f'/mnt/{ds}'
        call('filesystem.add_to_acl', {'path': ds_path, 'entries': nfs4_acl}, job=True)
        acl = call('filesystem.getacl', ds_path)['acl']
        assert check_for_entry(acl, 'USER', AclIds.user_to_add, {'BASIC': 'MODIFY'}), acl
        assert check_for_entry(acl, 'GROUP', AclIds.group_to_add, {'BASIC': 'READ'}), acl
        assert check_for_entry(acl, 'USER', AclIds.user2_to_add, {'BASIC': 'FULL_CONTROL'}), acl

        # check behavior of using force option.
        # presence of file in path should trigger failure if force is not set
        results = ssh(f'touch {ds_path}/canary', complete_response=True)
        assert results['result'] is True, results

        acl_changed = call('filesystem.add_to_acl', {'path': ds_path, 'entries': nfs4_acl}, job=True)

        assert acl_changed is False

        with pytest.raises(ClientException) as ve:
            call('filesystem.add_to_acl', {'path': ds_path, 'entries': nfs4_acl + [
                {'id_type': 'GROUP', 'id': AclIds.group_to_add, 'access': 'MODIFY'},
            ]}, job=True)

        assert ve.value.errno == errno.EPERM

        # check behavior of using force option.
        # second call with `force` specified should succeed
        acl_changed = call('filesystem.add_to_acl', {
            'path': ds_path,
            'entries': nfs4_acl + [{'id_type': 'GROUP', 'id': AclIds.group_to_add, 'access': 'MODIFY'}],
            'options': {'force': True}i
        }, job=True)

        assert acl_changed is True

        # we already added the entry earlier.
        # this check makes sure we're not adding duplicate entries.
        acl = call('filesystem.getacl', ds_path)['acl']
        assert check_for_entry(acl, 'USER', AclIds.user_to_add, {'BASIC': 'MODIFY'}), acl
        assert check_for_entry(acl, 'GROUP', AclIds.group_to_add, {'BASIC': 'READ'}), acl
        assert check_for_entry(acl, 'USER', AclIds.user2_to_add, {'BASIC': 'FULL_CONTROL'}), acl
