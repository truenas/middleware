import contextlib
import dataclasses
import os
import time
import stat

import pytest
from datetime import datetime, UTC
from pytest_dependency import depends

from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.assets.pool import dataset as dataset_asset
from middlewared.test.integration.utils import call, ssh

from functions import SSH_TEST, wait_on_job
from auto_config import pool_name, password, user
SHELL = '/usr/bin/bash'
VAR_EMPTY = '/var/empty'
BUILTIN_ADMINS_GROUP = 'builtin_administrators'
DEFAULT_HOMEDIR_OCTAL = 0o40700
SMB_CONFIGURED_SENTINEL = '/var/run/samba/.configured'
UTC_EPOCH = datetime.fromtimestamp(0, UTC)


@dataclasses.dataclass
class HomeAssets:
    HOME_FILES = {
        'depends_name': '',
        'files': {
            '~/': oct(DEFAULT_HOMEDIR_OCTAL),
            '~/.profile': '0o100644',
            '~/.ssh': '0o40700',
            '~/.ssh/authorized_keys': '0o100600',
        }
    }
    Dataset01 = {
        'depends_name': 'HOME_DS_CREATED',
        'create_payload': {
            'name': f'{pool_name}/test_homes',
            'share_type': 'SMB',
            'acltype': 'NFSV4',
            'aclmode': 'RESTRICTED'
        },
        'home_acl': [
            {
                "tag": "owner@",
                "id": None,
                "type": "ALLOW",
                "perms": {"BASIC": "FULL_CONTROL"},
                "flags": {"BASIC": "INHERIT"}
            },
            {
                "tag": "group@",
                "id": None,
                "type": "ALLOW",
                "perms": {"BASIC": "FULL_CONTROL"},
                "flags": {"BASIC": "INHERIT"}
            },
            {
                "tag": "everyone@",
                "id": None,
                "type": "ALLOW",
                "perms": {"BASIC": "TRAVERSE"},
                "flags": {"BASIC": "NOINHERIT"}
            },
        ],
        'new_home': 'new_home',
    }


@dataclasses.dataclass
class UserAssets:
    TestUser01 = {
        'depends_name': 'user_01',
        'query_response': dict(),
        'get_user_obj_response': dict(),
        'create_payload': {
            'username': 'testuser',
            'full_name': 'Test User',
            'group_create': True,
            'password': 'test1234',
            'uid': None,
            'smb': False,
            'shell': SHELL
        }
    }
    TestUser02 = {
        'depends_name': 'user_02',
        'query_response': dict(),
        'get_user_obj_response': dict(),
        'create_payload': {
            'username': 'testuser2',
            'full_name': 'Test User2',
            'group_create': True,
            'password': 'test1234',
            'uid': None,
            'shell': SHELL,
            'sshpubkey': 'canary',
            'home': f'/mnt/{HomeAssets.Dataset01["create_payload"]["name"]}',
            'home_mode': f'{stat.S_IMODE(DEFAULT_HOMEDIR_OCTAL):03o}',
            'home_create': True,
        },
        'filename': 'testfile_01',
    }
    ShareUser01 = {
        'depends_name': 'share_user_01',
        'query_response': dict(),
        'get_user_obj_reasponse': dict(),
        'create_payload': {
            'username': 'shareuser',
            'full_name': 'Share User',
            'group_create': True,
            'groups': [],
            'password': 'testing',
            'uid': None,
            'shell': SHELL
        }
    }


def check_config_file(file_name, expected_line):
    results = SSH_TEST(f'cat {file_name}', user, password)
    assert results['result'], results['output']
    assert expected_line in results['stdout'].splitlines(), results['output']


@contextlib.contextmanager
def create_user_with_dataset(ds_info, user_info):
    with dataset_asset(ds_info['name'], ds_info.get('options', []), **ds_info.get('kwargs', {})) as ds:
        if 'path' in user_info:
            user_info['payload']['home'] = os.path.join(f'/mnt/{ds}', user_info['path'])

        user_id = None
        try:
            user = call('user.create', user_info['payload'])
            user_id = user['id']
            yield user
        finally:
            if user_id is not None:
                call('user.delete', user_id, {"delete_group": True})


