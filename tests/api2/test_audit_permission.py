import os

from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call
from middlewared.test.integration.utils.audit import expect_audit_method_calls

JENNY = 8675309


def test_audit_chown():
    with dataset('audit_chown') as ds:
        path = os.path.join('/mnt', ds)
        payload = {'path': path, 'uid': JENNY}

        with expect_audit_method_calls([{
            'method': 'filesystem.chown',
            'params': [payload],
            'description': f'Filesystem change owner {path}'
        }]):
            call('filesystem.chown', payload, job=True)


def test_audit_setperm():
    with dataset('audit_setperm') as ds:
        path = os.path.join('/mnt', ds)
        payload = {'path': path, 'mode': '777'}

        with expect_audit_method_calls([{
            'method': 'filesystem.setperm',
            'params': [payload],
            'description': f'Filesystem set permission {path}'
        }]):
            call('filesystem.setperm', payload, job=True)


def test_audit_setacl():
    with dataset('audit_setacl', {'share_type': 'SMB'}) as ds:
        path = os.path.join('/mnt', ds)
        the_acl = call('filesystem.getacl', os.path.join('/mnt', ds))['acl']
        the_acl.append({
            'tag': 'USER',
            'id': JENNY,
            'perms': {'BASIC': 'FULL_CONTROL'},
            'flags': {'BASIC': 'INHERIT'},
            'type': 'ALLOW'
        })

        payload = {'path': path, 'dacl': the_acl}

        with expect_audit_method_calls([{
            'method': 'filesystem.setacl',
            'params': [payload],
            'description': f'Filesystem set ACL {path}'
        }]):
            call('filesystem.setacl', payload, job=True)
