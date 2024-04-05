import contextlib
import dataclasses
import json
import os
import time
import stat

import pytest
from pytest_dependency import depends

from middlewared.client import ClientException
from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.assets.account import user as user_asset
from middlewared.test.integration.assets.pool import dataset as dataset_asset
from middlewared.test.integration.utils import call, ssh

from functions import POST, GET, DELETE, PUT, SSH_TEST, wait_on_job
from auto_config import pool_name, ha, password, user, ip
SHELL = '/usr/bin/bash'
VAR_EMPTY = '/var/empty'
ROOT_GROUP = 'root'
DEFAULT_HOMEDIR_OCTAL = 0o40700
group_id = GET(f'/group/?group={GROUP}', controller_a=ha).json()[0]['id']
dataset = f"{pool_name}/test_homes"
dataset_url = dataset.replace('/', '%2F')
SMB_CONFIGURED_SENTINEL = '/var/run/samba/.configured'

home_files = {
    "~/": oct(DEFAULT_HOMEDIR_OCTAL),
    "~/.profile": "0o100644",
    "~/.ssh": "0o40700",
    "~/.ssh/authorized_keys": "0o100600",
}

home_acl = [
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
]


@dataclasses.dataclass
class HomeAssets:
    Dataset01 = {
        'name': dataset,
        'share_type': 'SMB',
        'acltype': 'NFSV4',
        'aclmode': 'RESTRICTED'
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
    results = SSH_TEST(f'cat {file_name}', user, password, ip)
    assert results['result'], results['output']
    assert expected_line in results['stdout'].splitlines(), results['output']


@contextlib.contextmanager
def create_user_with_dataset(ds_info, user_info):
    with dataset_asset(ds_info['name'], ds_info.get('options', []), **ds_info.get('kwargs', {})) as ds:
        if 'path' in user_info:
            user_info['payload']['home'] = os.path.join(f'/mnt/{ds}', user_info['path'])

        user_id = None
        try:
            user_id = call('user.create', user_info['payload'])
            yield call('user.query', [['id', '=', user_id]], {'get': True})
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
    qry = call('user.query', [['username', '=', UserAssets.TestUser01['create_payload']['username']]], {'get': True})
    UserAssets.TestUser01['query_response'].update(qry)

    # verify basic info
    for key in UserAssets.TestUser01['create_payload']:
        assert qry[key] == UserAssets.TestUser01['query_response'][key]

    # verify various /etc files were updated
    for f in (
        {
            'file': '/etc/shadow',
            'value': f'testuser:{qry["unixhash"]}:18397:0:99999:7:::'
        },
        {
            'file': '/etc/passwd',
            'value': f'testuser:x:{qry["uid"]}:{qry["group"]["bsdgrp_gid"]}:{qry["full_name"]}:{qry["home"]}:{qry["shell"]}'
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
        user, password, ip
    )
    assert results['result'] is False, str(results['output'])


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
    assert pw['sid_info'] is not None
    assert pw['sid_info']['domain_information']['online']
    assert pw['sid_info']['domain_information']['activedirectory'] is False


def test_003_get_next_uid_again(request):
    """user.get_next_uid should always return a unique uid"""
    depends(request, [UserAssets.TestUser01['depends_name']])
    assert call('user.get_next_uid') != UserAssets.TestUser01['create_payload']['uid']


def test_004_update_and_verify_user_groups(request):
    """Add the user to the root users group"""
    depends(request, [UserAssets.TestUser01['depends_name']])
    call(
        'user.update',
        UserAssets.TestUser01['query_response']['id'],
        {'groups': ROOT_GROUP}
    )

    grouplist = call(
        'user.get_user_obj',
        {'username': UserAssets.TestUser01['create_payload']['username'], 'get_groups': True}
    )['grouplist']
    assert 0 in grouplist


def test_006_delete_testuser(request):
    depends(request, [UserAssets.TestUser01['depends_name']])
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
    UserAssets.ShareUser01['create_payload']['grouplist'].append(
        call('group.query', [['group', '=', ROOT_GROUP]], {'get': True})['id']
    )

    call('user.create', UserAssets.ShareUser01['create_payload'])
    qry = call('user.query', [['username', '=', UserAssets.ShareUser01['create_payload']['username']]], {'get': True})
    UserAssets.ShareUser01['query_response'].update(qry)

    # verify basic info
    for key in UserAssets.ShareUser01['create_payload']:
        assert qry[key] == UserAssets.ShareUser01['query_response'][key]

    # verify password doesn't leak to middlewared.log
    # we do this inside the create and verify function
    # because this is severe enough problem that we should
    # just "fail" at this step so it sets off a bunch of
    # red flags in the CI
    results = SSH_TEST(
        f'grep -R {UserAssets.ShareUser01["create_payload"]["password"]!r} /var/log/middlewared.log',
        user, password, ip
    )
    assert results['result'] is False, str(results['output'])


@pytest.mark.dependency(name="HOME_DS_CREATED")
def test_30_creating_home_dataset(request):
    """
    SMB share_type is selected for this test so that
    we verify that ACL is being stripped properly from
    the newly-created home directory.
    """
    depends(request, [UserAssets.ShareUser01['depends_name']])
    payload = {
        "name": dataset,
        "share_type": "SMB",
        "acltype": "NFSV4",
        "aclmode": "RESTRICTED"
    }
    results = POST("/pool/dataset/", payload)
    assert results.status_code == 200, results.text

    results = POST(
        f'/pool/dataset/id/{dataset_url}/permission/', {
            'acl': home_acl,
        }
    )
    assert results.status_code == 200, results.text
    perm_job = results.json()
    job_status = wait_on_job(perm_job, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


@pytest.mark.dependency(name="USER_CREATED")
def test_31_creating_user_with_homedir(request):
    depends(request, ["HOME_DS_CREATED"])
    global user_id
    user_payload = {
        "username": "testuser2",
        "full_name": "Test User2",
        "group_create": True,
        "password": "test1234",
        "uid": next_uid,
        "shell": SHELL,
        "sshpubkey": "canary",
        "home": f"/mnt/{dataset}",
        "home_mode": f'{stat.S_IMODE(DEFAULT_HOMEDIR_OCTAL):03o}',
        "home_create": True,
    }
    results = POST("/user/", user_payload)
    assert results.status_code == 200, results.text
    user_id = results.json()
    time.sleep(5)

    results = POST("/user/get_user_obj/", {"username": "testuser2", "sid_info": True})
    assert results.status_code == 200, results.text

    pw = results.json()
    assert pw['pw_dir'] == os.path.join(user_payload['home'], user_payload['username']), results.text
    assert pw['pw_name'] == user_payload['username'], results.text
    assert pw['pw_uid'] == user_payload['uid'], results.text
    assert pw['pw_shell'] == user_payload['shell'], results.text
    assert pw['pw_gecos'] == user_payload['full_name'], results.text

    # this one is created as an SMB user
    assert pw['sid_info'] is not None, results.text
    assert pw['sid_info']['domain_information']['online'], results.text
    assert pw['sid_info']['domain_information']['activedirectory'] is False, results.text


def test_32_verify_post_user_do_not_leak_password_in_middleware_log(request):
    depends(request, ["USER_CREATED"], scope="session")
    cmd = """grep -R "test1234" /var/log/middlewared.log"""
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, str(results['output'])


def test_33_smb_user_passb_entry_exists(request):
    depends(request, ["USER_CREATED"], scope="session")
    result = GET(
        '/user', payload={
            'query-filters': [['username', '=', 'testuser2']],
            'query-options': {
                'get': True,
                'extra': {'additional_information': ['SMB']}
            }
        }
    )
    assert result.status_code == 200, result.text
    assert result.json()['sid'], result.text
    assert result.json()['nt_name'], result.text


@pytest.mark.dependency(name="HOMEDIR_EXISTS")
def test_34_verify_homedir_acl_is_stripped(request):
    depends(request, ["USER_CREATED"])
    # Homedir permissions changes are backgrounded.
    # one second sleep should be sufficient for them to complete.
    time.sleep(1)
    results = POST('/filesystem/stat/', f'/mnt/{dataset}/testuser2')
    assert results.status_code == 200, results.text
    assert results.json()['acl'] is False, results.text  # acl stripped


@pytest.mark.parametrize('to_test', home_files.keys())
def test_36_homedir_check_perm(to_test, request):
    depends(request, ["HOMEDIR_EXISTS"])
    results = POST('/filesystem/stat/', f'/mnt/{dataset}/testuser2/{to_test[2:]}')
    assert results.status_code == 200, results.text
    assert oct(results.json()['mode']) == home_files[to_test], f"{to_test}: {results.text}"
    assert results.json()['uid'] == next_uid, results.text


def test_37_homedir_testfile_create(request):
    depends(request, ["HOMEDIR_EXISTS"], scope="session")
    testfile = f'/mnt/{dataset}/testuser2/testfile.txt'

    cmd = f'touch {testfile}; chown {next_uid} {testfile}'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']

    results = POST('/filesystem/stat/', testfile)
    assert results.status_code == 200, results.text


@pytest.mark.dependency(name="HOMEDIR2_EXISTS")
def test_38_homedir_move_new_directory(request):
    depends(request, ["HOMEDIR_EXISTS"])

    # Validation of autocreation of homedir during path update
    with dataset_asset(os.path.join('test_homes', 'ds2')) as ds:
        results = PUT(f'/user/id/{user_id}', {'home': f'/mnt/{ds}', 'home_create': True})
        assert results.status_code == 200, results.text

        results = GET('/core/get_jobs/?method=user.do_home_copy')
        assert results.status_code == 200, results.text
        job_status = wait_on_job(results.json()[-1]['id'], 180)
        assert job_status['state'] == 'SUCCESS', str(job_status['results'])

        results = POST('/filesystem/stat/', os.path.join(f'/mnt/{ds}', 'testuser2'))
        assert results.status_code == 200, results.text
        assert results.json()['uid'] == next_uid, results.txt

        # now kick the can down the road to the root of our pool
        results = PUT(f'/user/id/{user_id}', {'home': os.path.join('/mnt', pool_name), 'home_create': True})
        assert results.status_code == 200, results.text

        results = GET('/core/get_jobs/?method=user.do_home_copy')
        assert results.status_code == 200, results.text
        job_status = wait_on_job(results.json()[-1]['id'], 180)
        assert job_status['state'] == 'SUCCESS', str(job_status['results'])

        results = POST('/filesystem/stat/', os.path.join('/mnt', pool_name, 'testuser2'))
        assert results.status_code == 200, results.text
        assert results.json()['uid'] == next_uid, results.txt

    new_home = f'/mnt/{dataset}/new_home'
    results = SSH_TEST(f'mkdir {new_home}', user, password, ip)
    assert results['result'] is True, results['output']

    # Validation of changing homedir to existing path without
    # autocreation of subdir for user.
    results = PUT(f"/user/id/{user_id}", {"home": new_home})
    assert results.status_code == 200, results.text

    results = GET('/core/get_jobs/?method=user.do_home_copy')
    assert results.status_code == 200, results.text
    job_status = wait_on_job(results.json()[-1]['id'], 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])

    results = POST('/filesystem/stat/', new_home)
    assert results.status_code == 200, results.text
    assert results.json()['uid'] == next_uid, results.txt


@pytest.mark.parametrize('to_test', home_files.keys())
def test_39_after_move_check_perm(to_test, request):
    depends(request, ["HOMEDIR2_EXISTS"])
    results = POST('/filesystem/stat/', f'/mnt/{dataset}/new_home/{to_test[2:]}')
    assert results.status_code == 200, results.text
    assert oct(results.json()['mode']) == home_files[to_test], f"{to_test}: {results.text}"
    assert results.json()['uid'] == next_uid, results.text


def test_40_testfile_successfully_moved(request):
    depends(request, ["HOMEDIR2_EXISTS"])
    results = POST('/filesystem/stat/', f'/mnt/{dataset}/new_home/testfile.txt')
    assert results.status_code == 200, results.text


def test_41_lock_smb_user(request):
    depends(request, ["USER_CREATED"])
    payload = {
        "locked": True,
    }
    results = PUT(f"/user/id/{user_id}", payload)
    assert results.status_code == 200, results.text

    check_config_file('/etc/shadow', 'testuser2:!:18397:0:99999:7:::')


def test_42_verify_locked_smb_user_is_disabled(request):
    """
    This test verifies that the passdb user is disabled
    when "locked" is set to True.
    """
    depends(request, ["USER_CREATED"], scope="session")
    cmd = "midclt call smb.passdb_list true"
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    pdb_list = json.loads(results['stdout'])
    my_entry = None
    for entry in pdb_list:
        if entry['Unix username'] == "testuser2":
            my_entry = entry
            break

    assert my_entry is not None, results['output']
    if my_entry is not None:
        assert my_entry["Account Flags"] == "[DU         ]", str(my_entry)


def test_43_verify_absent_from_passdb(request):
    """
    This test verifies that the user no longer appears
    in Samba's passdb after "smb" is set to False.
    """
    depends(request, ["USER_CREATED"], scope="session")
    payload = {
        "smb": False,
    }
    results = PUT(f"/user/id/{user_id}", payload)
    assert results.status_code == 200, results.text

    result = GET(
        '/user', payload={
            'query-filters': [['username', '=', 'testuser2']],
            'query-options': {
                'get': True,
                'extra': {'additional_information': ['SMB']}
            }
        }
    )
    assert result.status_code == 200, result.text
    assert result.json()['sid'] == "", result.text
    assert result.json()['nt_name'] == "", result.text


def test_44_homedir_collision(request):
    """
    Verify that validation error is raised if homedir collides with existing one.
    """
    depends(request, ["HOMEDIR2_EXISTS", "shareuser"])
    payload = {
        "home": f'/mnt/{dataset}/new_home',
    }
    results = PUT(f"/user/id/{share_user_db_id}", payload)
    assert results.status_code == 422, results.text


def test_45_deleting_homedir_user(request):
    depends(request, ["USER_CREATED"])
    results = DELETE(f"/user/id/{user_id}/", {"delete_group": True})
    assert results.status_code == 200, results.text


@pytest.mark.dependency(name="NON_SMB_USER_CREATED")
def test_46_creating_non_smb_user(request):
    depends(request, ["HOME_DS_CREATED"])
    global user_id
    payload = {
        "username": "testuser3",
        "full_name": "Test User3",
        "group_create": True,
        "password": "testabcd",
        "uid": next_uid,
        "smb": False
    }
    results = POST("/user/", payload)
    assert results.status_code == 200, results.text
    user_id = results.json()


def test_47_verify_post_user_do_not_leak_password_in_middleware_log(request):
    depends(request, ["NON_SMB_USER_CREATED"], scope="session")
    cmd = """grep -R "testabcd" /var/log/middlewared.log"""
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, str(results['output'])


def test_48_verify_non_smb_user_absent_from_passdb(request):
    """
    Creating new user with "smb" = False must not
    result in a passdb entry being generated.
    """
    depends(request, ["NON_SMB_USER_CREATED"], scope="session")
    result = GET(
        '/user', payload={
            'query-filters': [['username', '=', 'testuser3']],
            'query-options': {
                'get': True,
                'extra': {'additional_information': ['SMB']}
            }
        }
    )
    assert result.status_code == 200, result.text
    assert result.json()['sid'] == "", result.text
    assert result.json()['nt_name'] == "", result.text


def test_49_convert_to_smb_knownfail(request):
    """
    SMB auth for local users relies stored NT hash. We only generate this hash
    for SMB users. This means that converting from non-SMB to SMB requires
    re-submitting password so that we can generate the required hash. If
    payload submitted without password, then validation error _must_ be raised.
    """
    depends(request, ["NON_SMB_USER_CREATED"])
    payload = {
        "smb": True,
    }
    results = PUT(f"/user/id/{user_id}", payload)
    assert results.status_code == 422, results.text


def test_50_convert_to_smb_user(request):
    depends(request, ["NON_SMB_USER_CREATED"])
    payload = {
        "smb": True,
        "password": "testabcd1234",
    }
    results = PUT(f"/user/id/{user_id}", payload)
    assert results.status_code == 200, results.text
    time.sleep(2)


def test_51_verify_put_user_do_not_leak_password_in_middleware_log(request):
    depends(request, ["NON_SMB_USER_CREATED"], scope="session")
    cmd = """grep -R "testabcd1234" /var/log/middlewared.log"""
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, str(results['output'])


def test_52_converted_smb_user_passb_entry_exists(request):
    """
    At this point the non-SMB user has been converted to an SMB user. Verify
    that a passdb entry was appropriately generated.
    """
    global testuser_id
    depends(request, ["NON_SMB_USER_CREATED"], scope="session")
    result = GET(
        '/user', payload={
            'query-filters': [['username', '=', 'testuser3']],
            'query-options': {
                'get': True,
                'extra': {'additional_information': ['SMB']}
            }
        }
    )
    testuser_id = result.json()['id']
    assert result.status_code == 200, result.text
    assert result.json()['sid'], result.text
    assert result.json()['nt_name'], result.text


def test_53_add_user_to_sudoers(request):
    depends(request, ["NON_SMB_USER_CREATED"], scope="session")
    results = PUT(f"/user/id/{testuser_id}", {"sudo_commands": ["ALL"], "sudo_commands_nopasswd": []})
    assert results.status_code == 200, results.text

    check_config_file("/etc/sudoers", "testuser3 ALL=(ALL) ALL")

    results = PUT(f"/user/id/{user_id}", {"sudo_commands": [], "sudo_commands_nopasswd": ["ALL"]})
    assert results.status_code == 200, results.text

    check_config_file("/etc/sudoers", "testuser3 ALL=(ALL) NOPASSWD: ALL")

    results = PUT(f"/user/id/{user_id}", {"sudo_commands": ["ALL"], "sudo_commands_nopasswd": ["ALL"]})
    assert results.status_code == 200, results.text

    check_config_file("/etc/sudoers", "testuser3 ALL=(ALL) ALL, NOPASSWD: ALL")


def test_54_disable_password_auth(request):
    depends(request, ["NON_SMB_USER_CREATED"], scope="session")
    results = PUT(f"/user/id/{testuser_id}", {"password_disabled": True, "smb": False})
    assert results.status_code == 200, results.text

    check_config_file("/etc/shadow", "testuser3:*:18397:0:99999:7:::")


def test_55_deleting_non_smb_user(request):
    depends(request, ["NON_SMB_USER_CREATED"])
    results = DELETE(f"/user/id/{testuser_id}/", {"delete_group": True})
    assert results.status_code == 200, results.text


def test_56_destroying_home_dataset(request):
    depends(request, ["HOME_DS_CREATED"])
    results = DELETE(f"/pool/dataset/id/{dataset_url}/")
    assert results.status_code == 200, results.text


def test_57_check_no_builtin_smb_users(request):
    """
    We have builtin SMB groups, but should have no builtin
    users. Failure here may indicate an issue with builtin user
    synchronization code in middleware. Failure to catch this
    may lead to accidentally granting SMB access to builtin
    accounts.
    """
    result = GET(
        '/user', payload={
            'query-filters': [['builtin', '=', True], ['smb', '=', True]],
            'query-options': {'count': True},
        }
    )
    assert result.json() == 0, result.text


def test_58_create_new_user_existing_home_path(request):
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
        results = POST('/filesystem/stat/', user['home'])
        assert results.status_code == 200, results.text
        assert results.json()['acl'] is False, results.text
        assert f'{stat.S_IMODE(results.json()["mode"]):03o}' == '770', results.text

        # Attempting to repeat the same with new user should
        # fail (no users may share same home path)
        results = POST('/user/', {
            'username': 't2',
            'full_name': 't2',
            'group_create': True,
            'password': 'test1234',
            'home': user['home']
        })
        assert results.status_code == 422, results.text

        # Attempting to put homedir in subdirectory of existing homedir
        # should also rase validation error
        results = POST('/user/', {
            'username': 't2',
            'full_name': 't2',
            'group_create': True,
            'password': 'test1234',
            'home': user['home'],
            'home_create': True,
        })
        assert results.status_code == 422, results.text

        # Attempting to create a user with non-existing path
        results = POST('/user/', {
            'username': 't2',
            'full_name': 't2',
            'group_create': True,
            'password': 'test1234',
            'home': os.path.join(user['home'], 'canary'),
            'home_create': True,
        })
        assert results.status_code == 422, results.text


def test_59_create_user_ro_dataset(request):
    user_info = {
        'username': 't1',
        "full_name": 'T1',
        'group_create': True,
        'password': 'test1234',
        'home_mode': '770',
        'home_create': True,
    }
    with dataset_asset('ro_user_ds', {'readonly': 'ON'}) as ds:
        user_info['home'] = f'/mnt/{ds}'
        results = POST("/user/", user_info)
        assert results.status_code == 422, results.text


@pytest.mark.parametrize('payload', [
    {'group': 1},
    {'home': '/mnt/tank', 'home_create': True},
    {'uid': 777777},
    {'smb': True},
    {'username': 'glusterd_bad'},
])
def test_60_immutable_user_validation(payload, request):
    # Glusterd happens to be an immutable
    user_req = call('user.query', [['username', '=', 'news']], {'get': True})

    with pytest.raises(ValidationErrors) as ve:
        call('user.update', user_req['id'], payload)

    assert ve.value.errors[0].errmsg == 'This attribute cannot be changed'


@contextlib.contextmanager
def toggle_smb_configured():
    ssh(f'rm {SMB_CONFIGURED_SENTINEL}')
    assert call('smb.is_configured') is False
    try:
        yield
    finally:
        call('smb.set_configured')


def test_061_check_smb_configured_sentinel():
    assert call('smb.is_configured')
    with toggle_smb_configured():
        # Check that ValidationError is properly raised
        with pytest.raises(ValidationErrors):
            with user_asset({
                'username': 'doug',
                'full_name': 'doug',
                'group_create': True,
                'password': 'squirrel',
                'smb': True
            }, get_instance=False):
                pass

        with pytest.raises(ClientException):
            call('smb.synchronize_passdb', job=True)

    assert call('smb.is_configured')
    call('smb.synchronize_passdb', job=True)
