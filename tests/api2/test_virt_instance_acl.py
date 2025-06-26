import pytest

from copy import deepcopy

from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.assets.virt import (
    userns_user,
    userns_group,
    virt,
    virt_device,
    virt_instance,
)
from middlewared.test.integration.utils import call, ssh
from time import sleep

pytestmark = pytest.mark.skip('Disable VIRT tests for the moment')


@pytest.fixture(scope='module')
def instance():
    with virt():
        with virt_instance('virtacltest') as i:
            # install dependencies

            # libjansson is required for our nfsv4 acl tools (once they work)
            ssh(f'incus exec {i["name"]} -- apt install -y libjansson4')

            yield i


@pytest.fixture(scope='function')
def nfs4acl_dataset(instance):
    with userns_group('testgrp') as g:
        with userns_user('testusr') as u:
            # restart to get idmap changes
            call('virt.instance.restart', instance['name'])
            sleep(5)
            with dataset('virtnfsshare', {'share_type': 'SMB'}) as ds:
                with virt_device(instance['name'], 'disknfs', {
                    'dev_type': 'DISK',
                    'source': f'/mnt/{ds}',
                    'destination': '/nfs4acl',
                }):
                    yield {
                        'user': u,
                        'group': g,
                        'dataset': ds,
                        'dev': '/nfs4acl'
                    }


def create_virt_users(instance_name, uid, gid):
    """
    Create three test users.
    * One with the specified UID.
    * One with the specified GID.
    * One who has auxiliary group of specified GID

    These all get evaluated differently based on ACL
    """
    prefix = f'incus exec {instance_name} --'
    ssh(' '.join([prefix, 'useradd', f'-u {uid}', 'larry']))
    ssh(' '.join([prefix, 'useradd', f'-g {gid}', 'curly']))
    ssh(' '.join([prefix, 'useradd', f'-G {gid}', 'moe']))


def check_access(instance_name, path, username, expected_access):
    prefix = f'incus exec {instance_name}'
    account_string = f'-- sudo -i -u {username}'

    # READ and MODIFY should be able to list
    match expected_access:
        case 'READ':
            ssh(' '.join([prefix, account_string, 'ls', path]))
            with pytest.raises(AssertionError, match='Operation not permitted'):
                ssh(' '.join([prefix, account_string, 'mkdir', f'{path}/testdir']))

            with pytest.raises(AssertionError, match='Operation not permitted'):
                ssh(' '.join([prefix, account_string, 'chown', username, path]))

        case 'MODIFY':
            ssh(' '.join([prefix, account_string, 'ls', path]))
            ssh(' '.join([prefix, account_string, 'mkdir', f'{path}/testdir']))
            ssh(' '.join([prefix, account_string, 'rmdir', f'{path}/testdir']))
            with pytest.raises(AssertionError, match='Operation not permitted'):
                ssh(' '.join([prefix, account_string, 'chown', username, path]))

        case 'FULL_CONTROL':
            ssh(' '.join([prefix, account_string, 'chown', username, path]))

        case None:
            with pytest.raises(AssertionError, match='Operation not permitted'):
                ssh(' '.join([prefix, account_string, 'ls', path]))

            with pytest.raises(AssertionError, match='Operation not permitted'):
                ssh(' '.join([prefix, account_string, 'mkdir', f'{path}/testdir']))

            with pytest.raises(AssertionError, match='Operation not permitted'):
                ssh(' '.join([prefix, account_string, 'chown', username, path]))
        case _:
            raise ValueError(f'{expected_access}: unexpected access string')


def test_virt_instance_nfs4acl_functional(instance, nfs4acl_dataset):
    create_virt_users(
        instance['name'],
        nfs4acl_dataset['user']['uid'],
        nfs4acl_dataset['group']['gid']
    )

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
            'id': nfs4acl_dataset['group']['gid']
        },
        {
            'tag': 'USER',
            'type': 'ALLOW',
            'perms': {'BASIC': 'READ'},
            'flags': {'BASIC': 'INHERIT'},
            'id': nfs4acl_dataset['user']['uid']
        }
    ])

    for username in ('larry', 'curly', 'moe'):
        check_access(
            instance['name'],
            nfs4acl_dataset['dev'],
            username,
            None
        )

    # set READ ACL
    call('filesystem.setacl', {'path': path, 'dacl': acl}, job=True)

    ssh(f'cp /bin/nfs4xdr_getfacl {path}/nfs4xdr_getfacl')
    ssh(f'cp /bin/nfs4xdr_setfacl {path}/nfs4xdr_setfacl')

    # FIXME - NAS-134466
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

    for username in ('larry', 'curly', 'moe'):
        check_access(
            instance['name'],
            nfs4acl_dataset['dev'],
            username,
            'READ'
        )

    acl = deepcopy(acl_info['acl'])
    acl.extend([
        {
            'tag': 'GROUP',
            'type': 'ALLOW',
            'perms': {'BASIC': 'MODIFY'},
            'flags': {'BASIC': 'INHERIT'},
            'id': nfs4acl_dataset['group']['gid']
        },
        {
            'tag': 'USER',
            'type': 'ALLOW',
            'perms': {'BASIC': 'MODIFY'},
            'flags': {'BASIC': 'INHERIT'},
            'id': nfs4acl_dataset['user']['uid']
        }
    ])

    # set MODIFY ACL
    call('filesystem.setacl', {'path': path, 'dacl': acl}, job=True)

    for username in ('larry', 'curly', 'moe'):
        check_access(
            instance['name'],
            nfs4acl_dataset['dev'],
            username,
            'MODIFY'
        )

    acl = deepcopy(acl_info['acl'])
    acl.extend([
        {
            'tag': 'GROUP',
            'type': 'ALLOW',
            'perms': {'BASIC': 'FULL_CONTROL'},
            'flags': {'BASIC': 'INHERIT'},
            'id': nfs4acl_dataset['group']['gid']
        },
        {
            'tag': 'USER',
            'type': 'ALLOW',
            'perms': {'BASIC': 'FULL_CONTROL'},
            'flags': {'BASIC': 'INHERIT'},
            'id': nfs4acl_dataset['user']['uid']
        }
    ])

    # set FULL_CONTROL ACL
    call('filesystem.setacl', {'path': path, 'dacl': acl}, job=True)

    for username in ('larry', 'curly', 'moe'):
        check_access(
            instance['name'],
            nfs4acl_dataset['dev'],
            username,
            'FULL_CONTROL'
        )
