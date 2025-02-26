import json
import pytest

from contextlib import contextmanager
from copy import deepcopy

from middlewared.test.integration.assets.account import user, group
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.assets.virt import (
    virt,
    virt_device,
    virt_instance,
)
from middlewared.test.integration.utils.call import call
from middlewared.test.integration.utils.ssh import ssh


@contextmanager
def userns_user(username, userns_idmap='DIRECT'):
    with user({
        'username': username,
        'full_name': username,
        'group_create': True,
        'random_password': True,
        'userns_idmap': userns_idmap
    }) as u:
        yield u


@contextmanager
def userns_group(groupname, userns_idmap='DIRECT'):
    with group({
        'name': groupname,
        'userns_idmap': userns_idmap
    }) as g:
        yield g


@pytest.fixture(scope='module')
def instance():
    with virt():
        with virt_instance('virtacltest') as i:
            # install dependencies

            # libjansson is required for our nfsv4 acl tools (once they work)
            ssh(f'incus exec {i["name"]} apt install -y libjansson4')

            yield i


@pytest.fixture(scope='function')
def nfs4acl_dataset(instance):
    with userns_group('testgrp') as g:
        with userns_user('testusr') as u:
            # restart to get idmap changes
            call('virt.instance.restart', instance['name'])

            with dataset('virtnfsshare', {'share_type': 'SMB'}) as ds:
                with virt_device(instance['name'], 'disknfs', 'DISK', {
                    'source': f'/mnt/{ds}',
                    'destination': '/nfs4acl',
                }) as dev:
                    yield {
                        'user': u,
                        'group': g,
                        'dataset': ds,
                        'dev': '/nfs4acl'
                    }


def check_access(instance_name, path, account_string, expected_access):
    prefix = f'incus exec {instance_name}'

    # READ and MODIFY should be able to list
    match expected_access:
        case 'READ':
            ssh(' '.join([prefix, account_string, 'ls', path]))
            ssh(' '.join([prefix, account_string, 'mkdir', f'{path}/testdir']))
        case 'MODIFY':
            ssh(' '.join([prefix, account_string, 'ls', path]))
            ssh(' '.join([prefix, account_string, 'mkdir', f'{path}/testdir']))
            ssh(' '.join([prefix, account_string, 'rmdir', f'{path}/testdir']))
        case None:
            ssh(' '.join([prefix, account_string, 'ls', path]))
            ssh(' '.join([prefix, account_string, 'mkdir', f'{path}/testdir']))
        case _:
            raise ValueError(f'{expected_access}: unexpected access string')


def test_virt_instance_nfs4acl_functional(instance, nfs4acl_dataset):
    path = f'/mnt/{nfs4acl_dataset["dataset"]}'
    acl_info = call('filesystem.getacl', path)
    assert acl_info['acltype'] == 'NFS4'
    acl = deepcopy(acl_info['acl'])
    acl.extend([
        {
            'tag': 'GROUP',
            'type': 'ALLOW',
            'perms': {'BASIC': 'READ'},
            'flags': {'BASIC': 'INHERIT'},
            'id': nfs4_dataset['group']['gid']
        },
        {
            'tag': 'USER',
            'type': 'ALLOW',
            'perms': {'BASIC': 'READ'},
            'flags': {'BASIC': 'INHERIT'},
            'id': u['uid']
        }
    ])

    # set the ACL
    call('filesystem.setacl', {'path': path, 'dacl': acl}, job=True)

    ssh(f'cp /bin/nfs4xdr_getfacl {host_path}/nfs4xdr_getfacl')
    ssh(f'cp /bin/nfs4xdr_setfacl {host_path}/nfs4xdr_setfacl')

    # TODO: fix tools for getting / setting ACL to work with idmaps
    """
    ssh(f'cp /bin/nfs4xdr_getfacl /mnt/{ds}/nfs4xdr_getfacl')

    cmd = [
        'incus', 'exec', '-T', instance['name'],
        '-- bash -c "/host/nfs4xdr_getfacl -j /host"'
    ]
    instance_acl = json.loads(ssh(' '.join(cmd)))

    # Check that the ids in the ACL have been mapped
    check_nfs4_acl_entry(
        instance_acl['acl'],
        nfs4acl_dataset['group']['gid'],
        'ALLOW',
        'GROUP',
        {'BASIC': 'READ'},
        {'BASIC': 'INHERIT'}
    )

    check_nfs4_acl_entry(
        instance_acl['acl'],
        instance['user']['uid'],
        'ALLOW',
        'USER',
        {'BASIC': 'READ'},
        {'BASIC': 'INHERIT'}
    )
    """

    check_access(
        instance['name'],
        nfs4acl_dataset['dev'],
        f'--user {nfs4acl_dataset["user"]["uid"]}',
        'READ'
    )

    check_access(
        instance['name'],
        nfs4acl_dataset['dev'],
        f'--group {nfs4acl_dataset["group"]["gid"]}',
        'READ'
    )

    acl = deepcopy(acl_info['acl'])
    acl.extend([
        {
            'tag': 'GROUP',
            'type': 'ALLOW',
            'perms': {'BASIC': 'MODIFY'},
            'flags': {'BASIC': 'INHERIT'},
            'id': nfs4_dataset['group']['gid']
        },
        {
            'tag': 'USER',
            'type': 'ALLOW',
            'perms': {'BASIC': 'MODIFY'},
            'flags': {'BASIC': 'INHERIT'},
            'id': u['uid']
        }
    ])

    # set the ACL
    call('filesystem.setacl', {'path': path, 'dacl': acl}, job=True)

    check_access(
        instance['name'],
        nfs4acl_dataset['dev'],
        f'--user {nfs4acl_dataset["user"]["uid"]}',
        'MODIFY'
    )

    check_access(
        instance['name'],
        nfs4acl_dataset['dev'],
        f'--group {nfs4acl_dataset["group"]["gid"]}',
        'MODIFY'
    )

    # check that user without mapped uid / gid in ACL gets no access
    check_access(
        instance['name'],
        nfs4acl_dataset['dev'],
        '',
        None
    )