@pytest.mark.dependency(name=UserAssets.TestUser01['depends_name'])
def test_001_create_and_verify_testuser():
    """
    Test for basic user creation. In this case 'smb' is disabled to bypass
    passdb-related code. This is because the passdb add relies on users existing
    in passwd database, and errors during error creation will get masked as
    passdb errors.
    """
    UserAssets.TestUser01['create_payload']['uid'] = call('user.get_next_uid')
    call('user.create', UserAssets.TestUser01['create_payload'])
    username = UserAssets.TestUser01['create_payload']['username']
    qry = call(
        'user.query',
        [['username', '=', username]],
        {'get': True}
    )
    UserAssets.TestUser01['query_response'].update(qry)

    # verify basic info
    for key in ('username', 'full_name', 'shell'):
        assert qry[key] == UserAssets.TestUser01['create_payload'][key]

    shadow_days = (qry['last_password_change'] - UTC_EPOCH).days

    # verify various /etc files were updated
    for f in (
        {
            'file': '/etc/shadow',
            'value': f'{username}:{qry["unixhash"]}:{shadow_days}::::0::'
        },
        {
            'file': '/etc/passwd',
            'value': f'{username}:x:{qry["uid"]}:{qry["group"]["bsdgrp_gid"]}:{qry["full_name"]}:{qry["home"]}:{qry["shell"]}'
        },
        {
            'file': '/etc/group',
            'value': f'{qry["group"]["bsdgrp_group"]}:x:{qry["group"]["bsdgrp_gid"]}:'
        }
    ):
        check_config_file(f['file'], f['value'])

    # verify password doesn't leak to middlewared.log
    # we do this inside the create and verify function
    # because this is severe enough problem that we should
    # just "fail" at this step so it sets off a bunch of
    # red flags in the CI
    results = SSH_TEST(
        f'grep -R {UserAssets.TestUser01["create_payload"]["password"]!r} /var/log/middlewared.log',
        user, password
    )
    assert results['result'] is False, str(results['output'])

    # non-smb users shouldn't show up in smb's passdb
    assert qry['sid'] is None


def test_002_verify_user_exists_in_pwd(request):
    """
    get_user_obj is a wrapper around the pwd module.
    This check verifies that the user is _actually_ created.
    """
    depends(request, [UserAssets.TestUser01['depends_name']])
    pw = call(
        'user.get_user_obj',
        {'username': UserAssets.TestUser01['create_payload']['username'], 'sid_info': True}
    )
    UserAssets.TestUser01['get_user_obj_response'].update(pw)

    # Verify pwd info
    assert pw['pw_uid'] == UserAssets.TestUser01['query_response']['uid']
    assert pw['pw_shell'] == UserAssets.TestUser01['query_response']['shell']
    assert pw['pw_gecos'] == UserAssets.TestUser01['query_response']['full_name']
    assert pw['pw_dir'] == VAR_EMPTY

    # At this point, we're not an SMB user
    assert pw['sid'] is None
    assert pw['source'] == 'LOCAL'
    assert pw['local'] is True


def test_003_get_next_uid_again(request):
    """user.get_next_uid should always return a unique uid"""
    depends(request, [UserAssets.TestUser01['depends_name']])
    assert call('user.get_next_uid') != UserAssets.TestUser01['create_payload']['uid']


def test_004_update_and_verify_user_groups(request):
    """Add the user to the builtin_admins group"""
    depends(request, [UserAssets.TestUser01['depends_name']])
    ba_group_info = call(
        'group.query', [['group', '=', BUILTIN_ADMINS_GROUP]], {'get': True}
    )
    call(
        'user.update',
        UserAssets.TestUser01['query_response']['id'],
        {'groups': [ba_group_info['id']]}
    )

    grouplist = call(
        'user.get_user_obj',
        {'username': UserAssets.TestUser01['create_payload']['username'], 'get_groups': True}
    )['grouplist']
    assert ba_group_info['gid'] in grouplist


@pytest.mark.dependency(name='SMB_CONVERT')
def test_005_convert_non_smbuser_to_smbuser(request):
    depends(request, [UserAssets.TestUser01['depends_name']])
    with pytest.raises(ValidationErrors):
        """
        SMB auth for local users relies on a stored NT hash. We only generate this hash
        for SMB users. This means that converting from non-SMB to SMB requires
        re-submitting password so that we can generate the required hash. If
        payload submitted without password, then validation error _must_ be raised.
        """
        call('user.update', UserAssets.TestUser01['query_response']['id'], {'smb': True})

    rv = call(
        'user.update',
        UserAssets.TestUser01['query_response']['id'],
        {'smb': True, 'password': UserAssets.TestUser01['create_payload']['password']}
    )
    assert rv
    # TODO: why sleep here?
    time.sleep(2)

    # verify converted smb user doesn't leak password
    results = SSH_TEST(
        f'grep -R {UserAssets.TestUser01["create_payload"]["password"]!r} /var/log/middlewared.log',
        user, password
    )
    assert results['result'] is False, str(results['output'])


