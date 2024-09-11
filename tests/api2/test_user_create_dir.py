import errno
import os
import pytest

from middlewared.service_exception import CallError
from middlewared.test.integration.assets.account import user
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call

DS_NAME = 'user-create-homedir'


@pytest.fixture(scope='function')
def setup_user():
    with dataset(DS_NAME, data={'share_type': 'SMB'}) as ds:
        with user({
            'username': 'usercreate',
            'full_name': 'usercreate',
            'group_create': True,
            'home': os.path.join('/mnt', ds),
            'home_create': False,
            'password': 'ABCD1234'
        }) as u:
            yield u | {'dataset': ds}


def test_create_homedir(setup_user):
    """ This test validates we can set create a new homedir within the currently set homedir """

    call('user.update', setup_user['id'], {
        'home': setup_user['home'],
        'home_create': True
    })

    new = call('user.query', [['id', '=', setup_user['id']]], {'get': True})
    assert new['home'] == os.path.join(setup_user['home'], setup_user['username'])

    # verify that we won't endlessly create new homedirs within existing one if a user
    # is not very API / design savvy
    call('user.update', setup_user['id'], {
        'home': setup_user['home'],
        'home_create': True
    })

    new2 = call('user.query', [['id', '=', setup_user['id']]], {'get': True})
    assert new2['home'] == new['home']



def test_user_change_homedir_no_traverse(setup_user):
    """ we should not recurse into child datasets """
    with dataset(f'{DS_NAME}/subds') as subds:

        # Verify that new dataset exists in source
        call('filesystem.listdir', setup_user['home'], [['name', '=', 'subds']], {'get': True})

        with dataset('new-path', data={'share_type': 'SMB'}) as ds:
            call('user.update', setup_user['id'], {
                'home': os.path.join('/mnt', ds),
                'home_create': True
            })

            new = call('user.query', [['id', '=', setup_user['id']]], {'get': True})

            # Verify that we did not try to copy over the dataset
            with pytest.raises(CallError) as ce:
                call('filesystem.stat', os.path.join(new['home'], 'subds'))

            assert ce.value.errno == errno.ENOENT


def test_user_change_homedir_no_zfs_ctldir(setup_user):
    """ we should not recurse into / try to copy .zfs if snapdir visible """
    call('pool.dataset.update', setup_user['dataset'], {'snapdir': 'VISIBLE'})

    call('user.update', setup_user['id'], {
        'home': setup_user['home'],
        'home_create': True
    })

    new = call('user.query', [['id', '=', setup_user['id']]], {'get': True})
    assert new['home'] == os.path.join(setup_user['home'], setup_user['username'])


    with pytest.raises(CallError) as ce:
         call('filesystem.stat', os.path.join(new['home'], '.zfs'))

    assert ce.value.errno == errno.ENOENT


def test_user_change_homedir_acl_preserve(setup_user):
    """ If for some reason files within homedir have ACL, it should be preserved on copy """
    ACL = [{
        'tag': 'owner@',
        'id': -1,
        'perms': {'BASIC': 'FULL_CONTROL'},
        'flags': {'BASIC': 'INHERIT'},
        'type': 'ALLOW'
    }]
    call('filesystem.mkdir', {'path': os.path.join(setup_user['home'], 'canary')})

    call('filesystem.setacl', {
        'path': os.path.join(setup_user['home'], 'canary'),
        'dacl': ACL
    }, job=True)


    call('user.update', setup_user['id'], {
        'home': setup_user['home'],
        'home_create': True
    })

    new = call('user.query', [['id', '=', setup_user['id']]], {'get': True})

    acl = call('filesystem.getacl', os.path.join(new['home'], 'canary'))['acl']

    assert acl == ACL