def test_006_verify_converted_smbuser_passdb_entry_exists(request):
    """
    At this point the non-SMB user has been converted to an SMB user. Verify
    that a passdb entry was appropriately generated.
    """
    depends(request, ['SMB_CONVERT', UserAssets.TestUser01['depends_name']])
    qry = call(
        'user.query',
        [['username', '=', UserAssets.TestUser01['create_payload']['username']]],
        {'get': True, 'extra': {'additional_information': ['SMB']}}
    )
    assert qry
    assert qry['sid']


def test_007_add_smbuser_to_sudoers(request):
    depends(request, ['SMB_CONVERT', UserAssets.TestUser01['depends_name']])
    username = UserAssets.TestUser01['create_payload']['username']
    # all sudo commands
    call(
        'user.update',
        UserAssets.TestUser01['query_response']['id'],
        {'sudo_commands': ['ALL'], 'sudo_commands_nopasswd': []}
    )
    check_config_file('/etc/sudoers', f"{username} ALL=(ALL) ALL")

    # all sudo commands no password
    call(
        'user.update',
        UserAssets.TestUser01['query_response']['id'],
        {'sudo_commands': [], 'sudo_commands_nopasswd': ['ALL']}
    )
    check_config_file('/etc/sudoers', f"{username} ALL=(ALL) NOPASSWD: ALL")

    # all sudo commands and all sudo commands no password
    call(
        'user.update',
        UserAssets.TestUser01['query_response']['id'],
        {'sudo_commands': ['ALL'], 'sudo_commands_nopasswd': ['ALL']}
    )
    check_config_file('/etc/sudoers', f"{username} ALL=(ALL) ALL, NOPASSWD: ALL")


def test_008_disable_smb_and_password(request):
    depends(request, ['SMB_CONVERT', UserAssets.TestUser01['depends_name']])
    username = UserAssets.TestUser01['create_payload']['username']
    call(
        'user.update',
        UserAssets.TestUser01['query_response']['id'],
        {'password_disabled': True, 'smb': False}
    )
    check_config_file('/etc/shadow', f'{username}:*:::::::')


@pytest.mark.parametrize('username', [UserAssets.TestUser01['create_payload']['username']])
def test_009_delete_user(username, request):
    depends(request, ['SMB_CONVERT', UserAssets.TestUser01['depends_name']])
    # delete the user first
    call(
        'user.delete',
        UserAssets.TestUser01['query_response']['id'],
        {'delete_group': True}
    )
    assert not call(
        'user.query',
        [['username', '=', UserAssets.TestUser01['query_response']['username']]]
    )


# FIXME: why is this being called here randomly in the middle of this test? And why are we using REST?
# def test_25_has_local_administrator_set_up(request):
    # depends(request, ["user_02", "user_01"])
    # assert GET('/user/has_local_administrator_set_up/', anonymous=True).json() is True


@pytest.mark.dependency(name=UserAssets.ShareUser01['depends_name'])
def test_020_create_and_verify_shareuser():
    UserAssets.ShareUser01['create_payload']['uid'] = call('user.get_next_uid')
    UserAssets.ShareUser01['create_payload']['groups'].append(
        call('group.query', [['group', '=', BUILTIN_ADMINS_GROUP]], {'get': True})['id']
    )

    call('user.create', UserAssets.ShareUser01['create_payload'])
    qry = call('user.query', [['username', '=', UserAssets.ShareUser01['create_payload']['username']]], {'get': True})
    UserAssets.ShareUser01['query_response'].update(qry)

    # verify basic info
    for key in ('username', 'full_name', 'shell'):
        assert qry[key] == UserAssets.ShareUser01['create_payload'][key]

    # verify password doesn't leak to middlewared.log
    # we do this inside the create and verify function
    # because this is severe enough problem that we should
    # just "fail" at this step so it sets off a bunch of
    # red flags in the CI
    results = SSH_TEST(
        f'grep -R {UserAssets.ShareUser01["create_payload"]["password"]!r} /var/log/middlewared.log',
        user, password
    )
    assert results['result'] is False, str(results['output'])


@pytest.mark.dependency(name=UserAssets.TestUser02['depends_name'])
def test_031_create_user_with_homedir(request):
    """Create a zfs dataset to be used as a home directory for a
    local user. The user's SMB share_type is selected for this test
    so that we verify that ACL is being stripped properly from the
    newly-created home directory."""
    # create the dataset
    call('pool.dataset.create', HomeAssets.Dataset01['create_payload'])
    call('filesystem.setacl', {
        'path': os.path.join('/mnt', HomeAssets.Dataset01['create_payload']['name']),
        'dacl': HomeAssets.Dataset01['home_acl']
    }, job=True)

    # now create the user
    UserAssets.TestUser02['create_payload']['uid'] = call('user.get_next_uid')
    call('user.create', UserAssets.TestUser02['create_payload'])
    qry = call(
        'user.query',
        [['username', '=', UserAssets.TestUser02['create_payload']['username']]],
        {'get': True, 'extra': {'additional_information': ['SMB']}}
    )
    UserAssets.TestUser02['query_response'].update(qry)

    # verify basic info
    for key in ('username', 'full_name', 'shell'):
        assert qry[key] == UserAssets.TestUser02['create_payload'][key]

    # verify password doesn't leak to middlewared.log
    # we do this here because this is severe enough
    # problem that we should just "fail" at this step
    # so it sets off a bunch of red flags in the CI
    results = SSH_TEST(
        f'grep -R {UserAssets.TestUser02["create_payload"]["password"]!r} /var/log/middlewared.log',
        user, password
    )
    assert results['result'] is False, str(results['output'])

    pw = call(
        'user.get_user_obj',
        {'username': UserAssets.TestUser02['create_payload']['username'], 'sid_info': True}
    )
    UserAssets.TestUser02['get_user_obj_response'].update(pw)

    # verify pwd
    assert pw['pw_dir'] == os.path.join(
        UserAssets.TestUser02['create_payload']['home'], UserAssets.TestUser02['create_payload']['username']
    )
    assert pw['pw_name'] == UserAssets.TestUser02['query_response']['username']
    assert pw['pw_uid'] == UserAssets.TestUser02['query_response']['uid']
    assert pw['pw_shell'] == UserAssets.TestUser02['query_response']['shell']
    assert pw['pw_gecos'] == UserAssets.TestUser02['query_response']['full_name']
    assert pw['sid'] is not None
    assert pw['source'] == 'LOCAL'
    assert pw['local'] is True

    # verify smb user passdb entry
    assert qry['sid']

    # verify homedir acl is stripped
    st_info = call('filesystem.stat', UserAssets.TestUser02['query_response']['home'])
    assert st_info['acl'] is False


def test_035_check_file_perms_in_homedir(request):
    depends(request, [UserAssets.TestUser02['depends_name']])
    home_path = UserAssets.TestUser02['query_response']['home']
    for file, mode in HomeAssets.HOME_FILES['files'].items():
        st_info = call('filesystem.stat', os.path.join(home_path, file.removeprefix('~/')))
        assert oct(st_info['mode']) == mode, f"{file}: {st_info}"
        assert st_info['uid'] == UserAssets.TestUser02['query_response']['uid']


def test_036_create_testfile_in_homedir(request):
    depends(request, [UserAssets.TestUser02['depends_name']])
    filename = UserAssets.TestUser02['filename']
    filepath = f'{UserAssets.TestUser02["query_response"]["home"]}/{filename}'
    results = SSH_TEST(
        f'touch {filepath}; chown {UserAssets.TestUser01["query_response"]["uid"]} {filepath}',
        user, password
    )
    assert results['result'] is True, results['output']
    assert call('filesystem.stat', filepath)


@pytest.mark.dependency(name="HOMEDIR2_EXISTS")
def test_037_move_homedir_to_new_directory(request):
    depends(request, [UserAssets.TestUser02['depends_name']])

    # Validation of autocreation of homedir during path update
    with dataset_asset('temp_dataset_for_home') as ds:
        new_home = os.path.join('/mnt', ds)
        call(
            'user.update',
            UserAssets.TestUser02['query_response']['id'],
            {'home': new_home, 'home_create': True}
        )

        filters = [['method', '=', 'user.do_home_copy']]
        opts = {'get': True, 'order_by': ['-id']}
        move_job_timeout = 300  # 5 mins
        move_job1 = call('core.get_jobs', filters, opts)
        assert move_job1
        rv = wait_on_job(move_job1['id'], move_job_timeout)
        assert rv['state'] == 'SUCCESS', f'JOB: {move_job1!r}, RESULT: {str(rv["results"])}'

        st_info = call('filesystem.stat', os.path.join(new_home, UserAssets.TestUser02['create_payload']['username']))
        assert st_info['uid'] == UserAssets.TestUser02['query_response']['uid']

        # now kick the can down the road to the root of our pool
        new_home = os.path.join('/mnt', pool_name)
        call(
            'user.update',
            UserAssets.TestUser02['query_response']['id'],
            {'home': new_home, 'home_create': True}
        )

        move_job2 = call('core.get_jobs', filters, opts)
        assert move_job2
        assert move_job1['id'] != move_job2['id']
        rv = wait_on_job(move_job2['id'], move_job_timeout)
        assert rv['state'] == 'SUCCESS', f'JOB: {move_job2!r}, RESULT: {str(rv["results"])}'

        st_info = call('filesystem.stat', os.path.join(new_home, UserAssets.TestUser02['create_payload']['username']))
        assert st_info['uid'] == UserAssets.TestUser02['query_response']['uid']


def test_038_change_homedir_to_existing_path(request):
    depends(request, [UserAssets.ShareUser01['depends_name'], UserAssets.TestUser01['depends_name']])
    # Manually create a new home dir
    new_home = os.path.join(
        '/mnt',
        HomeAssets.Dataset01['create_payload']['name'],
        HomeAssets.Dataset01['new_home']
    )
    results = SSH_TEST(f'mkdir {new_home}', user, password)
    assert results['result'] is True, results['output']

    # Move the homedir to existing dir
    call(
        'user.update',
        UserAssets.TestUser02['query_response']['id'],
        {'home': new_home}
    )
    filters = [['method', '=', 'user.do_home_copy']]
    opts = {'get': True, 'order_by': ['-id']}
    move_job_timeout = 300  # 5 mins
    home_move_job = call('core.get_jobs', filters, opts)
    rv = wait_on_job(home_move_job['id'], move_job_timeout)
    assert rv['state'] == 'SUCCESS', str(rv['results'])

    # verify files in the homedir that were moved are what we expect
    for file, mode in HomeAssets.HOME_FILES['files'].items():
        st_info = call('filesystem.stat', os.path.join(new_home, file.removeprefix("~/")))
        assert oct(st_info['mode']) == mode, f"{file}: {st_info}"
        assert st_info['uid'] == UserAssets.TestUser02['query_response']['uid']

    # verify the specific file that existed in the previous homedir location was moved over
    # NOTE: this file was created in test_036
    assert call('filesystem.stat', os.path.join(new_home, UserAssets.TestUser02['filename']))


def test_041_lock_smb_user(request):
    depends(request, [UserAssets.TestUser02['depends_name']], scope='session')
    qry = call('user.update', UserAssets.TestUser02['query_response']['id'], {'locked': True})
    username = UserAssets.TestUser02['create_payload']['username']
    shadow_days = (qry['last_password_change'] - UTC_EPOCH).days

    check_config_file('/etc/shadow', f'{username}:!:{shadow_days}::::0::')

    username = UserAssets.TestUser02['create_payload']['username']

    my_entry = call('smb.passdb_list', [['username', '=', username]], {'get': True})
    assert my_entry['acct_ctrl'] & 0x00000400, str(my_entry)  # 0x00000400 is AUTO_LOCKED in MS-SAMR


def test_042_disable_smb_user(request):
    depends(request, [UserAssets.TestUser02['depends_name']], scope='session')
    assert call('user.update', UserAssets.TestUser02['query_response']['id'], {'smb': False})
    qry = call(
        'user.query',
        [['username', '=', UserAssets.TestUser02['create_payload']['username']]],
        {'get': True, 'extra': {'additional_information': ['SMB']}}
    )
    assert qry
    assert qry['sid'] is None


def test_043_raise_validation_error_on_homedir_collision(request):
    """
    Verify that validation error is raised if homedir collides with existing one.
    """
    depends(request, ['HOMEDIR2_EXISTS', UserAssets.TestUser02['depends_name']], scope='session')
    # NOTE: this was used in test_038
    existing_home = os.path.join(
        '/mnt',
        HomeAssets.Dataset01['create_payload']['name'],
        HomeAssets.Dataset01['new_home']
    )
    with pytest.raises(ValidationErrors):
        call(
            'user.update',
            UserAssets.ShareUser01['query_response']['id'],
            {'home': existing_home}
        )


@pytest.mark.parametrize('username', [UserAssets.TestUser02['create_payload']['username']])
def test_046_delete_homedir_user(username, request):
    depends(request, [UserAssets.TestUser02['depends_name']], scope='session')
    # delete user first
    assert call(
        'user.delete',
        UserAssets.TestUser02['query_response']['id']
    )

    # now clean-up dataset that was used as homedir
    assert call(
        'pool.dataset.delete',
        UserAssets.TestUser02['create_payload']['home'].removeprefix('/mnt/')
    )


def test_050_verify_no_builtin_smb_users(request):
    """
    We have builtin SMB groups, but should have no builtin
    users. Failure here may indicate an issue with builtin user
    synchronization code in middleware. Failure to catch this
    may lead to accidentally granting SMB access to builtin
    accounts.
    """
    qry = call('user.query', [['builtin', '=', True], ['smb', '=', True]], {'count': True})
    assert qry == 0


def test_058_create_new_user_knownfails(request):
    """
    Specifying an existing path without home_create should
    succeed and set mode to desired value.
    """
    ds = {'pool': pool_name, 'name': 'user_test_exising_home_path'}
    user_info = {
        'username': 't1',
        "full_name": 'T1',
        'group_create': True,
        'password': 'test1234',
        'home_mode': '770'
    }
    with create_user_with_dataset(ds, {'payload': user_info, 'path': ''}) as user:
        results = call('filesystem.stat', user['home'])
        assert results['acl'] is False
        assert f'{stat.S_IMODE(results["mode"]):03o}' == '770'

        # Attempting to repeat the same with new user should
        # fail (no users may share same home path)
        user2 = {
            'username': 't2',
            'full_name': 't2',
            'group_create': True,
            'password': 'test1234',
            'home': user['home']
        }
        with pytest.raises(ValidationErrors):
            # Attempting to repeat the same with new user should
            # fail (no users may share same home path)
            call('user.create', user2)

        with pytest.raises(ValidationErrors):
            # Attempting to put homedir in subdirectory of existing homedir
            # should also raise validation error
            user2.update({'home_create': True})
            call('user.create', user2)

        with pytest.raises(ValidationErrors):
            # Attempting to create a user with non-existing path
            user2.update({'home': os.path.join(user2['home'], 'canary')})
            call('user.create', user2)


def test_059_create_user_ro_dataset(request):
    with dataset_asset('ro_user_ds', {'readonly': 'ON'}) as ds:
        with pytest.raises(ValidationErrors):
            call('user.create', {
                'username': 't1',
                'full_name': 'T1',
                'group_create': True,
                'password': 'test1234',
                'home_mode': '770',
                'home_create': True,
                'home': f'/mnt/{ds}'
            })


def test_060_immutable_user_validation(request):
    # the `news` user is immutable
    immutable_id = call('user.query', [['username', '=', 'news']], {'get': True})['id']
    default_err = 'This attribute cannot be changed'
    to_validate = [
        ({'group': 1}, default_err),
        ({'home': '/mnt/tank', 'home_create': True}, default_err),
        ({'smb': True}, 'Password authentication may not be disabled for SMB users.'),
        ({'username': 'no_way_bad'}, default_err),
    ]
    for attr, expected_err in to_validate:
        with pytest.raises(ValidationErrors) as ve:
            call('user.update', immutable_id, attr)
        assert ve.value.errors[0].errmsg == expected_err


@contextlib.contextmanager
def toggle_smb_configured():
    ssh(f'rm {SMB_CONFIGURED_SENTINEL}')
    assert call('smb.is_configured') is False
    try:
        yield
    finally:
        call('smb.set_configured')


def test_099_cleanup_share_user():
    # we have a test that asserts there are no smb accounts created
    # by the time it runs so clean up this account
    call('user.delete', UserAssets.ShareUser01['query_response']['id'])
